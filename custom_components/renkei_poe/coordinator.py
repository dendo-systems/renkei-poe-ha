"""Data update coordinator for RENKEI PoE Motor Control integration."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import suppress
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_CONNECTION_STABILISE_DELAY,
    CONF_HEALTH_CHECK_INTERVAL,
    CONF_RECONNECT_INTERVAL,
    DEFAULT_CONNECTION_STABILISE_DELAY,
    DEFAULT_HEALTH_CHECK_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_RECONNECT_INTERVAL,
    DOMAIN,
    MANUFACTURER,
    MODEL,
)
from .motor_status import MotorMotion, motor_motion
from .renkei_client import RenkeiClient, RenkeiConnectionError, ConnectionState

_LOGGER = logging.getLogger(__name__)

# MCU motion updates normally arrive once a second. Silence triggers a query,
# never an assumed stop. Duplicate vendor events must not postpone this check.
MOTION_STATUS_DELAY = 2.0
MOTION_STATUS_MAX_FAILURES = 3


def _generate_device_name(mac_address: str) -> str:
    """Generate device name from MAC address."""
    # Extract last 3 bytes (6 characters) from MAC
    # MAC format: "aabbccddeeff" -> suffix "DDEEFF"
    mac_clean = mac_address.replace(":", "").upper()
    if len(mac_clean) >= 6:
        suffix = mac_clean[-6:]  # Last 3 bytes
        return f"RENKEI PoE {suffix}"
    return f"RENKEI PoE {mac_clean}"


class RenkeiCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from the RENKEI PoE Motor controller."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialise the data update coordinator."""
        options = config_entry.options
        data = config_entry.data
        self.client = RenkeiClient(
            host=data[CONF_HOST],
            port=data.get(CONF_PORT, DEFAULT_PORT),
            reconnect_interval=options.get(
                CONF_RECONNECT_INTERVAL,
                data.get(CONF_RECONNECT_INTERVAL, DEFAULT_RECONNECT_INTERVAL),
            ),
            health_check_interval=options.get(
                CONF_HEALTH_CHECK_INTERVAL,
                data.get(CONF_HEALTH_CHECK_INTERVAL, DEFAULT_HEALTH_CHECK_INTERVAL),
            ),
            connection_stabilise_delay=options.get(
                CONF_CONNECTION_STABILISE_DELAY,
                data.get(
                    CONF_CONNECTION_STABILISE_DELAY,
                    DEFAULT_CONNECTION_STABILISE_DELAY,
                ),
            ),
        )
        
        self._device_info: DeviceInfo | None = None
        self._status_listeners: list[Callable[[dict[str, Any]], None]] = []
        self._connection_listeners: list[Callable[[ConnectionState], None]] = []
        self._motion_status_timer: asyncio.TimerHandle | None = None
        self._motion_status_task: asyncio.Task | None = None
        self._last_position_event: tuple[Any, Any] | None = None
        self._motion_status_failures = 0
        self._shutting_down = False
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,  # Push updates plus a final status query
            always_update=False,
        )
        # Recent HA versions initialize this in the base constructor; retain
        # the explicit entry even when constructed outside its setup context.
        self.config_entry = config_entry
        
        # Set up callbacks
        self.client.set_status_callback(self._handle_status_update)
        self.client.set_connection_callback(self._handle_connection_state)

    async def _async_update_data(self) -> dict[str, Any]:
        """Initialise data - only called once during setup."""
        if not self.client.connected:
            try:
                await self.client.connect()
            except Exception as exc:
                raise UpdateFailed(f"Failed to connect: {exc}") from exc
        
        try:
            # Get device info for device setup
            if self._device_info is None:
                info_response = await asyncio.wait_for(
                    self.client.get_info(), timeout=10.0
                )
                if info_response and "data" in info_response:
                    self._setup_device_info(info_response["data"])
            
            # Get initial motor status to avoid "unknown" state on startup
            initial_status = {}
            try:
                status_response = await asyncio.wait_for(
                    self.client.get_status(), timeout=10.0
                )
                if status_response and "data" in status_response:
                    initial_status = status_response["data"]
            except Exception as exc:
                _LOGGER.warning("Failed to get initial status, will rely on events: %s", exc)
            
            return {
                "status": initial_status,
                "connection_state": self.client.state,
                "last_seen": self.client.last_seen,
            }
            
        except asyncio.TimeoutError as exc:
            raise UpdateFailed("Timeout getting device info") from exc
        except RenkeiConnectionError as exc:
            raise UpdateFailed(f"Connection error: {exc}") from exc
        except Exception as exc:
            raise UpdateFailed(f"Unexpected error: {exc}") from exc

    def _setup_device_info(self, device_data: dict[str, Any]) -> None:
        """Set up device info from motor controller data."""
        mac_address = device_data.get("mac", "").replace(":", "").lower()
        
        self._device_info = DeviceInfo(
            identifiers={(DOMAIN, mac_address)},
            name=_generate_device_name(mac_address),
            manufacturer=MANUFACTURER,
            model=MODEL,
            sw_version=device_data.get("firmware"),  # Use correct field name from API
        )

    def _handle_status_update(self, message: dict[str, Any]) -> None:
        """Handle real-time status updates from the motor."""
        if self._shutting_down:
            return
        event_type = message.get("event")
        response_type = message.get("response")
        data = message.get("data", {})
        full_status = (
            response_type == "GET_STATUS" or event_type == "MOTOR_STATUS"
        )
        motion = motor_motion(data.get("run_flags"))
        position_changed = False

        if event_type == "CURRENT_POS" and "percent" in data:
            position = (data.get("absolute"), data["percent"])
            position_changed = position != self._last_position_event
            if position_changed:
                self._last_position_event = position
                self._schedule_motion_status()
        elif response_type in {"MOVE", "A_MOVE", "STOP", "JOG", "F_MOVE"}:
            # An ACK does not prove execution or a stop. Also check commands
            # that produce no position change (for example a STOP at a limit).
            self._schedule_motion_status()

        if full_status or event_type == "CURRENT_POS":
            if motion == MotorMotion.STOPPED:
                self._cancel_motion_timer()
                self._motion_status_failures = 0
            elif motion is not None:
                self._schedule_motion_status()

        if not self.data:
            return

        # Install the snapshot before cover listeners calculate their state.
        updated = dict(self.data)
        status = dict(updated.get("status", {}))
        updated["status"] = status
        changed = False
        if event_type == "CURRENT_POS" and "percent" in data:
            # Repeated idle pushes must not replace a reconciled encoder
            # position with the same old, possibly truncated percentage.
            if position_changed or "current_pos_percent" in status:
                status["current_pos_percent"] = data["percent"]
            changed = True
        elif full_status and data:
            # Fresh encoder data supersedes the last push percentage, including
            # the rewrite's truncated 99% when an endpoint rounds to 100%.
            if "current_pos" in data:
                status.pop("current_pos_percent", None)
            if self.client.just_reconnected:
                self.client._just_reconnected = False
            status.update(data)
            status.pop("position_is_percentage", None)
            changed = True
        elif event_type == "ERROR" and "code" in data:
            status["err_flags"] = data["code"]
            changed = True

        if changed:
            updated["last_seen"] = self.client.last_seen
            self.data = updated

        for listener in self._status_listeners:
            try:
                listener(message)
            except Exception as exc:
                _LOGGER.error("Error in status listener: %s", exc)
        if changed:
            self.async_set_updated_data(updated)

    def _cancel_motion_timer(self) -> None:
        """Cancel a scheduled check without interrupting an on-wire query."""
        if self._motion_status_timer is not None:
            self._motion_status_timer.cancel()
            self._motion_status_timer = None

    def _schedule_motion_status(self, *, reset_failures: bool = True) -> None:
        """Check actual motion after position activity has settled."""
        if self._shutting_down or not self.available:
            return
        self._cancel_motion_timer()
        if reset_failures:
            self._motion_status_failures = 0
        self._motion_status_timer = asyncio.get_running_loop().call_later(
            MOTION_STATUS_DELAY, self._start_motion_status_check
        )

    def _start_motion_status_check(self) -> None:
        """Start at most one reconciliation query per motor."""
        self._motion_status_timer = None
        if self._shutting_down or not self.available:
            return
        if self._motion_status_task is None or self._motion_status_task.done():
            self._motion_status_task = asyncio.create_task(
                self._async_check_motion()
            )

    async def _async_check_motion(self) -> None:
        """Request authoritative status; failed queries never imply stopped."""
        try:
            response = await self.client.get_status()
            # The client delivers the response through _handle_status_update.
            # A newer push may already have arrived; do not reapply this reply.
            if (
                not response
                or motor_motion(response.get("data", {}).get("run_flags"))
                is None
            ):
                raise ValueError("GET_STATUS returned invalid motion flags")
        except Exception as exc:
            self._motion_status_failures += 1
            if self._motion_status_failures < MOTION_STATUS_MAX_FAILURES:
                self._schedule_motion_status(reset_failures=False)
            else:
                _LOGGER.warning("Unable to confirm motor motion: %s", exc)

    def _cancel_motion_check(self) -> asyncio.Task | None:
        """Cancel checks when their connection or coordinator is discarded."""
        self._cancel_motion_timer()
        task = self._motion_status_task
        self._motion_status_task = None
        if task is not None:
            task.cancel()
        self._last_position_event = None
        return task

    def _handle_connection_state(self, state: ConnectionState) -> None:
        """Handle connection state changes."""
        _LOGGER.debug("Connection state changed to: %s", state.value)
        if state != ConnectionState.CONNECTED:
            self._cancel_motion_check()
        
        # Update coordinator data with new connection state
        # async_set_updated_data() automatically notifies entities of availability changes
        if self.data:
            self.data["connection_state"] = state
        else:
            _LOGGER.debug("No coordinator data available for connection state update")
        
        # Notify all listeners
        for listener in self._connection_listeners:
            try:
                listener(state)
            except Exception as exc:
                _LOGGER.error("Error in connection listener: %s", exc)
        if self.data:
            self.async_set_updated_data(self.data)

    def add_status_listener(
        self, listener: Callable[[dict[str, Any]], None]
    ) -> None:
        """Add a status update listener."""
        self._status_listeners.append(listener)

    def remove_status_listener(
        self, listener: Callable[[dict[str, Any]], None]
    ) -> None:
        """Remove a status update listener."""
        if listener in self._status_listeners:
            self._status_listeners.remove(listener)

    def add_connection_listener(
        self, listener: Callable[[ConnectionState], None]
    ) -> None:
        """Add a connection state listener."""
        self._connection_listeners.append(listener)

    def remove_connection_listener(
        self, listener: Callable[[ConnectionState], None]
    ) -> None:
        """Remove a connection state listener."""
        if listener in self._connection_listeners:
            self._connection_listeners.remove(listener)

    @property
    def available(self) -> bool:
        """Return if coordinator is available (connected to motor)."""
        return self.client.state == ConnectionState.CONNECTED

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device info."""
        return self._device_info

    async def async_get_full_status(self) -> dict[str, Any] | None:
        """Get full status from motor - use sparingly, only for diagnostics."""
        try:
            status_response = await asyncio.wait_for(
                self.client.get_status(), timeout=10.0
            )
            
            if status_response and "data" in status_response:
                # Already applied in wire order by the status callback.
                return status_response["data"]
                
        except Exception as exc:
            _LOGGER.error("Failed to get full status: %s", exc)
            
        return None

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        self._shutting_down = True
        task = self._cancel_motion_check()
        if task is not None:
            with suppress(asyncio.CancelledError):
                await task
        await self.client.disconnect()
