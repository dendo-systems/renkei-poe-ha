"""Constants for the RENKEI PoE Motor Control integration."""

from homeassistant.const import Platform

DOMAIN = "renkei_poe"

# Build platforms list with conditional diagnostics support
PLATFORMS = [Platform.COVER]
try:
    # Add diagnostics platform if available (HA 2023.4+)
    PLATFORMS.append(Platform.DIAGNOSTICS)
except AttributeError:
    # Platform.DIAGNOSTICS not available in this HA version
    pass

# Default configuration
DEFAULT_PORT = 17002
DEFAULT_RECONNECT_INTERVAL = 10
DEFAULT_HEALTH_CHECK_INTERVAL = 60
DEFAULT_CONNECTION_STABILISE_DELAY = 0.5

# Configuration keys
CONF_RECONNECT_INTERVAL = "reconnect_interval"
CONF_HEALTH_CHECK_INTERVAL = "health_check_interval"
CONF_CONNECTION_STABILISE_DELAY = "connection_stabilise_delay"

# Device information
MANUFACTURER = "Dendo Systems Pty Ltd"
MODEL = "RENKEI PoE Motor"

# mDNS/Zeroconf constants
ZEROCONF_TYPE = "_dendo._tcp.local."
HOSTNAME_PREFIX = "RENKEI-"

# Motor position constants
MIN_POSITION = 0
MAX_POSITION = 100

# Command timeout
COMMAND_TIMEOUT = 10.0

# Connection states mapping
CONNECTION_STATE_MAPPING = {
    "disconnected": "Disconnected",
    "connecting": "Connecting", 
    "connected": "Connected",
    "reconnecting": "Reconnecting"
}

# Error codes from motor controller (from API documentation)
ERROR_CODES = {
    "100": "Unknown command",
    "101": "Invalid parameters", 
    "102": "Motor busy",
    "103": "Motor unreachable",
    "104": "Checksum error",
    "300": "Limits not set",
    "301": "UART Error",
    "302": "Voltage error",
    "303": "Over-current error",
    "304": "Encoder error"
}

# Device classes and categories
DEVICE_CLASS_WINDOW = "window"
ENTITY_CATEGORY_DIAGNOSTIC = "diagnostic"

# Update intervals
FAST_UPDATE_INTERVAL = 5  # seconds
SLOW_UPDATE_INTERVAL = 30  # seconds

# Services
SERVICE_JOG = "jog"
SERVICE_SET_POSITION = "set_position"
SERVICE_ABSOLUTE_MOVE = "absolute_move"
SERVICE_GET_STATUS = "get_status"
SERVICE_GET_INFO = "get_info"

# Service schemas
SERVICE_JOG_SCHEMA = {
    "type": "object",
    "properties": {
        "count": {
            "type": "integer",
            "minimum": 1,
            "maximum": 10,
            "default": 1
        }
    }
}

SERVICE_SET_POSITION_SCHEMA = {
    "type": "object", 
    "properties": {
        "position": {
            "type": "integer",
            "minimum": MIN_POSITION,
            "maximum": MAX_POSITION
        },
        "delay": {
            "type": "integer",
            "minimum": 0,
            "maximum": 30,
            "default": 0
        }
    },
    "required": ["position"]
}

SERVICE_ABSOLUTE_MOVE_SCHEMA = {
    "type": "object", 
    "properties": {
        "position": {
            "type": "integer",
            "minimum": 0,
            "maximum": 65536
        },
        "delay": {
            "type": "integer",
            "minimum": 0,
            "maximum": 65535,
            "default": 0
        }
    },
    "required": ["position"]
}

SERVICE_GET_STATUS_SCHEMA = {
    "type": "object",
    "properties": {}
}

SERVICE_GET_INFO_SCHEMA = {
    "type": "object",
    "properties": {}
}