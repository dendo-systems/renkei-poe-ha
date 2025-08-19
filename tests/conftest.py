"""Common fixtures for RENKEI PoE Motor Control tests."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant

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


@pytest.fixture
def mock_renkei_client():
    """Mock RENKEI client for testing."""
    with patch("custom_components.renkei_poe.RenkeiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        
        # Mock successful connection and basic data
        mock_client.connect.return_value = None
        mock_client.disconnect.return_value = None
        mock_client.connected = True
        mock_client.state = "CONNECTED"
        mock_client.last_seen = "2023-01-01T00:00:00"
        
        # Mock device info response
        mock_client.get_info.return_value = {
            "response": "GET_INFO",
            "data": {
                "mac": "A0:B7:65:31:11:5B",
                "ip": "192.168.1.100",
                "firmware": "1.0.5a",
                "hostname": "RENKEI-A0B76531115B"
            }
        }
        
        # Mock status response
        mock_client.get_status.return_value = {
            "response": "GET_STATUS", 
            "data": {
                "current_pos": 32768,
                "limit_pos": 65536,
                "target_pos": 32768,
                "run_flags": 0,
                "err_flags": 0
            }
        }
        
        # Mock movement commands
        mock_client.move.return_value = {"response": "MOVE", "data": {}}
        mock_client.stop.return_value = {"response": "STOP", "data": {}}
        mock_client.jog.return_value = {"response": "JOG", "data": {}}
        mock_client.absolute_move.return_value = {"response": "A_MOVE", "data": {}}
        
        yield mock_client


@pytest.fixture
def mock_config_entry_data():
    """Mock config entry data."""
    return {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: DEFAULT_PORT,
        CONF_NAME: "Test RENKEI Motor",
        CONF_RECONNECT_INTERVAL: DEFAULT_RECONNECT_INTERVAL,
        CONF_HEALTH_CHECK_INTERVAL: DEFAULT_HEALTH_CHECK_INTERVAL,
        CONF_CONNECTION_STABILISE_DELAY: DEFAULT_CONNECTION_STABILISE_DELAY,
    }


@pytest.fixture
def mock_config_entry(mock_config_entry_data):
    """Mock config entry."""
    from homeassistant.config_entries import ConfigEntry
    
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.unique_id = "a0b76531115b"
    entry.title = "Test RENKEI Motor"
    entry.data = mock_config_entry_data
    entry.options = {}
    entry.domain = DOMAIN
    entry.state = "loaded"
    
    return entry


@pytest.fixture
async def mock_hass():
    """Mock Home Assistant core."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config_entries = MagicMock()
    hass.services = MagicMock()
    hass.states = MagicMock()
    hass.bus = MagicMock()
    
    return hass