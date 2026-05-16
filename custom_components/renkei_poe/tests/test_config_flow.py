"""Test the RENKEI PoE Motor Control config flow."""

import asyncio

from homeassistant import config_entries
from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.renkei_poe.const import (
    CONF_CONNECTION_STABILISE_DELAY,
    CONF_HEALTH_CHECK_INTERVAL,
    CONF_RECONNECT_INTERVAL,
    DEFAULT_CONNECTION_STABILISE_DELAY,
    DEFAULT_HEALTH_CHECK_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_RECONNECT_INTERVAL,
    DOMAIN,
)
from custom_components.renkei_poe.renkei_client import RenkeiConnectionError


EXPECTED_DATA = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: DEFAULT_PORT,
    CONF_RECONNECT_INTERVAL: DEFAULT_RECONNECT_INTERVAL,
    CONF_HEALTH_CHECK_INTERVAL: DEFAULT_HEALTH_CHECK_INTERVAL,
    CONF_CONNECTION_STABILISE_DELAY: DEFAULT_CONNECTION_STABILISE_DELAY,
}


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
        {CONF_HOST: "192.168.1.100"},
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_user_timeout_error(hass: HomeAssistant, mock_renkei_client) -> None:
    """Test timeout error handling."""
    mock_renkei_client.get_info.side_effect = asyncio.TimeoutError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.100"},
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
        {CONF_HOST: "invalid-host"},
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
        {CONF_HOST: "192.168.1.100"},
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "RENKEI PoE 31115B"
    assert result2["data"] == EXPECTED_DATA


async def test_duplicate_device(hass: HomeAssistant, mock_renkei_client) -> None:
    """Test duplicate device handling."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.100"},
    )
    assert result2["type"] == FlowResultType.CREATE_ENTRY

    result3 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        {CONF_HOST: "192.168.1.100"},
    )

    assert result4["type"] == FlowResultType.ABORT
    assert result4["reason"] == "already_configured"


async def test_zeroconf_discovery(hass: HomeAssistant, mock_renkei_client) -> None:
    """Test zeroconf discovery flow."""
    discovery_info = ZeroconfServiceInfo(
        host="192.168.1.100",
        port=17002,
        hostname="RENKEI-A0B76531115B.local.",
        type="_dendo._tcp.local.",
        name="RENKEI-A0B76531115B._dendo._tcp.local.",
        properties={},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"


async def test_zeroconf_wrong_device(hass: HomeAssistant) -> None:
    """Test zeroconf discovery with wrong device type."""
    discovery_info = ZeroconfServiceInfo(
        host="192.168.1.100",
        port=80,
        hostname="OTHER-DEVICE.local.",
        type="_http._tcp.local.",
        name="OTHER-DEVICE._http._tcp.local.",
        properties={},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "not_renkei_device"


async def test_options_flow(hass: HomeAssistant, mock_config_entry) -> None:
    """Test options flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_RECONNECT_INTERVAL: 30,
            CONF_HEALTH_CHECK_INTERVAL: 60,
            CONF_CONNECTION_STABILISE_DELAY: 1.0,
        },
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        CONF_RECONNECT_INTERVAL: 30,
        CONF_HEALTH_CHECK_INTERVAL: 60,
        CONF_CONNECTION_STABILISE_DELAY: 1.0,
    }


async def test_reconfigure_wrong_device(
    hass: HomeAssistant, mock_config_entry, mock_renkei_client
) -> None:
    """Test reconfigure rejects a different motor."""
    mock_config_entry.add_to_hass(hass)
    mock_renkei_client.get_info.return_value = {
        "response": "GET_INFO",
        "data": {
            "mac": "AA:BB:CC:DD:EE:FF",
            "ip": "192.168.1.101",
            "firmware": "1.0.5a",
            "hostname": "RENKEI-AABBCCDDEEFF",
        },
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.101"},
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "wrong_device"}
