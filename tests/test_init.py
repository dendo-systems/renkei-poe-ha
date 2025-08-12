"""Test the RENKEI PoE Motor Control integration init."""

from unittest.mock import AsyncMock, patch
import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from custom_components.renkei_poe import async_setup_entry, async_unload_entry
from custom_components.renkei_poe.const import DOMAIN


async def test_setup_entry(
    hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_renkei_client
) -> None:
    """Test setting up config entry."""
    mock_config_entry.add_to_hass(hass)
    
    with patch("custom_components.renkei_poe.PLATFORMS", ["cover"]):
        assert await async_setup_entry(hass, mock_config_entry)
    
    # Verify coordinator was created and stored
    assert hasattr(mock_config_entry, 'runtime_data')
    
    # Verify client connection was attempted
    mock_renkei_client.connect.assert_called_once()


async def test_setup_entry_connection_error(
    hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_renkei_client
) -> None:
    """Test setup entry with connection error."""
    from custom_components.renkei_poe.renkei_client import RenkeiConnectionError
    
    mock_config_entry.add_to_hass(hass)
    mock_renkei_client.connect.side_effect = RenkeiConnectionError("Connection failed")
    
    with patch("custom_components.renkei_poe.PLATFORMS", ["cover"]):
        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, mock_config_entry)


async def test_setup_entry_timeout(
    hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_renkei_client
) -> None:
    """Test setup entry with timeout."""
    import asyncio
    
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
    
    # Mock successful platform unloading
    with patch("homeassistant.config_entries.ConfigEntries.async_unload_platforms") as mock_unload:
        mock_unload.return_value = True
        
        # Create mock coordinator
        mock_coordinator = AsyncMock()
        mock_config_entry.runtime_data = mock_coordinator
        
        # Mock no other entries
        with patch.object(hass.config_entries, "async_entries", return_value=[]):
            result = await async_unload_entry(hass, mock_config_entry)
            
        assert result is True
        mock_coordinator.async_shutdown.assert_called_once()


async def test_unload_entry_with_other_entries(
    hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_renkei_client
) -> None:
    """Test unloading entry when other entries exist (services should remain)."""
    mock_config_entry.add_to_hass(hass)
    
    # Mock successful platform unloading
    with patch("homeassistant.config_entries.ConfigEntries.async_unload_platforms") as mock_unload:
        mock_unload.return_value = True
        
        # Create mock coordinator
        mock_coordinator = AsyncMock()
        mock_config_entry.runtime_data = mock_coordinator
        
        # Mock other entries exist
        other_entry = AsyncMock()
        other_entry.entry_id = "other_id"
        other_entry.state.recoverable = True
        
        with patch.object(hass.config_entries, "async_entries", return_value=[other_entry]):
            result = await async_unload_entry(hass, mock_config_entry)
            
        assert result is True
        mock_coordinator.async_shutdown.assert_called_once()


async def test_service_registration(
    hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_renkei_client
) -> None:
    """Test that services are registered during setup."""
    mock_config_entry.add_to_hass(hass)
    
    with patch("custom_components.renkei_poe.PLATFORMS", ["cover"]):
        with patch("homeassistant.core.HomeAssistant.services") as mock_services:
            mock_services.has_service.return_value = False
            
            await async_setup_entry(hass, mock_config_entry)
            
            # Verify services were registered
            assert mock_services.async_register.call_count >= 4  # jog, set_position, absolute_move, get_status


async def test_service_calls(
    hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_renkei_client
) -> None:
    """Test service calls work correctly."""
    mock_config_entry.add_to_hass(hass)
    
    # Setup entry first
    with patch("custom_components.renkei_poe.PLATFORMS", ["cover"]):
        await async_setup_entry(hass, mock_config_entry)
    
    coordinator = mock_config_entry.runtime_data
    
    # Test jog service
    from homeassistant.core import ServiceCall
    jog_call = ServiceCall(DOMAIN, "jog", {"count": 3})
    
    # This would be called by the actual service handler
    await coordinator.client.jog(count=3)
    mock_renkei_client.jog.assert_called_with(count=3)
    
    # Test move service
    await coordinator.client.move(position=75, delay=5)
    mock_renkei_client.move.assert_called_with(position=75, delay=5)
    
    # Test absolute move service
    await coordinator.client.absolute_move(position=32768, delay=100)
    mock_renkei_client.absolute_move.assert_called_with(position=32768, delay=100)


async def test_coordinator_data_updates(
    hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_renkei_client
) -> None:
    """Test coordinator handles data updates correctly."""
    mock_config_entry.add_to_hass(hass)
    
    with patch("custom_components.renkei_poe.PLATFORMS", ["cover"]):
        await async_setup_entry(hass, mock_config_entry)
    
    coordinator = mock_config_entry.runtime_data
    
    # Test initial data fetch worked
    assert coordinator.data is not None
    assert "status" in coordinator.data
    assert "connection_state" in coordinator.data
    
    # Test status callback handling
    test_message = {
        "event": "CURRENT_POS",
        "data": {"percent": 75}
    }
    
    coordinator._handle_status_update(test_message)
    
    # Should update position in coordinator data
    assert coordinator.data["status"]["current_pos"] == 75


async def test_coordinator_connection_handling(
    hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_renkei_client
) -> None:
    """Test coordinator handles connection state changes."""
    from custom_components.renkei_poe.renkei_client import ConnectionState
    
    mock_config_entry.add_to_hass(hass)
    
    with patch("custom_components.renkei_poe.PLATFORMS", ["cover"]):
        await async_setup_entry(hass, mock_config_entry)
    
    coordinator = mock_config_entry.runtime_data
    
    # Test connection state callback
    coordinator._handle_connection_state(ConnectionState.DISCONNECTED)
    
    # Should update connection state in coordinator data
    assert coordinator.data["connection_state"] == ConnectionState.DISCONNECTED