"""
Exercise motor stop reconciliation through real coordinator/cover handlers.
"""

import asyncio
from datetime import datetime, UTC
from unittest.mock import MagicMock

import pytest

from custom_components.renkei_poe.coordinator import RenkeiCoordinator
from custom_components.renkei_poe.cover import RenkeiCover
from custom_components.renkei_poe.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.renkei_poe.motor_status import MotorMotion, motor_motion
from custom_components.renkei_poe.renkei_client import ConnectionState


@pytest.fixture
async def motor(hass, mock_config_entry, mock_renkei_client):
    """Connect a real coordinator and cover to a simulated motor transport."""
    mock_config_entry.add_to_hass(hass)
    coordinator = RenkeiCoordinator(hass, mock_config_entry)
    coordinator.data = {
        "status": {"current_pos": 500, "limit_pos": 1000, "run_flags": 0}
    }
    cover = RenkeiCover(coordinator)
    cover.async_write_ha_state = MagicMock()

    async def get_status():
        response = mock_renkei_client.get_status.return_value
        coordinator._handle_status_update(response)
        return response

    mock_renkei_client.get_status.side_effect = get_status
    try:
        yield coordinator, cover, mock_renkei_client
    finally:
        await coordinator.async_shutdown()


def position(coordinator, percent, absolute=None):
    """Deliver the unchanged legacy CURRENT_POS wire shape."""
    data = {"percent": percent}
    if absolute is not None:
        data["absolute"] = absolute
    coordinator._handle_status_update({"event": "CURRENT_POS", "data": data})


def status(client, current_pos, run_flags=0):
    """Set the response to the next actual-state query."""
    client.get_status.return_value = {
        "response": "GET_STATUS",
        "data": {
            "current_pos": current_pos,
            "limit_pos": 1000,
            "run_flags": run_flags,
            "err_flags": 0,
        },
    }


async def check_motion(coordinator):
    """Advance the quiet-period check without wall-clock sleeps."""
    assert coordinator._motion_status_timer is not None
    coordinator._cancel_motion_timer()
    coordinator._start_motion_status_check()
    await coordinator._motion_status_task


@pytest.mark.parametrize(
    ("events", "final_pos", "moving", "final_state", "final_percent"),
    [
        ([90, 99, 100], 1000, "opening", "open", 100),
        ([10, 1, 0], 0, "closing", "closed", 0),
        ([60, 44, 43], 437, "closing", "open", 44),
        ([90, 98, 99], 999, "opening", "open", 100),
    ],
)
async def test_single_final_event_reconciles_stop(
    motor, events, final_pos, moving, final_state, final_percent
):
    """Firmware 2.x needs no duplicate endpoint events or health polling."""
    coordinator, cover, client = motor
    client.health_check_interval = 0
    for percent in events:
        position(coordinator, percent)
    assert cover.state == moving
    status(client, final_pos, 0xD0)  # Other run flags must not imply movement.

    await check_motion(coordinator)

    assert cover.state == final_state
    assert cover.current_cover_position == final_percent
    assert cover.extra_state_attributes["absolute_position"] == final_pos
    assert coordinator._motion_status_timer is None
    client.get_status.assert_awaited_once()


async def test_vendor_duplicates_do_not_postpone_stop_check(motor):
    """
    Legacy repeated idle pushes neither starve the check nor start idle
    polling.
    """
    coordinator, cover, client = motor
    for percent in [90, 99, 100]:
        position(coordinator, percent, percent * 10)
    timer = coordinator._motion_status_timer
    for _ in range(5):
        position(coordinator, 100, 1000)
        assert coordinator._motion_status_timer is timer
    status(client, 1000)
    await check_motion(coordinator)
    assert cover.state == "open"

    for _ in range(5):
        position(coordinator, 100, 1000)
    assert cover.state == "open"
    assert coordinator._motion_status_timer is None
    client.get_status.assert_awaited_once()


async def test_quiet_period_automatically_queries_status(motor, monkeypatch):
    """
    Position traffic starts a real timer even with health polling disabled.
    """
    coordinator, cover, client = motor
    monkeypatch.setattr(
        "custom_components.renkei_poe.coordinator.MOTION_STATUS_DELAY", 0.001
    )
    checked = asyncio.Event()
    status(client, 1000)

    async def get_status():
        response = client.get_status.return_value
        coordinator._handle_status_update(response)
        checked.set()
        return response

    client.get_status.side_effect = get_status
    position(coordinator, 90)
    position(coordinator, 100)
    assert cover.is_opening
    await asyncio.wait_for(checked.wait(), timeout=1)
    assert cover.state == "open"
    assert coordinator._motion_status_timer is None


async def test_same_percentage_is_not_proof_of_stopping(motor):
    """
    Slow movement, even at displayed 100%, still follows the motion flags.
    """
    coordinator, cover, client = motor
    position(coordinator, 99, 990)
    position(coordinator, 100, 995)
    timer = coordinator._motion_status_timer
    position(coordinator, 100, 996)
    assert timer.cancelled()
    assert cover.is_opening
    status(client, 997, 0x91)
    await check_motion(coordinator)
    assert cover.current_cover_position == 100
    assert cover.is_opening
    assert coordinator._motion_status_timer is not None

    status(client, 1000)
    await check_motion(coordinator)
    assert not cover.is_opening
    assert coordinator._motion_status_timer is None


@pytest.mark.parametrize("absolute", [999, None])
async def test_duplicate_truncated_position_does_not_restart_motion(
    motor, absolute
):
    """
    Rounded status and truncated push positions cannot create false closing.
    """
    coordinator, cover, client = motor
    position(coordinator, 99, absolute)
    status(client, 999)
    await check_motion(coordinator)
    assert cover.current_cover_position == 100
    assert cover.state == "open"
    position(coordinator, 99, absolute)
    assert cover.current_cover_position == 100
    assert not cover.is_opening
    assert not cover.is_closing
    assert coordinator._motion_status_timer is None


async def test_direction_uses_latest_status_encoder_baseline(motor):
    """
    A reversed motor is not compared with an older percentage observation.
    """
    coordinator, cover, client = motor
    position(coordinator, 60, 600)
    status(client, 800, 2)
    coordinator._handle_status_update(client.get_status.return_value)
    position(coordinator, 79, 790)
    assert cover.is_closing
    assert not cover.is_opening


@pytest.mark.parametrize("event", ["GET_STATUS", "MOTOR_STATUS"])
@pytest.mark.parametrize(
    "flags,state", [(0xA0, "open"), (0xA1, "opening"), (0xA2, "closing")]
)
async def test_full_status_is_applied_before_state_is_published(
    motor, event, flags, state
):
    """Health checks and vendor debug events use the same fresh snapshot."""
    coordinator, cover, client = motor
    position(coordinator, 99)
    status(client, 1000, flags)
    message = client.get_status.return_value
    if event == "MOTOR_STATUS":
        message = {"event": event, "data": message["data"]}
    published = []
    cover.async_write_ha_state.side_effect = lambda: published.append(
        (cover.state, cover.current_cover_position)
    )
    coordinator._handle_status_update(message)
    assert published == [(state, 100)]


async def test_status_and_new_push_are_not_applied_out_of_order(motor):
    """A diagnostic caller must not reapply its response over a newer event."""
    coordinator, cover, client = motor
    status(client, 500, 1)

    async def get_status():
        response = client.get_status.return_value
        coordinator._handle_status_update(response)
        position(coordinator, 70, 700)
        return response

    client.get_status.side_effect = get_status
    await coordinator.async_get_full_status()
    assert cover.current_cover_position == 70
    assert cover.is_opening


@pytest.mark.parametrize("query_fails", [False, True])
async def test_diagnostics_share_authoritative_status_handling(
    motor, query_fails
):
    """Diagnostic queries update motion too; errors do not imply stopped."""
    coordinator, cover, client = motor
    coordinator.config_entry.runtime_data = coordinator
    client.connected = True
    client.last_seen = datetime.now(UTC)
    position(coordinator, 90)
    status(client, 1000)
    if query_fails:
        client.get_status.side_effect = TimeoutError("no status")
    result = await async_get_config_entry_diagnostics(
        coordinator.hass, coordinator.config_entry
    )
    assert result["network_info"]["firmware"] == "1.0.5a"
    if query_fails:
        assert result["current_motor_status"] == {"error": "no status"}
        assert cover.is_opening
    else:
        assert result["current_motor_status"]["run_flags"] == 0
        assert cover.state == "open"
        assert cover.current_cover_position == 100


@pytest.mark.parametrize("failure", [TimeoutError(), None, -1, 3, True, "0"])
async def test_failed_or_invalid_status_never_implies_stopped(motor, failure):
    """Retries are bounded and silence/invalid flags never fabricate a stop."""
    coordinator, cover, client = motor
    position(coordinator, 90)
    if isinstance(failure, Exception):
        client.get_status.side_effect = failure
    else:
        status(client, 1000, failure)
    for _ in range(3):
        await check_motion(coordinator)
        assert cover.is_opening
    assert coordinator._motion_status_timer is None
    assert client.get_status.await_count == 3


async def test_stop_ack_requires_stopped_status(motor):
    """
    STOP acknowledgement schedules verification instead of assuming execution.
    """
    coordinator, cover, client = motor
    position(coordinator, 40)
    coordinator._handle_status_update(
        {"response": "STOP", "data": {"status": "OK"}}
    )
    assert cover.is_closing
    status(client, 400)
    await check_motion(coordinator)
    assert cover.state == "open"
    assert not cover.is_closing


async def test_disconnect_cancels_pending_check_and_resets_direction(motor):
    """
    A new connection must not compare position to the old motion baseline.
    """
    coordinator, cover, client = motor
    position(coordinator, 90)
    timer = coordinator._motion_status_timer
    coordinator._handle_connection_state(ConnectionState.DISCONNECTED)
    assert timer.cancelled()
    assert coordinator._motion_status_timer is None
    assert not cover.is_opening
    assert cover._last_position is None
    coordinator._handle_connection_state(ConnectionState.CONNECTED)
    status(client, 0)
    coordinator._handle_status_update(client.get_status.return_value)
    assert cover.state == "closed"


async def test_unload_cancels_inflight_query(motor):
    """Unload owns and joins its outstanding reconciliation task."""
    coordinator, _, client = motor
    started = asyncio.Event()

    async def wait_for_status():
        started.set()
        await asyncio.Future()

    client.get_status.side_effect = wait_for_status
    position(coordinator, 90)
    coordinator._cancel_motion_timer()
    coordinator._start_motion_status_check()
    task = coordinator._motion_status_task
    await started.wait()
    await coordinator.async_shutdown()
    assert task.cancelled()
    assert coordinator._motion_status_timer is None
    position(coordinator, 100)
    assert coordinator._motion_status_timer is None


@pytest.mark.parametrize("flags", [None, True, -1, 256, "0", 0.0, 3, 255])
def test_invalid_motion_flags(flags):
    """Unknown flags are never silently converted to stopped."""
    assert motor_motion(flags) is None


@pytest.mark.parametrize("motion", list(MotorMotion))
def test_initial_motion_snapshot(mock_hass, mock_renkei_client, motion):
    """A cover loaded during movement starts with the reported direction."""
    coordinator = MagicMock()
    coordinator.data = {
        "status": {
            "current_pos": 500,
            "limit_pos": 1000,
            "run_flags": 0x90 | motion,
        }
    }
    coordinator.hass = mock_hass
    cover = RenkeiCover(coordinator)
    assert cover.is_opening == (motion == MotorMotion.OPENING)
    assert cover.is_closing == (motion == MotorMotion.CLOSING)
