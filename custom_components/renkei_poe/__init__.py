"""The RENKEI PoE Motor Control integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.components import repairs
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import service
from homeassistant.helpers.typing import ConfigType

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

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the RENKEI PoE Motor Control integration."""
    await _async_register_services(hass)
    return True


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
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    
    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    
    # Unload platforms
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: RenkeiCoordinator = entry.runtime_data
        await coordinator.async_shutdown()
    
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register integration services."""

    async def async_jog_motor(entity: Any, call: ServiceCall) -> None:
        """Service to jog the motor for identification."""
        await entity.async_jog_motor(count=call.data.get("count", 1))

    async def async_set_position(entity: Any, call: ServiceCall) -> None:
        """Service to set motor position with optional delay."""
        await entity.async_set_motor_position(
            position=call.data["position"],
            delay=call.data.get("delay", 0),
        )

    async def async_absolute_move(entity: Any, call: ServiceCall) -> None:
        """Service to move motor to absolute position (encoder value)."""
        await entity.async_absolute_move(
            position=call.data["position"],
            delay=call.data.get("delay", 0),
        )

    async def async_get_status(entity: Any, call: ServiceCall) -> None:
        """Service to get full motor status for diagnostics."""
        await entity.async_get_motor_status()

    async def async_get_info(entity: Any, call: ServiceCall) -> None:
        """Service to get network info for diagnostics."""
        await entity.async_get_motor_info()

    if not hass.services.has_service(DOMAIN, SERVICE_JOG):
        service.async_register_platform_entity_service(
            hass,
            DOMAIN,
            SERVICE_JOG,
            entity_domain=COVER_DOMAIN,
            schema=SERVICE_JOG_SCHEMA,
            func=async_jog_motor,
        )
    
    if not hass.services.has_service(DOMAIN, SERVICE_SET_POSITION):
        service.async_register_platform_entity_service(
            hass,
            DOMAIN,
            SERVICE_SET_POSITION,
            entity_domain=COVER_DOMAIN,
            schema=SERVICE_SET_POSITION_SCHEMA,
            func=async_set_position,
        )
    
    if not hass.services.has_service(DOMAIN, SERVICE_ABSOLUTE_MOVE):
        service.async_register_platform_entity_service(
            hass,
            DOMAIN,
            SERVICE_ABSOLUTE_MOVE,
            entity_domain=COVER_DOMAIN,
            schema=SERVICE_ABSOLUTE_MOVE_SCHEMA,
            func=async_absolute_move,
        )
        
    if not hass.services.has_service(DOMAIN, SERVICE_GET_STATUS):
        service.async_register_platform_entity_service(
            hass,
            DOMAIN,
            SERVICE_GET_STATUS,
            entity_domain=COVER_DOMAIN,
            schema=SERVICE_GET_STATUS_SCHEMA,
            func=async_get_status,
        )
    
    if not hass.services.has_service(DOMAIN, SERVICE_GET_INFO):
        service.async_register_platform_entity_service(
            hass,
            DOMAIN,
            SERVICE_GET_INFO,
            entity_domain=COVER_DOMAIN,
            schema=SERVICE_GET_INFO_SCHEMA,
            func=async_get_info,
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
