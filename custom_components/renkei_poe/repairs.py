"""Repairs for RENKEI PoE Motor Control integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_create_issue_deprecated_port_80(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Create a repair issue for deprecated port 80 configuration."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"deprecated_port_80_{entry.entry_id}",
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_port_80",
        translation_placeholders={
            "entry_title": entry.title,
            "current_port": str(entry.data.get("port", "unknown")),
        },
    )



async def async_create_issue_connection_unstable(
    hass: HomeAssistant,
    entry: ConfigEntry,
    reconnect_count: int,
) -> None:
    """Create a repair issue for unstable connection."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"connection_unstable_{entry.entry_id}",
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="connection_unstable",
        translation_placeholders={
            "entry_title": entry.title,
            "reconnect_count": str(reconnect_count),
        },
    )


async def async_create_issue_motor_error(
    hass: HomeAssistant,
    entry: ConfigEntry,
    error_code: str,
    error_description: str,
) -> None:
    """Create a repair issue for persistent motor errors."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"motor_error_{error_code}_{entry.entry_id}",
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="motor_error",
        translation_placeholders={
            "entry_title": entry.title,
            "error_code": error_code,
            "error_description": error_description,
        },
    )


def async_remove_issue(
    hass: HomeAssistant,
    entry: ConfigEntry,
    issue_id: str,
) -> None:
    """Remove a repair issue."""
    ir.async_delete_issue(hass, DOMAIN, f"{issue_id}_{entry.entry_id}")


class DeprecatedPort80RepairFlow(RepairsFlow):
    """Handler for deprecated port 80 repair flow."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialise the repair flow."""
        self._entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Handle the initial step."""
        if user_input is not None:
            # Update the config entry to use correct port
            new_data = {**self._entry.data}
            new_data["port"] = 17002
            
            self.hass.config_entries.async_update_entry(
                self._entry, data=new_data
            )
            
            # Remove the repair issue
            ir.async_delete_issue(
                self.hass, DOMAIN, f"deprecated_port_80_{self._entry.entry_id}"
            )
            
            return self.async_create_form(step_id="confirm")

        return self.async_show_form(
            step_id="init",
            description_placeholders={
                "entry_title": self._entry.title,
                "current_port": str(self._entry.data.get("port", "unknown")),
            },
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Handle the confirmation step."""
        return self.async_create_form(step_id="confirm")


class ConnectionUnstableRepairFlow(RepairsFlow):
    """Handler for unstable connection repair flow."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialise the repair flow."""
        self._entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Handle the initial step."""
        if user_input is not None:
            # Update config with more conservative connection settings
            new_data = {**self._entry.data}
            new_data["reconnect_interval"] = max(
                new_data.get("reconnect_interval", 10), 30
            )
            new_data["health_check_interval"] = 60
            new_data["connection_stabilise_delay"] = 2.0
            
            self.hass.config_entries.async_update_entry(
                self._entry, data=new_data
            )
            
            # Remove the repair issue
            ir.async_delete_issue(
                self.hass, DOMAIN, f"connection_unstable_{self._entry.entry_id}"
            )
            
            return self.async_create_form(step_id="confirm")

        return self.async_show_form(
            step_id="init",
            description_placeholders={
                "entry_title": self._entry.title,
            },
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Handle the confirmation step."""
        return self.async_create_form(step_id="confirm")


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create a fix flow for repair issues."""
    entry_id = issue_id.split("_")[-1]
    entry = hass.config_entries.async_get_entry(entry_id)
    
    if entry is None:
        raise ValueError(f"Config entry {entry_id} not found")
    
    if issue_id.startswith("deprecated_port_80"):
        return DeprecatedPort80RepairFlow(entry)
    elif issue_id.startswith("connection_unstable"):
        return ConnectionUnstableRepairFlow(entry)
    
    raise ValueError(f"Unknown repair issue: {issue_id}")