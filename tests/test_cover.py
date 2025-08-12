"""Test the RENKEI PoE Motor Control cover platform."""

from unittest.mock import AsyncMock, patch
import pytest
from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntityFeature,
)
from homeassistant.const import STATE_CLOSED, STATE_OPEN, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from custom_components.renkei_poe.cover import RenkeiCover
from custom_components.renkei_poe.renkei_client import ConnectionState


async def test_cover_entity_properties(mock_hass, mock_renkei_client):
    """Test cover entity basic properties."""
    # Create mock coordinator
    mock_coordinator = AsyncMock()
    mock_coordinator.hass = mock_hass
    mock_coordinator.client = mock_renkei_client
    mock_coordinator.config_entry.unique_id = "test_unique_id"
    mock_coordinator.device_info = {"name": "Test Device"}
    mock_coordinator.data = {
        "status": {"current_pos": 50, "limit_pos": 100},
        "connection_state": ConnectionState.CONNECTED,
        "last_seen": "2023-01-01T00:00:00"
    }
    
    cover = RenkeiCover(mock_coordinator)
    
    # Test basic properties
    assert cover.has_entity_name is True
    assert cover.translation_key == "shade"
    assert cover.device_class == CoverDeviceClass.SHADE
    assert cover.supported_features == (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )
    assert cover.unique_id == "test_unique_id_cover"


async def test_cover_availability(mock_hass, mock_renkei_client):
    """Test cover availability based on connection state."""
    mock_coordinator = AsyncMock()
    mock_coordinator.hass = mock_hass
    mock_coordinator.client = mock_renkei_client
    mock_coordinator.config_entry.unique_id = "test"
    mock_coordinator.device_info = {}
    mock_coordinator.data = {}
    
    # Mock coordinator availability
    mock_coordinator.available = True
    mock_renkei_client.state = ConnectionState.CONNECTED
    
    cover = RenkeiCover(mock_coordinator)
    
    # Should be available when connected
    assert cover.available is True
    
    # Should be unavailable when disconnected
    mock_renkei_client.state = ConnectionState.DISCONNECTED
    assert cover.available is False


async def test_cover_position_calculation(mock_hass, mock_renkei_client):
    """Test cover position calculation from motor data."""
    mock_coordinator = AsyncMock()
    mock_coordinator.hass = mock_hass
    mock_coordinator.client = mock_renkei_client
    mock_coordinator.config_entry.unique_id = "test"
    mock_coordinator.device_info = {}
    
    cover = RenkeiCover(mock_coordinator)
    
    # Test percentage position (from CURRENT_POS events)
    mock_coordinator.data = {
        "status": {"current_pos": 75},  # Already a percentage
        "connection_state": ConnectionState.CONNECTED
    }
    assert cover.current_cover_position == 75
    
    # Test encoder position calculation (from GET_STATUS response)
    mock_coordinator.data = {
        "status": {"current_pos": 32768, "limit_pos": 65536},  # Encoder values
        "connection_state": ConnectionState.CONNECTED
    }
    assert cover.current_cover_position == 50  # 32768/65536 * 100 = 50%
    
    # Test no data
    mock_coordinator.data = None
    assert cover.current_cover_position is None


async def test_cover_state_properties(mock_hass, mock_renkei_client):
    """Test cover state properties (open/closed/moving)."""
    mock_coordinator = AsyncMock()
    mock_coordinator.hass = mock_hass
    mock_coordinator.client = mock_renkei_client
    mock_coordinator.config_entry.unique_id = "test"
    mock_coordinator.device_info = {}
    mock_coordinator.data = {
        "status": {"current_pos": 0},  # Fully closed
        "connection_state": ConnectionState.CONNECTED
    }
    
    cover = RenkeiCover(mock_coordinator)
    
    # Test closed state
    assert cover.is_closed is True
    
    # Test open state
    mock_coordinator.data["status"]["current_pos"] = 100
    assert cover.is_closed is False
    
    # Test moving states
    cover._is_moving = True
    cover._target_position = 100
    mock_coordinator.data["status"]["current_pos"] = 50  # Currently at 50%
    
    assert cover.is_opening is True
    assert cover.is_closing is False
    
    # Test moving closed
    cover._target_position = 0
    assert cover.is_opening is False
    assert cover.is_closing is True


async def test_cover_open(mock_hass, mock_renkei_client):
    """Test cover open command."""
    mock_coordinator = AsyncMock()
    mock_coordinator.hass = mock_hass
    mock_coordinator.client = mock_renkei_client
    mock_coordinator.config_entry.unique_id = "test"
    mock_coordinator.device_info = {}
    mock_coordinator.data = {"status": {"current_pos": 50}}
    
    cover = RenkeiCover(mock_coordinator)
    
    await cover.async_open_cover()
    
    mock_renkei_client.move.assert_called_once_with(position=100)


async def test_cover_close(mock_hass, mock_renkei_client):
    """Test cover close command."""
    mock_coordinator = AsyncMock()
    mock_coordinator.hass = mock_hass
    mock_coordinator.client = mock_renkei_client
    mock_coordinator.config_entry.unique_id = "test"
    mock_coordinator.device_info = {}
    mock_coordinator.data = {"status": {"current_pos": 50}}
    
    cover = RenkeiCover(mock_coordinator)
    
    await cover.async_close_cover()
    
    mock_renkei_client.move.assert_called_once_with(position=0)


async def test_cover_set_position(mock_hass, mock_renkei_client):
    """Test cover set position command."""
    mock_coordinator = AsyncMock()
    mock_coordinator.hass = mock_hass
    mock_coordinator.client = mock_renkei_client
    mock_coordinator.config_entry.unique_id = "test"
    mock_coordinator.device_info = {}
    mock_coordinator.data = {"status": {"current_pos": 0}}
    
    cover = RenkeiCover(mock_coordinator)
    
    await cover.async_set_cover_position(position=75)
    
    mock_renkei_client.move.assert_called_once_with(position=75)


async def test_cover_set_position_no_position(mock_hass, mock_renkei_client):
    """Test cover set position without position parameter."""
    mock_coordinator = AsyncMock()
    mock_coordinator.hass = mock_hass
    mock_coordinator.client = mock_renkei_client
    mock_coordinator.config_entry.unique_id = "test"
    mock_coordinator.device_info = {}
    mock_coordinator.data = {}
    
    cover = RenkeiCover(mock_coordinator)
    
    with patch("custom_components.renkei_poe.cover._get_translated_exception") as mock_translate:
        mock_translate.return_value = "Position is required"
        
        with pytest.raises(ServiceValidationError, match="Position is required"):
            await cover.async_set_cover_position()


async def test_cover_set_position_out_of_range(mock_hass, mock_renkei_client):
    """Test cover set position with out of range value."""
    mock_coordinator = AsyncMock()
    mock_coordinator.hass = mock_hass
    mock_coordinator.client = mock_renkei_client
    mock_coordinator.config_entry.unique_id = "test"
    mock_coordinator.device_info = {}
    mock_coordinator.data = {}
    
    cover = RenkeiCover(mock_coordinator)
    
    with patch("custom_components.renkei_poe.cover._get_translated_exception") as mock_translate:
        mock_translate.return_value = "Position 150 is out of range (0-100)"
        
        with pytest.raises(ServiceValidationError, match="Position 150 is out of range"):
            await cover._async_set_position(150)


async def test_cover_stop(mock_hass, mock_renkei_client):
    """Test cover stop command."""
    mock_coordinator = AsyncMock()
    mock_coordinator.hass = mock_hass
    mock_coordinator.client = mock_renkei_client
    mock_coordinator.config_entry.unique_id = "test"
    mock_coordinator.device_info = {}
    mock_coordinator.data = {}
    
    cover = RenkeiCover(mock_coordinator)
    
    await cover.async_stop_cover()
    
    mock_renkei_client.stop.assert_called_once()


async def test_cover_status_update_handling(mock_hass, mock_renkei_client):
    """Test cover handles status updates from coordinator."""
    mock_coordinator = AsyncMock()
    mock_coordinator.hass = mock_hass
    mock_coordinator.client = mock_renkei_client
    mock_coordinator.config_entry.unique_id = "test"
    mock_coordinator.device_info = {}
    mock_coordinator.data = {"status": {}}
    
    cover = RenkeiCover(mock_coordinator)
    
    # Test CURRENT_POS event handling
    position_message = {
        "event": "CURRENT_POS",
        "data": {"percent": 85, "absolute": "D000"}  # 85% and hex absolute position
    }
    
    cover._handle_status_update(position_message)
    
    # Should update position tracking
    assert cover._last_position == 85
    assert cover._absolute_position == 0xD000


async def test_cover_connection_state_handling(mock_hass, mock_renkei_client):
    """Test cover handles connection state changes."""
    mock_coordinator = AsyncMock()
    mock_coordinator.hass = mock_hass
    mock_coordinator.client = mock_renkei_client
    mock_coordinator.config_entry.unique_id = "test"
    mock_coordinator.device_info = {}
    mock_coordinator.data = {}
    
    cover = RenkeiCover(mock_coordinator)
    cover._is_moving = True
    cover._target_position = 100
    
    # Test disconnection resets movement state
    cover._handle_connection_state(ConnectionState.DISCONNECTED)
    
    assert cover._is_moving is False
    assert cover._target_position is None


async def test_cover_error_handling(mock_hass, mock_renkei_client):
    """Test cover handles motor errors."""
    mock_coordinator = AsyncMock()
    mock_coordinator.hass = mock_hass
    mock_coordinator.client = mock_renkei_client
    mock_coordinator.config_entry.unique_id = "test"
    mock_coordinator.device_info = {}
    mock_coordinator.data = {"status": {}}
    
    cover = RenkeiCover(mock_coordinator)
    cover._is_moving = True
    
    # Test error message handling
    error_message = {
        "event": "ERROR",
        "data": {"code": 3}
    }
    
    cover._handle_status_update(error_message)
    
    # Should stop movement and store error info
    assert cover._is_moving is False
    assert cover._current_error is not None
    assert cover._current_error["code"] == 3


async def test_cover_extra_state_attributes(mock_hass, mock_renkei_client):
    """Test cover extra state attributes."""
    mock_coordinator = AsyncMock()
    mock_coordinator.hass = mock_hass
    mock_coordinator.client = mock_renkei_client
    mock_coordinator.config_entry.unique_id = "test"
    mock_coordinator.device_info = {}
    mock_coordinator.data = {
        "status": {"current_pos": 50},
        "connection_state": ConnectionState.CONNECTED
    }
    
    cover = RenkeiCover(mock_coordinator)
    cover._absolute_position = 32768
    cover._current_error = {
        "code": 1,
        "description": "Test error",
        "timestamp": "2023-01-01T00:00:00"
    }
    
    attrs = cover.extra_state_attributes
    
    # Should include diagnostic information
    assert "absolute_position" in attrs
    assert attrs["absolute_position"] == 32768
    assert "error" in attrs
    assert attrs["error"] == "Test error"
    assert "error_code" in attrs
    assert attrs["error_code"] == 1