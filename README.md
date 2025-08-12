# RENKEI PoE Motor Control Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![License](https://img.shields.io/github/license/dendo-systems/renkei-poe-homeassistant.svg)](LICENSE)
[![Version](https://img.shields.io/github/v/release/dendo-systems/renkei-poe-homeassistant)](https://github.com/dendo-systems/renkei-poe-homeassistant/releases)

A Home Assistant integration for controlling RENKEI PoE motors from Dendo Systems.

## Overview

RENKEI PoE motors are network-connected devices designed for motorising window coverings. They communicate over Ethernet using Power over Ethernet (PoE) for both power and control, eliminating the need for separate power supplies.

This integration provides:
- **Real-time control** of motor position and movement
- **Automatic discovery** via mDNS/Zeroconf
- **Live status updates** via TCP push notifications
- **Comprehensive diagnostics** for troubleshooting
- **Multi-language support** (English, Spanish, French, German, Japanese, Chinese)
- **Repair system** for automatic issue resolution

## Supported Devices

### RENKEI PoE Motors
- **RPE-20** and similar model variants
- All current RENKEI PoE motor models from Dendo Systems
- Firmware version 1.1.2 and later (recommended)

### Requirements
- **Network**: Ethernet connection with PoE support
- **Power**: Any standards compliant PoE switch rated for 802.3af or higher
- **Home Assistant**: Version 2023.8 or later

## Installation

### Via HACS (Recommended)

1. **Open HACS** in your Home Assistant instance
2. Go to **"Integrations"**
3. Click the **"+ Explore & Download Repositories"** button
4. Search for **"RENKEI PoE Motor"**
5. Click **"Download"**
6. Restart Home Assistant
7. Go to **Settings > Devices & Services**
8. Click **"Add Integration"** and search for **"RENKEI PoE Motor"**

### Manual Installation

1. **Download** the latest release from the [releases page](https://github.com/dendo-systems/renkei-poe-homeassistant/releases)
2. **Extract** the contents to your `custom_components` directory:
   ```
   config/custom_components/renkei_poe/
   ```
3. **Restart** Home Assistant
4. **Add Integration**: Go to Settings > Devices & Services > Add Integration > "RENKEI PoE Motor"

## Configuration

### Automatic Discovery (Recommended)

The integration automatically discovers RENKEI motors on your network:

1. **Navigate** to Settings > Devices & Services
2. **Look** for "Discovered" notification for RENKEI motors
3. **Click "Configure"** on the discovered motor
4. **Enter** a friendly name for your motor
5. **Click "Submit"** to complete setup

### Manual Configuration

If automatic discovery doesn't work:

1. **Add Integration**: Settings > Devices & Services > Add Integration
2. **Search** for "RENKEI PoE Motor"
3. **Configure** the connection:
   - **IP Address**: Motor's IP address (e.g., `192.168.1.100`)

## Features

### Entities

The integration creates the following entities for each motor:

#### Cover Entity
- **Entity ID**: `cover.{device_name}_shade`
- **Device Class**: `shade`
- **Supported Features**: Open, Close, Stop, Set Position
- **Position Range**: 0-100% (0 = fully closed, 100 = fully open)

#### Attributes
- **Current Position**: Real-time position percentage
- **Absolute Position**: Raw encoder value (0-65536)
- **Available**: Connection status to motor

### Diagnostics

Comprehensive diagnostic data available through Home Assistant's diagnostic download:

- **Cached Data**: Last known motor status
- **Current Data**: Real-time motor status
- **Network Information**: IP, MAC address, firmware version
- **Connection Status**: Current connection state and health

## Services

The integration provides several services for advanced control and automation:

### `renkei_poe.jog`
Briefly move the motor for identification purposes.

**Parameters:**
- `count` (optional): Number of jog movements (1-10, default: 1)

**Example:**
```yaml
service: renkei_poe.jog
target:
  entity_id: cover.living_room_shade
data:
  count: 3
```

### `renkei_poe.set_position`
Move the motor to a specific percentage position with optional delay.

**Parameters:**
- `position` (required): Target position 0-100%
- `delay` (optional): Delay before movement in seconds (0-30, default: 0)

**Example:**
```yaml
service: renkei_poe.set_position
target:
  entity_id: cover.living_room_shade
data:
  position: 75
  delay: 5
```

### `renkei_poe.absolute_move`
Move the motor to a specific absolute encoder position for precise control.

**Parameters:**
- `position` (required): Target encoder position (0-65536)
- `delay` (optional): Delay before movement in milliseconds (0-10000, default: 0)

**Example:**
```yaml
service: renkei_poe.absolute_move
target:
  entity_id: cover.living_room_shade
data:
  position: 32768  # Approximately 50%
  delay: 100
```

### `renkei_poe.get_status`
Retrieve full motor status for diagnostics (output appears in Home Assistant logs).

**Example:**
```yaml
service: renkei_poe.get_status
target:
  entity_id: cover.living_room_shade
```

## Automation Examples

### Sunrise/Sunset Automation
```yaml
automation:
  - alias: "Open blinds at sunrise"
    trigger:
      platform: sun
      event: sunrise
    action:
      service: cover.open_cover
      target:
        entity_id: cover.living_room_shade

  - alias: "Close blinds at sunset"
    trigger:
      platform: sun
      event: sunset
    action:
      service: cover.close_cover
      target:
        entity_id: cover.living_room_shade
```

### Position-Based Scene
```yaml
scene:
  - name: "Privacy Mode"
    entities:
      cover.living_room_shade: 25  # 25% open for privacy
      cover.bedroom_shade: 0       # Fully closed
```

### Conditional Movement with Delay
```yaml
automation:
  - alias: "Gradual morning opening"
    trigger:
      platform: time
      at: "07:00:00"
    action:
      - service: renkei_poe.set_position
        target:
          entity_id: cover.living_room_shade
        data:
          position: 50
          delay: 0
      - delay: "00:05:00"  # Wait 5 minutes
      - service: cover.open_cover
        target:
          entity_id: cover.living_room_shade
```

### Advanced Positioning
```yaml
automation:
  - alias: "Precise positioning"
    trigger:
      platform: state
      entity_id: input_number.shade_position
    action:
      service: renkei_poe.absolute_move
      target:
        entity_id: cover.living_room_shade
      data:
        position: "{{ (trigger.to_state.state | float * 655.36) | int }}"
```

## Data Updates

The integration uses **real-time push notifications** from the motor, providing:

- **Instant position updates** during movement
- **Error notifications** when issues occur
- **Connection state changes** for availability tracking
- **No polling required** - efficient and responsive

Data flows:
1. **Initial Setup**: GET_STATUS command retrieves current state
2. **Real-time Updates**: CURRENT_POS events during movement
3. **Error Handling**: ERROR events for troubleshooting
4. **Health Monitoring**: Optional periodic status checks

## Use Cases

### Automated Privacy Control
Configure blinds to automatically close when motion is detected in adjacent rooms, or open/close based on occupancy patterns.

### Energy Efficiency
Integrate with temperature sensors to automatically adjust window coverings for passive heating/cooling, reducing HVAC costs.

### Security Integration
Coordinate with security systems to close all coverings when "Away" mode is activated, or create random movement patterns during vacations.

### Circadian Lighting
Work with smart lighting systems to gradually adjust natural light throughout the day, supporting healthy circadian rhythms.

### Weather Response
Integrate with weather services to automatically close coverings during storms or high winds, protecting both the motors and interior.

## Known Limitations

### Hardware Limitations
- **One connection per motor** - Each RENKEI motor only accepts one connection
- **Encoder limits** - Position range limited to 0-32768 encoder steps

### Network Requirements
- **Direct TCP connection** - Motors must be reachable on the local network
- **Port 17002** - Firewall must allow communication on this port
- **mDNS support** - Discovery requires multicast DNS (usually enabled by default)

### Integration Constraints
- **Limited speed control** - Movement speed is fixed by motor firmware
- **Sequential commands** - Each motor processes one command at a time

## Troubleshooting

### Connection Issues

**Problem**: Motor not discovered automatically
**Solutions**:
1. Verify motor is powered and connected to network
2. Check that Home Assistant and motor are on same network segment
3. Ensure mDNS/multicast is not blocked by firewall
4. Try manual configuration with motor's IP address

**Problem**: "Connection timeout" errors
**Solutions**:
1. Ping motor IP address to verify network connectivity
2. Check firewall settings for port 17002
4. Restart both motor and Home Assistant

### Motor Control Issues

**Problem**: Commands not responding
**Solutions**:
1. Check motor status with `renkei_poe.get_status` service
2. Verify motor is not in error state (check diagnostics)
3. Try `renkei_poe.jog` service to test basic communication
4. Power cycle the motor

**Problem**: Reported position inaccurate 
**Solutions**:
1. This might be due to desync between motor and HA entity
3. Simply move the motor to refresh

### Advanced Diagnostics

1. **Download Diagnostics**: Settings > Devices & Services > RENKEI Motor > Download Diagnostics
2. **Check Integration Logs**: Settings > System > Logs > Filter by "renkei_poe"
3. **Network Analysis**: Use `ping` and `telnet` to verify connectivity
4. **Motor Reset**: Power cycle motor if communication is completely lost

For additional support, check the [troubleshooting guide](TROUBLESHOOTING.md) or [report an issue](https://github.com/dendo-systems/renkei-poe-homeassistant/issues).

## Supported Functionality

### Platforms
- **Cover**: Primary motor control entity
- **Diagnostics**: System health and troubleshooting data

### Device Features
- **Real-time Position Tracking**: Live updates during movement
- **Bi-directional Communication**: Commands and status updates
- **Error Detection**: Automatic problem identification and reporting
- **Network Discovery**: Automatic detection via mDNS/Zeroconf

### Integration Features
- **Multi-language Support**: 6 languages supported
- **Automatic Repairs**: Self-healing configuration issues
- **Service Actions**: 4 specialised services for advanced control
- **State Management**: Proper unavailable/available state handling

## Removal Instructions

### Via Home Assistant UI
1. **Navigate** to Settings > Devices & Services
2. **Find** the RENKEI PoE Motor integration
3. **Click** the three-dot menu
4. **Select** "Delete"
5. **Confirm** removal

### Complete Removal (Manual Installation)
1. **Remove** via UI (steps above)
2. **Delete** the integration folder:
   ```
   config/custom_components/renkei_poe/
   ```
3. **Restart** Home Assistant
4. **Clean up** any remaining entities in the entity registry if needed

### HACS Removal
1. **Remove** via UI (steps above)  
2. **Open** HACS > Integrations
3. **Find** "RENKEI PoE Motor"
4. **Click** the three-dot menu > "Uninstall"
5. **Restart** Home Assistant

## Contributing

We welcome contributions! Please see our [contributing guidelines](CONTRIBUTING.md) for details on:

- Bug reports and feature requests
- Code contributions and pull requests  
- Documentation improvements
- Translation updates

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- **Documentation**: [GitHub Wiki](https://github.com/dendo-systems/renkei-poe-homeassistant/wiki)
- **Issues**: [Bug Reports & Feature Requests](https://github.com/dendo-systems/renkei-poe-homeassistant/issues)
- **Discussions**: [Community Forum](https://github.com/dendo-systems/renkei-poe-homeassistant/discussions)
- **Dendo Systems**: [Official Website](https://dendosystems.com)

---

*RENKEI PoE Motor Control Integration - The next generation of window coverings automation.*