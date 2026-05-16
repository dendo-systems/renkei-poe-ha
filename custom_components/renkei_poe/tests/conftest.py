"""Common fixtures for RENKEI PoE Motor Control tests."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

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
from custom_components.renkei_poe.renkei_client import ConnectionState


@pytest.fixture
def mock_renkei_client():
    """Mock RENKEI client for testing."""
    mock_client = MagicMock()

    with (
        patch(
            "custom_components.renkei_poe.config_flow.RenkeiClient",
            return_value=mock_client,
        ) as config_flow_client_class,
        patch(
            "custom_components.renkei_poe.coordinator.RenkeiClient",
            return_value=mock_client,
        ) as coordinator_client_class,
    ):
        mock_client.config_flow_client_class = config_flow_client_class
        mock_client.coordinator_client_class = coordinator_client_class

        # Mock successful connection and basic data
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.disconnect = AsyncMock(return_value=None)
        mock_client.connected = True
        mock_client.state = ConnectionState.CONNECTED
        mock_client.last_seen = "2023-01-01T00:00:00"
        mock_client.just_reconnected = False
        mock_client.set_status_callback = MagicMock()
        mock_client.set_connection_callback = MagicMock()
        
        # Mock device info response
        mock_client.get_info = AsyncMock(return_value={
            "response": "GET_INFO",
            "data": {
                "mac": "A0:B7:65:31:11:5B",
                "ip": "192.168.1.100",
                "firmware": "1.0.5a",
                "hostname": "RENKEI-A0B76531115B"
            }
        })
        
        # Mock status response
        mock_client.get_status = AsyncMock(return_value={
            "response": "GET_STATUS", 
            "data": {
                "current_pos": 32768,
                "limit_pos": 65536,
                "target_pos": 32768,
                "run_flags": 0,
                "err_flags": 0
            }
        })
        
        # Mock movement commands
        mock_client.move = AsyncMock(return_value={"response": "MOVE", "data": {}})
        mock_client.stop = AsyncMock(return_value={"response": "STOP", "data": {}})
        mock_client.jog = AsyncMock(return_value={"response": "JOG", "data": {}})
        mock_client.absolute_move = AsyncMock(return_value={"response": "A_MOVE", "data": {}})
        
        yield mock_client


@pytest.fixture
def mock_config_entry_data():
    """Mock config entry data."""
    return {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: DEFAULT_PORT,
        CONF_RECONNECT_INTERVAL: DEFAULT_RECONNECT_INTERVAL,
        CONF_HEALTH_CHECK_INTERVAL: DEFAULT_HEALTH_CHECK_INTERVAL,
        CONF_CONNECTION_STABILISE_DELAY: DEFAULT_CONNECTION_STABILISE_DELAY,
    }


@pytest.fixture
def mock_config_entry(mock_config_entry_data):
    """Mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry_data,
        entry_id="test_entry_id",
        unique_id="a0b76531115b",
        title="Test RENKEI Motor",
        options={},
    )


@pytest.fixture
async def mock_hass():
    """Mock Home Assistant core."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config_entries = MagicMock()
    hass.services = MagicMock()
    hass.states = MagicMock()
    hass.bus = MagicMock()
    
    return hass
