"""Test the RENKEI PoE Motor Control config flow."""

import asyncio
from unittest.mock import AsyncMock, patch
import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.renkei_poe.config_flow import ConfigFlow
from custom_components.renkei_poe.const import DOMAIN, DEFAULT_PORT
from custom_components.renkei_poe.renkei_client import RenkeiConnectionError


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}


async def test_user_connection_error(hass: HomeAssistant, mock_renkei_client) -> None:
    """Test connection error handling."""
    mock_renkei_client.connect.side_effect = RenkeiConnectionError("Connection failed")
    
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_PORT: DEFAULT_PORT,
            CONF_NAME: "Test Motor",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_user_timeout_error(hass: HomeAssistant, mock_renkei_client) -> None:
    """Test timeout error handling."""
    mock_renkei_client.connect.side_effect = asyncio.TimeoutError()
    
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_PORT: DEFAULT_PORT,
            CONF_NAME: "Test Motor",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "timeout"}


async def test_user_invalid_host(hass: HomeAssistant) -> None:
    """Test invalid host error handling."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "invalid-host",
            CONF_PORT: DEFAULT_PORT,
            CONF_NAME: "Test Motor",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_host"}


async def test_user_success(hass: HomeAssistant, mock_renkei_client) -> None:
    """Test successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_PORT: DEFAULT_PORT,
            CONF_NAME: "Test Motor",
        },
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Test Motor"
    assert result2["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: DEFAULT_PORT,
        CONF_NAME: "Test Motor",
    }


async def test_user_success_no_name(hass: HomeAssistant, mock_renkei_client) -> None:
    """Test successful user flow without custom name."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_PORT: DEFAULT_PORT,
        },
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "RENKEI PoE Motor (192.168.1.100)"


async def test_duplicate_device(hass: HomeAssistant, mock_renkei_client) -> None:
    """Test duplicate device handling."""
    # First entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_PORT: DEFAULT_PORT,
            CONF_NAME: "Test Motor",
        },
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY

    # Try to add the same device again
    result3 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        {
            CONF_HOST: "192.168.1.100",  # Same IP/device
            CONF_PORT: DEFAULT_PORT,
            CONF_NAME: "Test Motor 2",
        },
    )

    # Should be aborted due to duplicate unique_id
    assert result4["type"] == FlowResultType.ABORT
    assert result4["reason"] == "already_configured"


async def test_zeroconf_discovery(hass: HomeAssistant, mock_renkei_client) -> None:
    """Test zeroconf discovery flow."""
    from homeassistant.components.zeroconf import ZeroconfServiceInfo
    
    discovery_info = ZeroconfServiceInfo(
        host="192.168.1.100",
        port=17002,
        hostname="RENKEI-A0B76531115B.local.",
        type="_dendo._tcp.local.",
        name="RENKEI-A0B76531115B._dendo._tcp.local.",
        properties={}
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, 
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info
    )

    # Should proceed to discovery confirmation form
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"


async def test_zeroconf_wrong_device(hass: HomeAssistant) -> None:
    """Test zeroconf discovery with wrong device type."""
    from homeassistant.components.zeroconf import ZeroconfServiceInfo
    
    discovery_info = ZeroconfServiceInfo(
        host="192.168.1.100",
        port=80,
        hostname="OTHER-DEVICE.local.",
        type="_http._tcp.local.",
        name="OTHER-DEVICE._http._tcp.local.",
        properties={}
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, 
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info
    )

    # Should abort for non-RENKEI device
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "not_renkei_device"


async def test_options_flow(hass: HomeAssistant, mock_config_entry) -> None:
    """Test options flow."""
    mock_config_entry.add_to_hass(hass)
    
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    
    # Test configuring options
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "reconnect_interval": 30,
            "health_check_interval": 60,
            "connection_stabilise_delay": 1.0,
        },
    )
    
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"]["reconnect_interval"] == 30
    assert result2["data"]["health_check_interval"] == 60
    assert result2["data"]["connection_stabilise_delay"] == 1.0