"""Test the RENKEI PoE Motor Control integration init."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from custom_components.renkei_poe import async_setup, async_setup_entry, async_unload_entry
from custom_components.renkei_poe.const import (
    CONF_CONNECTION_STABILISE_DELAY,
    CONF_HEALTH_CHECK_INTERVAL,
    CONF_RECONNECT_INTERVAL,
    SERVICE_ABSOLUTE_MOVE,
    SERVICE_GET_INFO,
    SERVICE_GET_STATUS,
    SERVICE_JOG,
    SERVICE_SET_POSITION,
)
from custom_components.renkei_poe.renkei_client import ConnectionState


async def test_setup_registers_entity_services(hass: HomeAssistant) -> None:
    """Test that services are registered globally."""
    with patch(
        "custom_components.renkei_poe.service.async_register_platform_entity_service"
    ) as mock_register:
        assert await async_setup(hass, {})

    service_names = [call.args[2] for call in mock_register.call_args_list]
    assert service_names == [
        SERVICE_JOG,
        SERVICE_SET_POSITION,
        SERVICE_ABSOLUTE_MOVE,
        SERVICE_GET_STATUS,
        SERVICE_GET_INFO,
    ]


async def test_setup_entry(
    hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_renkei_client
) -> None:
    """Test setting up config entry."""
    mock_config_entry.add_to_hass(hass)

    with patch("custom_components.renkei_poe.PLATFORMS", ["cover"]):
        assert await async_setup_entry(hass, mock_config_entry)

    assert hasattr(mock_config_entry, "runtime_data")
    mock_renkei_client.connect.assert_called_once()


async def test_setup_entry_connection_error(
    hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_renkei_client
) -> None:
    """Test setup entry with connection error."""
    from custom_components.renkei_poe.renkei_client import RenkeiConnectionError

    mock_config_entry.add_to_hass(hass)
    mock_renkei_client.connect.side_effect = RenkeiConnectionError(
        "Connection failed"
    )

    with patch("custom_components.renkei_poe.PLATFORMS", ["cover"]):
        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, mock_config_entry)


async def test_setup_entry_timeout(
    hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_renkei_client
) -> None:
    """Test setup entry with timeout."""
    mock_config_entry.add_to_hass(hass)
    mock_renkei_client.get_info.side_effect = asyncio.TimeoutError()

    with patch("custom_components.renkei_poe.PLATFORMS", ["cover"]):
        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, mock_config_entry)


async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_renkei_client
) -> None:
    """Test unloading config entry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        return_value=True,
    ):
        mock_coordinator = AsyncMock()
        mock_config_entry.runtime_data = mock_coordinator

        result = await async_unload_entry(hass, mock_config_entry)

    assert result is True
    mock_coordinator.async_shutdown.assert_called_once()


async def test_coordinator_data_updates(
    hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_renkei_client
) -> None:
    """Test coordinator handles data updates correctly."""
    mock_config_entry.add_to_hass(hass)

    with patch("custom_components.renkei_poe.PLATFORMS", ["cover"]):
        await async_setup_entry(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data

    assert coordinator.data is not None
    assert "status" in coordinator.data
    assert "connection_state" in coordinator.data

    coordinator._handle_status_update(
        {
            "event": "CURRENT_POS",
            "data": {"percent": 75},
        }
    )

    assert coordinator.data["status"]["current_pos_percent"] == 75


async def test_coordinator_connection_handling(
    hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_renkei_client
) -> None:
    """Test coordinator handles connection state changes."""
    mock_config_entry.add_to_hass(hass)

    with patch("custom_components.renkei_poe.PLATFORMS", ["cover"]):
        await async_setup_entry(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data

    coordinator._handle_connection_state(ConnectionState.DISCONNECTED)

    assert coordinator.data["connection_state"] == ConnectionState.DISCONNECTED


async def test_coordinator_uses_options(
    hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_renkei_client
) -> None:
    """Test coordinator prefers options over stored defaults."""
    mock_config_entry.options = {
        CONF_RECONNECT_INTERVAL: 30,
        CONF_HEALTH_CHECK_INTERVAL: 120,
        CONF_CONNECTION_STABILISE_DELAY: 2.0,
    }
    mock_config_entry.add_to_hass(hass)

    with patch("custom_components.renkei_poe.PLATFORMS", ["cover"]):
        await async_setup_entry(hass, mock_config_entry)

    mock_renkei_client.coordinator_client_class.assert_called_with(
        host="192.168.1.100",
        port=17002,
        reconnect_interval=30,
        health_check_interval=120,
        connection_stabilise_delay=2.0,
    )
