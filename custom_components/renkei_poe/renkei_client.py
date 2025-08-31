import asyncio
import logging
import json
from datetime import datetime
from typing import Optional, Callable, Dict, Any
from enum import Enum

_LOGGER = logging.getLogger(__name__)

class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"


class RenkeiClientError(Exception):
    """Base exception for Renkei client errors."""
    pass

class RenkeiConnectionError(RenkeiClientError):
    """Connection related errors."""
    pass

class RenkeiClient:
    def __init__(self, host: str, port: int = 17002, reconnect_interval: int = 10, 
                 health_check_interval: int = 0, connection_stabilise_delay: float = 0.5):
        self.host = host
        self.port = port
        self.reconnect_interval = reconnect_interval
        self.health_check_interval = health_check_interval  # 0 = disabled
        self.connection_stabilise_delay = connection_stabilise_delay  # NEW: Stabilisation delay
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self._state = ConnectionState.DISCONNECTED
        self.last_seen: Optional[datetime] = None
        self._listen_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        self._health_check_task: Optional[asyncio.Task] = None
        self._just_reconnected = False  # Flag to track when cache sync is needed
        self._status_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self._connection_callback: Optional[Callable[[ConnectionState], None]] = None
        self._lock = asyncio.Lock()
        self._shutdown_event = asyncio.Event()
        self._listen_ready = asyncio.Event()  # NEW: Signal when listen loop is ready
        
        # Command response tracking
        self._pending_responses: Dict[str, asyncio.Future] = {}
        self._response_timeout = 10.0  # seconds
        
        _LOGGER.debug(f"RenkeiClient initialised - health_check_interval={health_check_interval}, host={host}")

    @property
    def connected(self) -> bool:
        """Return True if currently connected."""
        return self._state == ConnectionState.CONNECTED

    @property
    def state(self) -> ConnectionState:
        """Return current connection state."""
        return self._state
    
    @property
    def just_reconnected(self) -> bool:
        """Return True if client just reconnected and needs cache sync."""
        return self._just_reconnected

    def _set_state(self, new_state: ConnectionState) -> None:
        """Set connection state and notify callback."""
        if self._state != new_state:
            old_state = self._state
            self._state = new_state
            _LOGGER.debug(f"Connection state changed from {old_state.value} to {new_state.value}")
            
            if self._connection_callback:
                try:
                    self._connection_callback(new_state)
                except Exception as e:
                    _LOGGER.error(f"Error in connection callback: {e}")

    async def connect(self) -> bool:
        """Connect to the motor. Returns True if successful."""
        async with self._lock:
            if self.connected:
                return True
            
            self._set_state(ConnectionState.CONNECTING)
            
            try:
                _LOGGER.info(f"Connecting to {self.host}:{self.port}")
                self.reader, self.writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port),
                    timeout=5.0
                )
                
                # Disable Nagle's algorithm for better motor responsiveness
                if self.writer:
                    sock = self.writer.get_extra_info('socket')
                    if sock:
                        sock.setsockopt(asyncio.socket.IPPROTO_TCP, asyncio.socket.TCP_NODELAY, 1)
                        _LOGGER.debug("TCP_NODELAY enabled for improved motor responsiveness")
                
                self._set_state(ConnectionState.CONNECTED)
                _LOGGER.info(f"Connected to {self.host}:{self.port}")
                
                # Start listening task
                if self._listen_task:
                    self._listen_task.cancel()
                
                self._listen_ready.clear()  # Reset the ready flag
                self._listen_task = asyncio.create_task(self._listen_loop())
                _LOGGER.debug("Listen task started")
                
                # Wait for listen loop to be ready before proceeding
                try:
                    _LOGGER.debug("Waiting for listen loop to be ready...")
                    await asyncio.wait_for(self._listen_ready.wait(), timeout=5.0)  # Increased timeout
                    _LOGGER.debug("Listen loop confirmed ready")
                except asyncio.TimeoutError:
                    _LOGGER.error("Listen loop failed to become ready within 5 seconds")
                    return False
                
                # Allow motor to stabilise after connection
                if self.connection_stabilise_delay > 0:
                    _LOGGER.debug(f"Allowing {self.connection_stabilise_delay}s for motor to stabilise...")
                    await asyncio.sleep(self.connection_stabilise_delay)
                    _LOGGER.debug("Motor stabilisation delay complete")
                
                # Start optional health check task
                if self.health_check_interval > 0:
                    _LOGGER.debug(f"Starting health check task with {self.health_check_interval}s interval")
                    if self._health_check_task:
                        self._health_check_task.cancel()
                    self._health_check_task = asyncio.create_task(self._health_check_loop())
                else:
                    _LOGGER.debug("Health check disabled (interval = 0)")
                
                return True
                
            except Exception as e:
                _LOGGER.error(f"Failed to connect to {self.host}:{self.port}: {e}")
                self._set_state(ConnectionState.DISCONNECTED)
                await self._cleanup_connection()
                return False

    async def _listen_loop(self) -> None:
        """Main listening loop for incoming messages."""
        _LOGGER.debug("Listen loop started")
        try:
            # Signal that listen loop is ready to receive messages
            self._listen_ready.set()
            _LOGGER.debug("Listen loop ready for messages")
            
            while not self._shutdown_event.is_set() and self.reader:
                try:
                    # Wait for message WITHOUT timeout - let TCP handle connection health
                    line = await self.reader.readline()
                    
                    if not line:
                        _LOGGER.info("Connection closed by motor")
                        break

                    self.last_seen = datetime.now()
                    line = line.decode().strip()
                    _LOGGER.debug(f"Raw line received: {line}")

                    if not line:
                        continue

                    try:
                        message = json.loads(line)
                        _LOGGER.debug(f"Parsed message: {message}")
                        await self._handle_message(message)
                        
                    except json.JSONDecodeError as e:
                        _LOGGER.warning(f"Invalid JSON from motor: {line} ({e})")
                    
                except Exception as e:
                    _LOGGER.error(f"Error reading from connection: {e}")
                    break
                    
        except Exception as e:
            _LOGGER.error(f"Fatal error in listen loop: {e}")
        finally:
            _LOGGER.debug(f"Listen loop exiting - current state: {self._state.value}, connected: {self.connected}")
            if self.connected:
                _LOGGER.info("Connection lost, attempting to reconnect")
                self._set_state(ConnectionState.DISCONNECTED)
            else:
                _LOGGER.debug("Listen loop exiting but already disconnected")
            await self._handle_disconnection()

    async def _handle_message(self, message: Dict[str, Any]) -> None:
        """Handle incoming message from motor."""
        try:
            # Handle responses to commands
            if "response" in message:
                cmd = message["response"]
                _LOGGER.debug(f"Received response for command: {cmd}")
                _LOGGER.debug(f"Pending responses: {list(self._pending_responses.keys())}")
                
                # Handle ERROR responses - they could be for any pending command
                if cmd == "ERROR":
                    error_code = message["data"].get("code", "unknown")
                    error_desc = message["data"].get("description", "No description")
                    _LOGGER.error(f"Motor returned error {error_code}: {error_desc}")
                    
                    # Find the most recent pending response and set it as error
                    # Since we don't know which command failed, take the oldest pending
                    if self._pending_responses:
                        # Get the first (oldest) pending response
                        oldest_cmd = next(iter(self._pending_responses))
                        future = self._pending_responses.pop(oldest_cmd)
                        if not future.done():
                            error = RenkeiClientError(f"Motor error {error_code}: {error_desc}")
                            future.set_exception(error)
                            _LOGGER.debug(f"Set error for pending command {oldest_cmd}")
                    else:
                        _LOGGER.warning("Received ERROR response but no pending commands")
                
                else:
                    # Handle normal command responses
                    if cmd in self._pending_responses:
                        future = self._pending_responses.pop(cmd)
                        if not future.done():
                            future.set_result(message)
                            _LOGGER.debug(f"Response correlated successfully for {cmd}")
                        else:
                            _LOGGER.warning(f"Future for {cmd} was already done")
                    else:
                        _LOGGER.warning(f"No pending response expected for {cmd}")

            # Forward all messages to status callback
            if self._status_callback:
                self._status_callback(message)
                
        except Exception as e:
            _LOGGER.error(f"Error handling message {message}: {e}")

    async def _health_check_loop(self) -> None:
        """Optional health check loop using GET_STATUS commands."""
        _LOGGER.debug(f"Health check loop started with {self.health_check_interval}s interval")
        while not self._shutdown_event.is_set() and self.connected:
            try:
                await asyncio.sleep(self.health_check_interval)
                
                if not self.connected:
                    break
                    
                # Send GET_STATUS command to check health and refresh motor data
                try:
                    await asyncio.wait_for(
                        self.send_command("GET_STATUS", expect_response=True),
                        timeout=5.0
                    )
                    _LOGGER.debug("Health check passed")
                except Exception as e:
                    _LOGGER.info(f"Health check failed: {e}")
                    # Application layer failure - trigger disconnection
                    if not self._shutdown_event.is_set():  # Only if not shutting down
                        _LOGGER.info("Motor disconnected, attempting reconnection")
                        await self._handle_disconnection()
                    break  # Exit health check loop
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                _LOGGER.error(f"Error in health check loop: {e}")
                break

    async def _handle_disconnection(self) -> None:
        """Handle disconnection and attempt reconnect if needed."""
        _LOGGER.debug(f"_handle_disconnection called - current state: {self._state.value}, shutdown: {self._shutdown_event.is_set()}")
        await self._cleanup_connection()
        
        # Cancel any pending responses with timeout
        for future in self._pending_responses.values():
            if not future.done():
                future.set_exception(RenkeiConnectionError("Connection lost"))
        self._pending_responses.clear()
        
        # Start reconnection if not shutting down
        if not self._shutdown_event.is_set():
            _LOGGER.info("Connection lost, starting reconnection process")
            self._set_state(ConnectionState.RECONNECTING)
            if self._reconnect_task:
                self._reconnect_task.cancel()
            self._reconnect_task = asyncio.create_task(self._reconnect_loop())
        else:
            _LOGGER.warning("Shutdown event set, not starting reconnection")

    async def _reconnect_loop(self) -> None:
        """Reconnection loop."""
        while not self._shutdown_event.is_set() and not self.connected:
            try:
                _LOGGER.info(f"Attempting to reconnect in {self.reconnect_interval} seconds...")
                await asyncio.sleep(self.reconnect_interval)
                
                if await self.connect():
                    _LOGGER.info("Reconnection successful")
                    # Set flag to indicate cache sync is needed on next GET_STATUS
                    self._just_reconnected = True
                    # Immediately refresh motor status after reconnection to sync current position
                    try:
                        await asyncio.wait_for(self.get_status(), timeout=5.0)
                        _LOGGER.debug("Motor status refreshed after reconnection")
                    except Exception as e:
                        _LOGGER.warning(f"Failed to refresh status after reconnection: {e}")
                    break
                    
            except Exception as e:
                _LOGGER.error(f"Reconnection attempt failed: {e}")

    async def _cleanup_connection(self) -> None:
        """Clean up connection resources."""
        if self.writer:
            try:
                if not self.writer.is_closing():
                    self.writer.close()
                await self.writer.wait_closed()
            except Exception as e:
                _LOGGER.debug(f"Exception during writer cleanup: {e}")
        
        self.reader = None
        self.writer = None

    async def send_command(self, cmd: str, params: Optional[Dict[str, Any]] = None, 
                          expect_response: bool = True) -> Optional[Dict[str, Any]]:
        """
        Send command to motor.
        
        Args:
            cmd: Command name
            params: Command parameters
            expect_response: Whether to wait for a response
            
        Returns:
            Response message if expect_response=True, None otherwise
            
        Raises:
            RenkeiConnectionError: If not connected or send fails
            asyncio.TimeoutError: If response times out
        """
        if not self.writer:
            raise RenkeiConnectionError("Not connected to motor")

        message = {
            "cmd": cmd,
            "params": params or {}
        }

        # Set up response future if expecting response
        response_future = None
        if expect_response:
            response_future = asyncio.Future()
            self._pending_responses[cmd] = response_future
            _LOGGER.debug(f"Registered future for command: {cmd}")

        try:
            msg_str = json.dumps(message) + "\n"
            self.writer.write(msg_str.encode())
            await self.writer.drain()
            _LOGGER.debug(f"Sent command: {msg_str.strip()}")
            
            # Wait for response if expected
            if expect_response and response_future:
                try:
                    _LOGGER.debug(f"Waiting for response to {cmd}...")
                    response = await asyncio.wait_for(response_future, timeout=self._response_timeout)
                    _LOGGER.debug(f"Got response for {cmd}: {response}")
                    return response
                except asyncio.TimeoutError:
                    # Clean up pending response
                    self._pending_responses.pop(cmd, None)
                    _LOGGER.error(f"Timeout waiting for response to {cmd}. Pending: {list(self._pending_responses.keys())}")
                    raise asyncio.TimeoutError(f"Timeout waiting for response to {cmd}")
            
            return None
            
        except Exception as e:
            # Clean up pending response on error
            if expect_response and cmd in self._pending_responses:
                future = self._pending_responses.pop(cmd)
                if not future.done():
                    future.set_exception(e)
            
            if isinstance(e, (asyncio.TimeoutError, RenkeiConnectionError)):
                raise
            else:
                raise RenkeiConnectionError(f"Failed to send command '{cmd}': {e}")

    async def move(self, position: int, delay: int = 0) -> Optional[Dict[str, Any]]:
        """Move motor to position (0-100% open)."""
        return await self.send_command("MOVE", {"pos": position, "delay": delay})

    async def absolute_move(self, position: int, delay: int = 0) -> Optional[Dict[str, Any]]:
        """Move motor to absolute position (encoder value 0-65536)."""
        return await self.send_command("A_MOVE", {"pos": position, "delay": delay})

    async def stop(self) -> Optional[Dict[str, Any]]:
        """Stop motor immediately."""
        return await self.send_command("STOP")

    async def get_status(self) -> Optional[Dict[str, Any]]:
        """Get motor status."""
        return await self.send_command("GET_STATUS")

    async def get_info(self) -> Optional[Dict[str, Any]]:
        """Get network info."""
        return await self.send_command("GET_INFO")

    async def jog(self, count: int = 1) -> Optional[Dict[str, Any]]:
        """Jog motor for identification."""
        return await self.send_command("JOG", {"count": count})

    def set_status_callback(self, callback: Optional[Callable[[Dict[str, Any]], None]]) -> None:
        """Set callback for status updates and events."""
        self._status_callback = callback

    def set_connection_callback(self, callback: Optional[Callable[[ConnectionState], None]]) -> None:
        """Set callback for connection state changes."""
        self._connection_callback = callback

    async def disconnect(self) -> None:
        """Cleanly disconnect from motor."""
        _LOGGER.info("Disconnecting from motor...")
        
        # Signal shutdown
        self._shutdown_event.set()
        
        # Cancel tasks
        tasks = [self._listen_task, self._health_check_task, self._reconnect_task]
        for task in tasks:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Cleanup connection
        await self._cleanup_connection()
        self._set_state(ConnectionState.DISCONNECTED)
        
        _LOGGER.info("Disconnected cleanly.")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()