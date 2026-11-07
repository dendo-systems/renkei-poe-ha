"""Status queries share the legacy command-name response channel safely."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.renkei_poe.renkei_client import (
    ConnectionState,
    RenkeiClient,
    RenkeiConnectionError,
)


@pytest.fixture
def client():
    """Use real command/response handling with an in-memory TCP writer."""
    transport = RenkeiClient("192.0.2.1")
    transport.writer = MagicMock()
    transport.writer.drain = AsyncMock()
    return transport


async def test_concurrent_status_queries_keep_their_own_responses(client):
    """
    A final-state query cannot overwrite a health/diagnostic query waiter.
    """
    first = asyncio.create_task(client.get_status())
    second = asyncio.create_task(client.get_status())
    await asyncio.sleep(0)
    assert client.writer.write.call_count == 1

    moving = {"response": "GET_STATUS", "data": {"run_flags": 1}}
    await client._handle_message(moving)
    assert await first == moving
    await asyncio.sleep(0)
    assert client.writer.write.call_count == 2

    stopped = {"response": "GET_STATUS", "data": {"run_flags": 0}}
    await client._handle_message(stopped)
    assert await second == stopped
    assert not client._pending_responses


async def test_cancelling_status_check_removes_waiter(client):
    """Disconnect/unload cancellation leaves no orphaned response future."""
    task = asyncio.create_task(client.get_status())
    await asyncio.sleep(0)
    assert "GET_STATUS" in client._pending_responses
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not client._pending_responses
    assert not client._status_lock.locked()


async def test_cancelling_queued_check_preserves_active_query(client):
    """
    A queued status query never cancels another caller's in-flight request.
    """
    first = asyncio.create_task(client.get_status())
    queued = asyncio.create_task(client.get_status())
    await asyncio.sleep(0)
    queued.cancel()
    with pytest.raises(asyncio.CancelledError):
        await queued
    assert client.writer.write.call_count == 1
    response = {"response": "GET_STATUS", "data": {"run_flags": 0}}
    await client._handle_message(response)
    assert await first == response


async def test_motion_command_is_not_blocked_by_status_query(client):
    """Serializing status requests must not delay a user's STOP command."""
    query = asyncio.create_task(client.get_status())
    stop = asyncio.create_task(client.stop())
    await asyncio.sleep(0)
    assert client.writer.write.call_count == 2
    response = {"response": "STOP", "data": {"status": "OK"}}
    await client._handle_message(response)
    assert await stop == response
    assert not query.done()
    await client._handle_message(
        {"response": "GET_STATUS", "data": {"run_flags": 0}}
    )
    await query


@pytest.fixture
async def stream_client(monkeypatch):
    """Run the real TCP reader against an in-memory legacy protocol peer."""
    reader = asyncio.StreamReader()
    writer = MagicMock()
    writer.drain = AsyncMock()
    writer.wait_closed = AsyncMock()
    writer.is_closing.return_value = False

    def respond(frame):
        command = json.loads(frame)["cmd"]
        response = {"response": command, "data": {"run_flags": 0}}
        reader.feed_data((json.dumps(response) + "\n").encode())

    writer.write.side_effect = respond
    open_connection = AsyncMock(return_value=(reader, writer))
    monkeypatch.setattr(asyncio, "open_connection", open_connection)
    transport = RenkeiClient("192.0.2.1", connection_stabilise_delay=0)
    try:
        assert await transport.connect()
        yield transport, reader, writer, open_connection
    finally:
        await transport.disconnect()


async def test_real_reader_delivers_status_and_pushes_in_wire_order(
    stream_client,
):
    """The query response callback runs before its awaiting caller resumes."""
    transport, reader, _, open_connection = stream_client
    messages = []
    transport.set_status_callback(messages.append)
    reader.feed_data(
        b'\nnot-json\n{"event":"CURRENT_POS","data":{"percent":100}}\n'
    )
    response = await transport.get_status()
    assert [
        message.get("event", message.get("response")) for message in messages
    ] == ["CURRENT_POS", "GET_STATUS"]
    assert messages[-1] == response
    assert transport.last_seen is not None
    assert transport.connected
    assert transport.state == ConnectionState.CONNECTED
    assert await transport.connect()  # An existing session is reused.
    open_connection.assert_awaited_once()


@pytest.mark.parametrize(
    "method,args,command,params",
    [
        ("move", (75, 10), "MOVE", {"pos": 75, "delay": 10}),
        ("absolute_move", (750, 10), "A_MOVE", {"pos": 750, "delay": 10}),
        ("stop", (), "STOP", {}),
        ("jog", (2,), "JOG", {"count": 2}),
        ("get_info", (), "GET_INFO", {}),
    ],
)
async def test_legacy_commands_unchanged(
    stream_client, method, args, command, params
):
    """Stop detection adds no new firmware command or parameter requirement."""
    transport, _, writer, _ = stream_client
    await getattr(transport, method)(*args)
    assert json.loads(writer.write.call_args.args[0]) == {
        "cmd": command,
        "params": params,
    }


async def test_error_response_does_not_leak_status_waiter(client):
    """
    A rejected query releases the same channel used by later health checks.
    """
    task = asyncio.create_task(client.get_status())
    await asyncio.sleep(0)
    await client._handle_message(
        {
            "response": "ERROR",
            "data": {"code": 103, "description": "unreachable"},
        }
    )
    with pytest.raises(RenkeiConnectionError):
        await task
    assert not client._pending_responses
    assert not client._status_lock.locked()


async def test_query_timeout_releases_status_channel(client):
    """A timed-out status request cannot strand its lock or response future."""
    client._response_timeout = 0.001
    with pytest.raises(TimeoutError):
        await client.get_status()
    assert not client._pending_responses
    assert not client._status_lock.locked()


async def test_connection_failure_remains_unavailable(monkeypatch):
    """Failure to connect must never look like a successful status refresh."""
    monkeypatch.setattr(
        asyncio, "open_connection", AsyncMock(side_effect=OSError())
    )
    transport = RenkeiClient("192.0.2.1")
    states = []
    transport.set_connection_callback(states.append)
    assert not await transport.connect()
    assert states == [ConnectionState.CONNECTING, ConnectionState.DISCONNECTED]
    with pytest.raises(RenkeiConnectionError):
        await transport.get_status()


async def test_send_failure_releases_status_channel(client):
    """A transport write failure clears the new status serialization lock."""
    client.writer.write.side_effect = OSError("connection closed")
    with pytest.raises(RenkeiConnectionError):
        await client.get_status()
    assert not client._pending_responses
    assert not client._status_lock.locked()


async def test_reconnect_refreshes_status_before_resuming(stream_client):
    """
    After EOF, a fresh GET_STATUS is delivered on the replacement session.
    """
    transport, reader, writer, open_connection = stream_client
    replacement = asyncio.StreamReader()
    open_connection.return_value = (replacement, writer)
    transport.reconnect_interval = 0.001
    received = asyncio.Event()

    def respond(frame):
        response = {
            "response": json.loads(frame)["cmd"],
            "data": {"run_flags": 0},
        }
        replacement.feed_data((json.dumps(response) + "\n").encode())

    writer.write.side_effect = respond
    transport.set_status_callback(lambda message: received.set())
    reader.feed_eof()
    await asyncio.wait_for(received.wait(), timeout=1)
    assert transport.connected
    assert transport.just_reconnected
    assert open_connection.await_count == 2


async def test_health_check_uses_serialized_status_path(stream_client):
    """
    Optional health checks and motion confirmation use the same query API.
    """
    transport, _, _, _ = stream_client
    transport.health_check_interval = 0.001
    checked = asyncio.Event()
    transport.set_status_callback(lambda message: checked.set())
    health = asyncio.create_task(transport._health_check_loop())
    try:
        await asyncio.wait_for(checked.wait(), timeout=1)
        assert transport.connected
    finally:
        health.cancel()
        await health
