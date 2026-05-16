"""Test the RENKEI PoE Motor Control cover platform."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.cover import CoverDeviceClass, CoverEntityFeature
from homeassistant.exceptions import ServiceValidationError

from custom_components.renkei_poe.cover import RenkeiCover
from custom_components.renkei_poe.renkei_client import ConnectionState


def _mock_coordinator(mock_hass, mock_renkei_client, data=None):
    """Create a coordinator-like object for entity unit tests."""
    coordinator = MagicMock()
    coordinator.hass = mock_hass
    coordinator.client = mock_renkei_client
    coordinator.config_entry.unique_id = "test_unique_id"
    coordinator.device_info = {"name": "Test Device"}
    coordinator.data = data if data is not None else {}
    coordinator.available = True
    coordinator.add_status_listener = MagicMock()
    coordinator.remove_status_listener = MagicMock()
    coordinator.add_connection_listener = MagicMock()
    coordinator.remove_connection_listener = MagicMock()
    coordinator.async_get_full_status = AsyncMock(
        return_value={
            "current_pos": 32768,
            "limit_pos": 65536,
            "err_flags": 0,
        }
    )
    return coordinator


def _cover(mock_hass, mock_renkei_client, data=None):
    """Create a cover entity with state writes stubbed."""
    cover = RenkeiCover(_mock_coordinator(mock_hass, mock_renkei_client, data))
    cover.async_write_ha_state = MagicMock()
    return cover


async def test_cover_entity_properties(mock_hass, mock_renkei_client):
    """Test cover entity basic properties."""
    cover = _cover(
        mock_hass,
        mock_renkei_client,
        {
            "status": {"current_pos": 50, "limit_pos": 100},
            "connection_state": ConnectionState.CONNECTED,
            "last_seen": "2023-01-01T00:00:00",
        },
    )

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
    """Test cover availability follows coordinator availability."""
    coordinator = _mock_coordinator(mock_hass, mock_renkei_client)
    cover = RenkeiCover(coordinator)

    coordinator.available = True
    assert cover.available is True

    coordinator.available = False
    assert cover.available is False


async def test_cover_position_calculation(mock_hass, mock_renkei_client):
    """Test cover position calculation from motor data."""
    cover = _cover(mock_hass, mock_renkei_client)

    cover.coordinator.data = {
        "status": {
            "current_pos_percent": 76,
            "current_pos": 32768,
            "limit_pos": 65536,
        },
        "connection_state": ConnectionState.CONNECTED,
    }
    assert cover.current_cover_position == 76

    cover.coordinator.data = {
        "status": {"current_pos": 32768, "limit_pos": 65536},
        "connection_state": ConnectionState.CONNECTED,
    }
    assert cover.current_cover_position == 50

    cover.coordinator.data = {
        "status": {"current_pos": 75},
        "connection_state": ConnectionState.CONNECTED,
    }
    assert cover.current_cover_position == 75

    cover.coordinator.data = None
    assert cover.current_cover_position is None


async def test_cover_state_properties(mock_hass, mock_renkei_client):
    """Test cover state properties."""
    cover = _cover(
        mock_hass,
        mock_renkei_client,
        {
            "status": {"current_pos": 0},
            "connection_state": ConnectionState.CONNECTED,
        },
    )

    assert cover.is_closed is True

    cover.coordinator.data["status"]["current_pos"] = 100
    assert cover.is_closed is False


async def test_cover_movement_state_from_current_pos(mock_hass, mock_renkei_client):
    """Test movement state from real-time position events."""
    cover = _cover(mock_hass, mock_renkei_client, {"status": {}})

    cover._handle_status_update({"event": "CURRENT_POS", "data": {"percent": 40}})
    cover._handle_status_update({"event": "CURRENT_POS", "data": {"percent": 45}})
    assert cover.is_opening is True
    assert cover.is_closing is False

    cover._handle_status_update({"event": "CURRENT_POS", "data": {"percent": 42}})
    assert cover.is_opening is False
    assert cover.is_closing is True

    cover._handle_status_update({"event": "CURRENT_POS", "data": {"percent": 42}})
    cover._handle_status_update({"event": "CURRENT_POS", "data": {"percent": 42}})
    assert cover.is_opening is False
    assert cover.is_closing is False


async def test_cover_open(mock_hass, mock_renkei_client):
    """Test cover open command."""
    cover = _cover(mock_hass, mock_renkei_client, {"status": {"current_pos": 50}})

    await cover.async_open_cover()

    mock_renkei_client.move.assert_called_once_with(position=100, delay=0)


async def test_cover_close(mock_hass, mock_renkei_client):
    """Test cover close command."""
    cover = _cover(mock_hass, mock_renkei_client, {"status": {"current_pos": 50}})

    await cover.async_close_cover()

    mock_renkei_client.move.assert_called_once_with(position=0, delay=0)


async def test_cover_set_position(mock_hass, mock_renkei_client):
    """Test cover set position command."""
    cover = _cover(mock_hass, mock_renkei_client, {"status": {"current_pos": 0}})

    await cover.async_set_cover_position(position=75)

    mock_renkei_client.move.assert_called_once_with(position=75, delay=0)


async def test_custom_set_position_with_delay(mock_hass, mock_renkei_client):
    """Test custom service set position supports delay."""
    cover = _cover(mock_hass, mock_renkei_client, {"status": {"current_pos": 0}})

    await cover.async_set_motor_position(position=75, delay=5)

    mock_renkei_client.move.assert_called_once_with(position=75, delay=5)


async def test_cover_set_position_no_position(mock_hass, mock_renkei_client):
    """Test cover set position without position parameter."""
    cover = _cover(mock_hass, mock_renkei_client)

    with pytest.raises(ServiceValidationError):
        await cover.async_set_cover_position()


async def test_cover_set_position_out_of_range(mock_hass, mock_renkei_client):
    """Test cover set position with out of range value."""
    cover = _cover(mock_hass, mock_renkei_client)

    with pytest.raises(ServiceValidationError):
        await cover._async_set_position(150)


async def test_cover_stop(mock_hass, mock_renkei_client):
    """Test cover stop command."""
    cover = _cover(mock_hass, mock_renkei_client)

    await cover.async_stop_cover()

    mock_renkei_client.stop.assert_called_once()


async def test_custom_service_methods(mock_hass, mock_renkei_client):
    """Test custom service methods call the targeted motor."""
    cover = _cover(mock_hass, mock_renkei_client)

    await cover.async_jog_motor(count=3)
    await cover.async_absolute_move(position=32768, delay=100)
    await cover.async_get_motor_status()
    await cover.async_get_motor_info()

    mock_renkei_client.jog.assert_called_once_with(count=3)
    mock_renkei_client.absolute_move.assert_called_once_with(
        position=32768, delay=100
    )
    cover.coordinator.async_get_full_status.assert_called_once()
    mock_renkei_client.get_info.assert_called()


async def test_cover_status_update_handling(mock_hass, mock_renkei_client):
    """Test cover handles status updates from coordinator."""
    cover = _cover(mock_hass, mock_renkei_client, {"status": {}})

    cover._handle_status_update(
        {
            "event": "CURRENT_POS",
            "data": {"percent": 85, "absolute": "D000"},
        }
    )

    assert cover._last_position == 85
    assert cover._absolute_position == 0xD000


async def test_cover_connection_state_handling(mock_hass, mock_renkei_client):
    """Test cover handles connection state changes."""
    cover = _cover(mock_hass, mock_renkei_client)
    cover._absolute_position = 1234

    cover._handle_connection_state(ConnectionState.CONNECTED)

    assert cover._absolute_position is None


async def test_cover_error_handling(mock_hass, mock_renkei_client):
    """Test cover handles motor errors."""
    cover = _cover(mock_hass, mock_renkei_client, {"status": {}})
    cover._is_opening = True

    cover._handle_status_update({"event": "ERROR", "data": {"code": 300}})

    assert cover.is_opening is False
    assert cover.is_closing is False
    assert cover._current_error is not None
    assert cover._current_error["code"] == 300


async def test_cover_extra_state_attributes(mock_hass, mock_renkei_client):
    """Test cover extra state attributes."""
    cover = _cover(
        mock_hass,
        mock_renkei_client,
        {
            "status": {"current_pos": 50},
            "connection_state": ConnectionState.CONNECTED,
        },
    )
    cover._absolute_position = 32768
    cover._current_error = {
        "code": 1,
        "description": "Test error",
        "timestamp": "2023-01-01T00:00:00",
    }

    attrs = cover.extra_state_attributes

    assert attrs["absolute_position"] == 32768
    assert attrs["error"] == "Test error"
    assert attrs["error_code"] == 1
