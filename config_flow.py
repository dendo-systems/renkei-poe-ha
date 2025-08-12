"""Config flow for RENKEI PoE Motor Control integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.util.network import is_ip_address

from .const import (
    CONF_CONNECTION_STABILISE_DELAY,
    CONF_HEALTH_CHECK_INTERVAL,
    CONF_RECONNECT_INTERVAL,
    DEFAULT_CONNECTION_STABILISE_DELAY,
    DEFAULT_HEALTH_CHECK_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_RECONNECT_INTERVAL,
    DOMAIN,
    HOSTNAME_PREFIX,
)
from .renkei_client import RenkeiClient, RenkeiConnectionError

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

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)

STEP_DISCOVERY_DATA_SCHEMA = vol.Schema({})

STEP_RECONFIGURE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    
    if not is_ip_address(data[CONF_HOST]):
        raise ValueError("Invalid IP address format")
    
    # Add default constants for advanced options not exposed to user
    enhanced_data = {
        **data,
        CONF_PORT: DEFAULT_PORT,
        CONF_RECONNECT_INTERVAL: DEFAULT_RECONNECT_INTERVAL,
        CONF_HEALTH_CHECK_INTERVAL: DEFAULT_HEALTH_CHECK_INTERVAL,
        CONF_CONNECTION_STABILISE_DELAY: DEFAULT_CONNECTION_STABILISE_DELAY,
    }
    
    client = RenkeiClient(
        host=enhanced_data[CONF_HOST],
        port=enhanced_data[CONF_PORT],
        reconnect_interval=enhanced_data[CONF_RECONNECT_INTERVAL],
        health_check_interval=enhanced_data[CONF_HEALTH_CHECK_INTERVAL],
        connection_stabilise_delay=enhanced_data[CONF_CONNECTION_STABILISE_DELAY],
    )
    
    try:
        # Test connection
        if not await client.connect():
            raise RenkeiConnectionError("Failed to connect")
        
        # Get device info for unique ID
        info = await asyncio.wait_for(client.get_info(), timeout=10.0)
        if not info or "data" not in info:
            raise RenkeiConnectionError("Failed to get device information")
        
        device_info = info["data"]
        mac_address = device_info.get("mac", "").replace(":", "").lower()
        
        if not mac_address:
            raise RenkeiConnectionError("Could not determine device MAC address")
        
        # Get current status to verify motor functionality
        status = await asyncio.wait_for(client.get_status(), timeout=10.0)
        if not status:
            raise RenkeiConnectionError("Failed to get motor status")
            
        await client.disconnect()
        
        return {
            "title": _generate_device_name(mac_address),
            "unique_id": mac_address,
            "device_info": device_info,
            "enhanced_data": enhanced_data,  # Return enhanced data with all settings
        }
        
    except asyncio.TimeoutError as exc:
        await client.disconnect()
        raise RenkeiConnectionError("Connection timeout") from exc
    except Exception as exc:
        await client.disconnect()
        if isinstance(exc, RenkeiConnectionError):
            raise
        raise RenkeiConnectionError(f"Unexpected error: {exc}") from exc


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RENKEI PoE Motor Control."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise the config flow."""
        self.discovery_info: dict[str, Any] = {}


    @staticmethod
    @callback
    def async_get_reconfigure_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ConfigFlow:
        """Return a reconfigure flow."""
        return ConfigFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except ValueError:
            errors["base"] = "invalid_host"
        except asyncio.TimeoutError:
            errors["base"] = "timeout"
        except RenkeiConnectionError:
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(info["unique_id"])
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(
                title=info["title"],
                data=info["enhanced_data"],  # Use enhanced data with all settings
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        host = discovery_info.host
        port = discovery_info.port or DEFAULT_PORT
        hostname = discovery_info.hostname
        
        # Only handle RENKEI PoE devices
        if not hostname.upper().startswith(HOSTNAME_PREFIX):
            return self.async_abort(reason="not_renkei_device")

        # Try to connect and get unique ID
        try:
            validation_data = {
                CONF_HOST: host,
            }
            
            info = await validate_input(self.hass, validation_data)
            
        except Exception as exc:  # pylint: disable=broad-except
            _LOGGER.debug("Failed to validate discovered device %s: %s", host, exc)
            return self.async_abort(reason="cannot_connect")
            
        await self.async_set_unique_id(info["unique_id"])
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        
        # Store discovery info for confirmation step
        self.discovery_info = info["enhanced_data"].copy()
        
        self.context["title_placeholders"] = {"name": info["title"]}
        
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        if user_input is None:
            return self.async_show_form(
                step_id="discovery_confirm",
                data_schema=STEP_DISCOVERY_DATA_SCHEMA,
                description_placeholders={"name": self.context["title_placeholders"]["name"]},
            )

        # Generate title using MAC-based naming
        # Get MAC from host to generate name
        try:
            validation_data = {CONF_HOST: self.discovery_info[CONF_HOST]}
            info = await validate_input(self.hass, validation_data)
            title = info["title"]
        except Exception:
            # Fallback to host-based naming if validation fails
            title = f"RENKEI PoE Motor ({self.discovery_info[CONF_HOST]})"
        
        return self.async_create_entry(
            title=title,
            data=self.discovery_info,
        )


    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reconfiguration."""
        config_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        
        if user_input is None:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=self.add_suggested_values_to_schema(
                    STEP_RECONFIGURE_DATA_SCHEMA, config_entry.data
                ),
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except ValueError:
            errors["base"] = "invalid_host"
        except asyncio.TimeoutError:
            errors["base"] = "timeout"
        except RenkeiConnectionError:
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception during reconfigure")
            errors["base"] = "unknown"
        else:
            # Check if unique ID changed (different device)
            if info["unique_id"] != config_entry.unique_id:
                errors["base"] = "wrong_device"
            else:
                return self.async_update_reload_and_abort(
                    config_entry,
                    data=info["enhanced_data"],  # Use enhanced data with all settings
                    title=info["title"],
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_RECONFIGURE_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )


