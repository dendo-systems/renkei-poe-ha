"""Data update coordinator for RENKEI PoE Motor Control integration."""

from __future__ import annotations

import asyncio
import logging
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
    DOMAIN,
    MANUFACTURER,
    MODEL,
)
from .renkei_client import RenkeiClient, RenkeiConnectionError, ConnectionState

_LOGGER = logging.getLogger(__name__)


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
        self.config_entry = config_entry
        self.client = RenkeiClient(
            host=config_entry.data[CONF_HOST],
            port=config_entry.data[CONF_PORT],
            reconnect_interval=config_entry.data[CONF_RECONNECT_INTERVAL],
            health_check_interval=config_entry.data[CONF_HEALTH_CHECK_INTERVAL],
            connection_stabilise_delay=config_entry.data[CONF_CONNECTION_STABILISE_DELAY],
        )
        
        self._device_info: DeviceInfo | None = None
        self._status_listeners: list[callable] = []
        self._connection_listeners: list[callable] = []
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,  # Explicit: Use push events only, no polling
            always_update=False,
        )
        
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
        # Notify all listeners first
        for listener in self._status_listeners:
            try:
                listener(message)
            except Exception as exc:
                _LOGGER.error("Error in status listener: %s", exc)
        
        # Update coordinator data based on the message type
        if not self.data:
            return
            
        event_type = message.get("event")
        response_type = message.get("response")
        data = message.get("data", {})
        
        # Handle position updates from CURRENT_POS events
        if event_type == "CURRENT_POS" and "percent" in data:
            if "status" not in self.data:
                self.data["status"] = {}
            # Store percentage from CURRENT_POS events in separate field
            self.data["status"]["current_pos_percent"] = data["percent"]
            self.data["last_seen"] = self.client.last_seen
            self.async_set_updated_data(self.data)
            
        # Handle GET_STATUS responses (from health checks)
        elif response_type == "GET_STATUS" and data:
            if "status" not in self.data:
                self.data["status"] = {}
            
            # Only clear stale position cache if this is after a reconnection
            # During routine health checks, preserve more accurate real-time position data
            if self.client.just_reconnected:
                # Clear stale current_pos_percent to force sync with motor's actual position
                self.data["status"].pop("current_pos_percent", None)
                # Clear the reconnection flag after handling
                self.client._just_reconnected = False
            
            # Update status data from GET_STATUS response (keeps limit_pos fresh)
            self.data["status"].update(data)
            # Don't set position_is_percentage flag for GET_STATUS responses (encoder data)
            self.data["status"].pop("position_is_percentage", None)
            self.data["last_seen"] = self.client.last_seen
            self.async_set_updated_data(self.data)
            
        # Handle error events  
        elif event_type == "ERROR":
            # Update error flags if available
            if "code" in data:
                if "status" not in self.data:
                    self.data["status"] = {}
                self.data["status"]["err_flags"] = data["code"]
                self.data["last_seen"] = self.client.last_seen
                self.async_set_updated_data(self.data)

    def _handle_connection_state(self, state: ConnectionState) -> None:
        """Handle connection state changes."""
        _LOGGER.debug("Connection state changed to: %s", state.value)
        
        # Update coordinator data with new connection state
        # async_set_updated_data() automatically notifies entities of availability changes
        if self.data:
            self.data["connection_state"] = state
            self.async_set_updated_data(self.data)
        else:
            _LOGGER.debug("No coordinator data available for connection state update")
        
        # Notify all listeners
        for listener in self._connection_listeners:
            try:
                listener(state)
            except Exception as exc:
                _LOGGER.error("Error in connection listener: %s", exc)

    def add_status_listener(self, listener: callable) -> None:
        """Add a status update listener."""
        self._status_listeners.append(listener)

    def remove_status_listener(self, listener: callable) -> None:
        """Remove a status update listener."""
        if listener in self._status_listeners:
            self._status_listeners.remove(listener)

    def add_connection_listener(self, listener: callable) -> None:
        """Add a connection state listener."""
        self._connection_listeners.append(listener)

    def remove_connection_listener(self, listener: callable) -> None:
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
                # Update our cached data
                self.data["status"].update(status_response["data"])
                self.data["last_seen"] = self.client.last_seen
                self.async_set_updated_data(self.data)
                return status_response["data"]
                
        except Exception as exc:
            _LOGGER.error("Failed to get full status: %s", exc)
            
        return None

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        await self.client.disconnect()