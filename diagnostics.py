"""Diagnostics support for RENKEI PoE Motor Control."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .coordinator import RenkeiCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: RenkeiCoordinator = config_entry.runtime_data
    
    # Try to get current motor status first for comparison
    current_motor_status = None
    try:
        if coordinator.client.connected:
            status_response = await asyncio.wait_for(
                coordinator.client.get_status(), timeout=5.0
            )
            if status_response and "data" in status_response:
                current_motor_status = status_response["data"]
    except Exception as exc:
        _LOGGER.debug("Failed to get current motor status for diagnostics: %s", exc)
        current_motor_status = {"error": str(exc)}
    
    # Try to get current network info
    network_info = None
    try:
        if coordinator.client.connected:
            info_response = await asyncio.wait_for(
                coordinator.client.get_info(), timeout=5.0
            )
            if info_response and "data" in info_response:
                network_info = info_response["data"]
    except Exception as exc:
        _LOGGER.debug("Failed to get network info for diagnostics: %s", exc)
        network_info = {"error": str(exc)}

    diagnostics_data = {
        "config_entry": {
            "title": config_entry.title,
            "unique_id": config_entry.unique_id,
            "version": config_entry.version,
            "minor_version": config_entry.minor_version,
            "domain": config_entry.domain,
            "data": _redact_sensitive_data(config_entry.data),
            "options": config_entry.options,
            "disabled_by": config_entry.disabled_by,
            "source": config_entry.source,
        },
        "current_motor_status": current_motor_status,
        "network_info": network_info,
        "client_info": {
            "connection_state": coordinator.client.state.value,
            "last_seen": coordinator.client.last_seen.isoformat() if coordinator.client.last_seen else None,
        },
        "device_info": coordinator.device_info,
    }
    
    return diagnostics_data


def _redact_sensitive_data(data: dict[str, Any]) -> dict[str, Any]:
    """Redact sensitive information from config data."""
    redacted = data.copy()
    
    # Redact potentially sensitive fields
    sensitive_keys = ["password", "token", "api_key", "secret"]
    
    for key in redacted:
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            redacted[key] = "**REDACTED**"
    
    return redacted