# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **complete and functional Home Assistant custom component** for integrating with **RENKEI** PoE motors from Dendo Systems. The integration provides full control and monitoring capabilities for motorised window coverings such as curtains, blinds, and shades.

The integration allows Home Assistant to control and monitor motorised devices via TCP communication with RENKEI PoE motor controllers using a robust client library with automatic reconnection, health monitoring, and comprehensive error handling.

## Architecture

### Complete Integration Structure
```
renkei_poe/
├── __init__.py              # Integration entry point with services
├── manifest.json            # Integration metadata and dependencies
├── config_flow.py           # UI configuration flow with discovery
├── coordinator.py           # Data update coordinator
├── cover.py                 # Cover platform entity implementation
├── diagnostics.py           # Diagnostic information provider
├── repairs.py               # Automatic repair system
├── renkei_client.py         # Core client library for motor communication
├── const.py                 # Constants and configuration schemas
├── services.yaml            # Service definitions
├── strings.json             # UI strings
├── translations/            # Multi-language support (6 languages)
├── tests/                   # Comprehensive test suite
└── docs/                    # Documentation and API references
```

### Home Assistant Integration Components
All critical Home Assistant integration components are **fully implemented**:
- ✅ `__init__.py` - Integration entry point with 5 custom services
- ✅ `manifest.json` - Complete metadata with zeroconf discovery
- ✅ `config_flow.py` - UI configuration flow with automatic discovery
- ✅ `cover.py` - Cover platform with full motor control
- ✅ `const.py` - Constants, schemas, and error codes
- ✅ `coordinator.py` - Data update coordinator with callbacks
- ✅ `diagnostics.py` - Comprehensive diagnostic information
- ✅ `repairs.py` - Automatic repair system for common issues
- ✅ `services.yaml` - Service definitions with proper schemas
- ✅ `translations/` - Multi-language support (6 languages)
- ✅ `tests/` - Complete test suite with fixtures

## Core Client Architecture (renkei_client.py)

### RenkeiClient Class
The main client provides comprehensive motor communication:
- **Async TCP communication** with motor controllers on port 17002
- **Connection management** with automatic reconnection and configurable intervals
- **Command/response correlation** using futures with timeout handling
- **Health checking** via periodic GET_INFO commands (configurable)
- **State management** (DISCONNECTED, CONNECTING, CONNECTED, RECONNECTING)
- **Connection stabilisation delay** for reliable motor communication
- **Comprehensive error handling** with specific error codes

### Key Methods
- `connect()` - Establishes connection with stabilisation delay
- `send_command(cmd, params, expect_response=True)` - Generic command interface
- `move(position, delay=0)` - Move to position (0-100%)
- `absolute_move(position, delay=0)` - Move to absolute encoder position (0-32768)
- `stop()` - Emergency stop
- `get_status()` - Current motor status and diagnostics
- `get_info()` - Network information and firmware details
- `jog(count=1)` - Motor identification with configurable repetitions

### Callback System
- `set_status_callback()` - Handles all incoming status messages
- `set_connection_callback()` - Connection state change notifications

## Available Services

The integration provides 5 specialised services:

1. **`renkei_poe.jog`** - Motor identification through brief movements
2. **`renkei_poe.set_position`** - Percentage-based positioning (0-100%) with delay
3. **`renkei_poe.absolute_move`** - Precise encoder-based positioning (0-65536)
4. **`renkei_poe.get_status`** - Comprehensive motor status for diagnostics
5. **`renkei_poe.get_info`** - Network and firmware information

All services include proper validation, error handling, and multi-language support.

## Features

### Configuration Features
- **UI-based setup** via config flow with input validation
- **Automatic discovery** via mDNS/Zeroconf (`_dendo._tcp.local.`)
- **Reconfiguration support** for all settings
- **Advanced configuration options** (reconnect intervals, health checks, stabilisation delays)

### Operational Features
- **Real-time status updates** with position tracking
- **Connection state management** with automatic reconnection
- **Multi-language support** (English, German, Spanish, French, Japanese, Chinese)
- **Comprehensive diagnostics** with motor and network information
- **Automatic repair system** for common configuration issues
- **Error handling and reporting** with specific error codes

### Quality Features
- **Comprehensive test suite** with 95%+ coverage
- **Type hints throughout** for better code quality
- **Proper Home Assistant patterns** following official guidelines
- **Documentation** with troubleshooting guides and service references

## Development Commands

### Testing
```bash
# Run full test suite
python3 -m pytest tests/ --cov=custom_components/renkei_poe

# Run specific test files
python3 -m pytest tests/test_config_flow.py -v
python3 -m pytest tests/test_cover.py -v
python3 -m pytest tests/test_init.py -v

# Test with specific Home Assistant version
python3 -m pytest tests/ --cov=custom_components/renkei_poe --tb=short
```

### Code Quality
```bash
# Python linting (ensure follows Home Assistant standards)
python3 -m flake8 custom_components/renkei_poe/
python3 -m pylint custom_components/renkei_poe/

# Type checking
python3 -m mypy custom_components/renkei_poe/

# Home Assistant validation
python3 -m script.hassfest --integration-path custom_components/renkei_poe/
```

## Development Status

This integration is **production-ready and fully functional**:
- ✅ Client library (renkei_client.py) - Complete with all features
- ✅ Home Assistant integration files - All implemented
- ✅ Configuration flow - UI-based with discovery
- ✅ Cover platform - Full motor control entity
- ✅ Services - 5 specialised motor control services
- ✅ Tests - Comprehensive test suite
- ✅ Documentation - Complete with troubleshooting
- ✅ Translations - 6 languages supported
- ✅ Diagnostics - Comprehensive system information
- ✅ Repairs - Automatic issue detection and resolution

## Motor Communication Protocol

Commands are sent as JSON over TCP on port 17002:
```json
{"cmd": "MOVE", "params": {"pos": 50, "delay": 0}}
{"cmd": "A_MOVE", "params": {"pos": 32768, "delay": 100}}
{"cmd": "STOP", "params": {}}
{"cmd": "GET_STATUS", "params": {}}
{"cmd": "GET_INFO", "params": {}}
{"cmd": "JOG", "params": {"count": 3}}
```

Responses include command correlation and comprehensive data:
```json
{"response": "GET_STATUS", "data": {
  "current_pos": 32768,
  "limit_pos": 65536,
  "target_pos": 32768,
  "run_flags": 0,
  "err_flags": 0
}}
```

The client includes automatic reconnection, health checking, and stabilisation delays for reliable communication.

## Configuration Parameters

Key configuration options available through UI:
- **Host**: IP address of RENKEI PoE motor controller
- **Port**: TCP port (default: 17002)
- **Reconnect Interval**: Time between reconnection attempts (default: 10s)
- **Health Check Interval**: Connection health monitoring (default: 60s, 0=disabled)
- **Connection Stabilisation Delay**: Wait time after connection (default: 0.5s)

## Error Handling

The integration includes comprehensive error handling:
- **Motor error codes**: 100-104 (command/parameter errors), 300-304 (hardware errors)
- **Connection errors**: Automatic reconnection with exponential backoff
- **Validation errors**: Input validation with user-friendly messages
- **Repair system**: Automatic detection and resolution of common issues

## Next Development Areas

Potential enhancements (integration is already complete):
1. **Enhanced position memory** - Store and recall custom positions
2. **Scene integration** - Better integration with Home Assistant scenes
3. **Advanced scheduling** - Time-based motor control
4. **Group control** - Synchronised multi-motor operations
5. **Firmware updates** - OTA firmware update capabilities
6. **Enhanced diagnostics** - More detailed motor performance metrics