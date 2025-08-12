"""The RENKEI PoE Motor Control integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.components import repairs
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
from homeassistant.helpers.translation import async_get_translations
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from .const import (
    DOMAIN,
    PLATFORMS,
    SERVICE_JOG,
    SERVICE_JOG_SCHEMA,
    SERVICE_SET_POSITION,
    SERVICE_SET_POSITION_SCHEMA,
    SERVICE_ABSOLUTE_MOVE,
    SERVICE_ABSOLUTE_MOVE_SCHEMA,
    SERVICE_GET_STATUS,
    SERVICE_GET_STATUS_SCHEMA,
    SERVICE_GET_INFO,
    SERVICE_GET_INFO_SCHEMA,
)
from .coordinator import RenkeiCoordinator
from .renkei_client import RenkeiConnectionError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up RENKEI PoE Motor Control from a config entry."""
    
    coordinator = RenkeiCoordinator(hass, entry)
    
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        raise
    except Exception as exc:
        raise ConfigEntryNotReady(f"Failed to setup RENKEI PoE Motor: {exc}") from exc
    
    # Store coordinator in config entry runtime data
    entry.runtime_data = coordinator
    
    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register services
    await _async_register_services(hass, coordinator)
    
    # Repair flows are handled by the repairs module when issues are created
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    
    # Unload platforms
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: RenkeiCoordinator = entry.runtime_data
        await coordinator.async_shutdown()
        
        # Check if any other RENKEI PoE entries exist before removing services
        other_entries = [
            e for e in hass.config_entries.async_entries(DOMAIN) 
            if e.entry_id != entry.entry_id and e.state.recoverable
        ]
        if not other_entries:
            hass.services.async_remove(DOMAIN, SERVICE_JOG)
            hass.services.async_remove(DOMAIN, SERVICE_SET_POSITION)
            hass.services.async_remove(DOMAIN, SERVICE_ABSOLUTE_MOVE)
            hass.services.async_remove(DOMAIN, SERVICE_GET_STATUS)
            hass.services.async_remove(DOMAIN, SERVICE_GET_INFO)
    
    return unload_ok


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
            "failed_to_jog_motor": "Failed to jog motor: {error}",
            "failed_to_set_position": "Failed to set position: {error}",
            "failed_to_move_to_absolute_position": "Failed to move to absolute position: {error}",
            "failed_to_get_motor_status": "Failed to get motor status",
            "failed_to_get_status": "Failed to get status: {error}",
            "failed_to_get_motor_info": "Failed to get motor info",
            "failed_to_get_info": "Failed to get info: {error}",
            "position_required": "Position is required",
            "failed_to_stop_motor": "Failed to stop motor: {error}",
            "unexpected_error": "Unexpected error: {error}",
            "position_out_of_range": "Position {position} is out of range ({min_position}-{max_position})",
            "failed_to_move_motor": "Failed to move motor: {error}"
        }
        message_template = fallback_messages.get(key, key)
        return message_template.format(**kwargs)


async def _async_register_services(hass: HomeAssistant, coordinator: RenkeiCoordinator) -> None:
    """Register integration services."""
    
    async def async_jog_motor(call: ServiceCall) -> None:
        """Service to jog the motor for identification."""
        count = call.data.get("count", 1)
        
        try:
            await coordinator.client.jog(count=count)
        except Exception as exc:
            message = await _get_translated_exception(hass, "failed_to_jog_motor", error=str(exc))
            raise ServiceValidationError(message) from exc
    
    async def async_set_position(call: ServiceCall) -> None:
        """Service to set motor position with optional delay."""
        position = call.data["position"]
        delay = call.data.get("delay", 0)
        
        try:
            await coordinator.client.move(position=position, delay=delay)
        except Exception as exc:
            message = await _get_translated_exception(hass, "failed_to_set_position", error=str(exc))
            raise ServiceValidationError(message) from exc
    
    async def async_absolute_move(call: ServiceCall) -> None:
        """Service to move motor to absolute position (encoder value)."""
        position = call.data["position"]
        delay = call.data.get("delay", 0)
        
        try:
            await coordinator.client.absolute_move(position=position, delay=delay)
        except Exception as exc:
            message = await _get_translated_exception(hass, "failed_to_move_to_absolute_position", error=str(exc))
            raise ServiceValidationError(message) from exc
    
    async def async_get_status(call: ServiceCall) -> None:
        """Service to get full motor status for diagnostics."""
        try:
            status = await coordinator.async_get_full_status()
            if status:
                _LOGGER.info("Full motor status: %s", status)
            else:
                message = await _get_translated_exception(hass, "failed_to_get_motor_status")
                raise ServiceValidationError(message)
        except Exception as exc:
            message = await _get_translated_exception(hass, "failed_to_get_status", error=str(exc))
            raise ServiceValidationError(message) from exc
    
    async def async_get_info(call: ServiceCall) -> None:
        """Service to get network info for diagnostics."""
        try:
            info = await coordinator.client.get_info()
            if info:
                _LOGGER.info("Motor network info: %s", info)
            else:
                message = await _get_translated_exception(hass, "failed_to_get_motor_info")
                raise ServiceValidationError(message)
        except Exception as exc:
            message = await _get_translated_exception(hass, "failed_to_get_info", error=str(exc))
            raise ServiceValidationError(message) from exc
    
    # Register services (only register once globally)
    if not hass.services.has_service(DOMAIN, SERVICE_JOG):
        hass.services.async_register(
            DOMAIN,
            SERVICE_JOG,
            async_jog_motor,
            schema=vol.Schema(SERVICE_JOG_SCHEMA),
        )
    
    if not hass.services.has_service(DOMAIN, SERVICE_SET_POSITION):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_POSITION,
            async_set_position,
            schema=vol.Schema(SERVICE_SET_POSITION_SCHEMA),
        )
    
    if not hass.services.has_service(DOMAIN, SERVICE_ABSOLUTE_MOVE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_ABSOLUTE_MOVE,
            async_absolute_move,
            schema=vol.Schema(SERVICE_ABSOLUTE_MOVE_SCHEMA),
        )
        
    if not hass.services.has_service(DOMAIN, SERVICE_GET_STATUS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_GET_STATUS,
            async_get_status,
            schema=vol.Schema(SERVICE_GET_STATUS_SCHEMA),
        )
    
    if not hass.services.has_service(DOMAIN, SERVICE_GET_INFO):
        hass.services.async_register(
            DOMAIN,
            SERVICE_GET_INFO,
            async_get_info,
            schema=vol.Schema(SERVICE_GET_INFO_SCHEMA),
        )


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating configuration from version %s.%s", 
                  config_entry.version, config_entry.minor_version)
    
    if config_entry.version > 1:
        # This means the user has a newer version of the integration
        # than this version supports, so we cannot migrate
        return False
    
    # No migrations needed for version 1
    return True


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> repairs.RepairsFlow:
    """Create a repair flow for issues."""
    from .repairs import async_create_fix_flow as repair_flow_handler
    return await repair_flow_handler(hass, issue_id, data)