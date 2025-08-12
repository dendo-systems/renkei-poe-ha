"""Cover platform for RENKEI PoE Motor Control."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.translation import async_get_translations
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import RenkeiCoordinator
from .const import (
    DOMAIN,
    ERROR_CODES,
    MAX_POSITION,
    MIN_POSITION,
)
from .renkei_client import RenkeiConnectionError

_LOGGER = logging.getLogger(__name__)


async def _get_translated_exception(hass: HomeAssistant, key: str, **kwargs) -> str:
    """Get translated exception message."""
    try:
        translations = await async_get_translations(hass, hass.config.language, "exceptions", {DOMAIN})
        domain_translations = translations.get(DOMAIN, {}).get("exceptions", {})
        message_template = domain_translations.get(key, key)
        return message_template.format(**kwargs)
    except Exception:
        # Fallback to English/key if translation fails
        fallback_messages = {
            "position_required": "Position is required",
            "failed_to_stop_motor": "Failed to stop motor: {error}",
            "unexpected_error": "Unexpected error: {error}",
            "position_out_of_range": "Position {position} is out of range ({min_position}-{max_position})",
            "failed_to_move_motor": "Failed to move motor: {error}"
        }
        message_template = fallback_messages.get(key, key)
        return message_template.format(**kwargs)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the RENKEI PoE Motor cover platform."""
    coordinator: RenkeiCoordinator = config_entry.runtime_data
    
    # Create cover entity
    async_add_entities([RenkeiCover(coordinator)])


class RenkeiCover(CoordinatorEntity[RenkeiCoordinator], CoverEntity):
    """Representation of a RENKEI PoE Motor cover."""

    _attr_has_entity_name = True
    _attr_translation_key = "shade"
    _attr_device_class = CoverDeviceClass.SHADE
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )
    
    # Limit parallel updates since motor can only handle one command at a time
    parallel_updates = 1

    def __init__(self, coordinator: RenkeiCoordinator) -> None:
        """Initialise the cover."""
        super().__init__(coordinator)
        
        self._hass = coordinator.hass
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_cover"
        self._attr_device_info = coordinator.device_info
        
        # Track movement state
        self._is_opening = False
        self._is_closing = False
        self._last_position: int | None = None
        self._position_stable_count = 0
        
        # Track diagnostic data
        self._absolute_position: int | None = None
        self._current_error: dict[str, Any] | None = None
        
        # Register for real-time updates
        coordinator.add_status_listener(self._handle_status_update)

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when entity is removed."""
        self.coordinator.remove_status_listener(self._handle_status_update)
        await super().async_will_remove_from_hass()

    @callback
    def _handle_status_update(self, message: dict[str, Any]) -> None:
        """Handle real-time status updates from motor."""
        event_type = message.get("event")
        data = message.get("data", {})
        
        if event_type == "CURRENT_POS":
            # Real-time position update from CURRENT_POS event
            if "percent" in data:
                new_position = int(data["percent"])
                
                # Capture absolute position if available
                if "absolute" in data:
                    # Convert hex string to integer if needed
                    absolute_raw = data["absolute"]
                    if isinstance(absolute_raw, str):
                        try:
                            self._absolute_position = int(absolute_raw, 16)  # Hex to int
                        except ValueError:
                            self._absolute_position = absolute_raw
                    else:
                        self._absolute_position = absolute_raw
                
                # Update coordinator data with new position (coordinator already handles this)
                # Note: coordinator stores this as current_pos_percent, no need to duplicate
                
                # Detect movement based on position changes
                if self._last_position is not None:
                    if new_position > self._last_position:
                        # Position increasing - opening
                        self._is_opening = True
                        self._is_closing = False
                        self._position_stable_count = 0
                    elif new_position < self._last_position:
                        # Position decreasing - closing
                        self._is_opening = False
                        self._is_closing = True
                        self._position_stable_count = 0
                    else:
                        # Position unchanged - check if we should stop
                        self._position_stable_count += 1
                        if self._position_stable_count >= 2:
                            # Position stable for 2+ updates - not moving
                            self._is_opening = False
                            self._is_closing = False
                
                self._last_position = new_position
                self.async_write_ha_state()
        
        elif event_type == "ERROR" or message.get("response") == "ERROR":
            # Handle motor errors (both ERROR events and ERROR command responses)
            error_code = data.get("code", "unknown")
            error_desc = ERROR_CODES.get(str(error_code), "Unknown error")
            _LOGGER.error("Motor error %s: %s", error_code, error_desc)
            
            # Store error information for display in attributes
            self._current_error = {
                "code": error_code,
                "description": error_desc,
                "timestamp": datetime.now().isoformat()
            }
            
            # Clear movement states on error
            self._is_opening = False
            self._is_closing = False
            
            self.async_write_ha_state()


    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.available

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover."""
        if not self.coordinator.data:
            return None
        
        status = self.coordinator.data.get("status", {})
        
        # Priority-based position calculation
        current_pos_percent = status.get("current_pos_percent")
        current_pos = status.get("current_pos") 
        limit_pos = status.get("limit_pos")
        
        # Priority 1: Use percentage from CURRENT_POS events (most accurate)
        if current_pos_percent is not None:
            position = round(current_pos_percent)
        # Priority 2: Calculate from encoder values (GET_STATUS response)
        elif current_pos is not None and limit_pos is not None and limit_pos > 0:
            position = round((current_pos / limit_pos) * 100)
        # Priority 3: Use current_pos directly (backward compatibility)
        elif current_pos is not None:
            position = round(current_pos)
        else:
            return None
            
        return max(MIN_POSITION, min(MAX_POSITION, position))

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing."""
        return self._is_closing

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening."""
        return self._is_opening

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed."""
        position = self.current_cover_position
        return position is not None and position <= MIN_POSITION


    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return {}
        
        status = self.coordinator.data.get("status", {})
        connection_state = self.coordinator.data.get("connection_state")
        last_seen = self.coordinator.data.get("last_seen")
        
        attrs = {}
        
        # Connection diagnostics
        if last_seen:
            attrs["last_seen"] = last_seen
        
        # Motor diagnostics (for troubleshooting)
        absolute_pos = self._absolute_position  # From CURRENT_POS events if available
        if absolute_pos is None:
            # Fallback to current_pos from GET_STATUS (absolute position due to firmware quirk)
            absolute_pos = status.get("current_pos")
        if absolute_pos is not None:
            attrs["absolute_position"] = absolute_pos
        
        # Add current error information if available (diagnostic)
        if self._current_error:
            attrs["error"] = self._current_error["description"]
            attrs["error_code"] = self._current_error["code"]
            attrs["error_time"] = self._current_error["timestamp"]
        
        return attrs

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._async_set_position(MAX_POSITION)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._async_set_position(MIN_POSITION)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs.get(ATTR_POSITION)
        if position is None:
            message = await _get_translated_exception(self._hass, "position_required")
            raise ServiceValidationError(message)
        
        await self._async_set_position(position)

    
    async def _validate_position(self, position: int) -> None:
        """Validate position is within bounds."""
        if not MIN_POSITION <= position <= MAX_POSITION:
            message = await _get_translated_exception(
                self._hass, 
                "position_out_of_range", 
                position=position, 
                min_position=MIN_POSITION, 
                max_position=MAX_POSITION
            )
            raise ServiceValidationError(message)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        try:
            await self.coordinator.client.stop()
            
            # Clear any previous errors on successful command
            self._current_error = None
            
            _LOGGER.debug("Stop command sent successfully")
        except RenkeiConnectionError as exc:
            message = await _get_translated_exception(self._hass, "failed_to_stop_motor", error=str(exc))
            raise ServiceValidationError(message) from exc
        except Exception as exc:
            _LOGGER.error("Unexpected error stopping motor: %s", exc)
            message = await _get_translated_exception(self._hass, "unexpected_error", error=str(exc))
            raise ServiceValidationError(message) from exc

    async def _async_set_position(self, position: int) -> None:
        """Set cover position."""
        # Validate position
        await self._validate_position(position)
        
        try:
            # Send move command
            response = await self.coordinator.client.move(position=position)
            
            # Clear any previous errors on successful command
            self._current_error = None
            
            _LOGGER.debug("Move command sent successfully to position %s", position)
            
            # Position will be updated via CURRENT_POS events
            
        except RenkeiConnectionError as exc:
            message = await _get_translated_exception(self._hass, "failed_to_move_motor", error=str(exc))
            raise ServiceValidationError(message) from exc
        except Exception as exc:
            _LOGGER.error("Unexpected error moving motor: %s", exc)
            message = await _get_translated_exception(self._hass, "unexpected_error", error=str(exc))
            raise ServiceValidationError(message) from exc