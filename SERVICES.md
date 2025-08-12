# RENKEI PoE Motor Services Reference

This document provides detailed information about all services provided by the RENKEI PoE Motor Control integration.

## Overview

The RENKEI integration provides four specialised services for controlling and diagnosing your motorised window coverings:

- **`renkei_poe.jog`** - Motor identification through brief movements
- **`renkei_poe.set_position`** - Percentage-based positioning with delay
- **`renkei_poe.absolute_move`** - Precise encoder-based positioning  
- **`renkei_poe.get_status`** - Comprehensive diagnostic information

All services support targeting specific motors or groups of motors using standard Home Assistant service targeting.

---

## `renkei_poe.jog`

Briefly moves the motor to help identify which physical motor corresponds to the entity in Home Assistant.

### Use Cases
- **Motor Identification**: Determine which physical motor is controlled by each entity
- **Basic Connectivity Test**: Verify the motor responds to commands
- **Installation Verification**: Confirm proper motor setup after installation

### Parameters

| Parameter | Type | Required | Default | Range | Description |
|-----------|------|----------|---------|-------|-------------|
| `count` | integer | No | 1 | 1-10 | Number of brief movements to perform |

### Examples

#### Basic Jog (Single Movement)
```yaml
service: renkei_poe.jog
target:
  entity_id: cover.living_room_shade
```

#### Multiple Jogs for Clear Identification
```yaml
service: renkei_poe.jog
target:
  entity_id: cover.bedroom_shade
data:
  count: 5
```

#### Jog Multiple Motors
```yaml
service: renkei_poe.jog
target:
  entity_id:
    - cover.living_room_shade
    - cover.kitchen_shade
data:
  count: 2
```

### Automation Example
```yaml
automation:
  - alias: "Identify motors on startup"
    trigger:
      platform: homeassistant
      event: start
    action:
      - delay: "00:01:00"  # Wait for system to stabilise
      - service: renkei_poe.jog
        target:
          entity_id: all  # Jog all RENKEI motors
        data:
          count: 1
```

---

## `renkei_poe.set_position`

Moves the motor to a specific percentage position (0-100%) with an optional delay before movement begins.

### Use Cases
- **Percentage Control**: Standard position control using familiar 0-100% scale
- **Delayed Execution**: Schedule movement to occur after a specified delay
- **Scene Management**: Set multiple motors to specific positions
- **Gradual Adjustments**: Step through positions with timed delays

### Parameters

| Parameter | Type | Required | Default | Range | Unit | Description |
|-----------|------|----------|---------|-------|------|-------------|
| `position` | integer | **Yes** | - | 0-100 | % | Target position percentage |
| `delay` | integer | No | 0 | 0-30 | seconds | Delay before starting movement |

### Position Reference
- **0%** = Fully closed (minimum encoder position)
- **25%** = Quarter open (privacy position)
- **50%** = Half open (partial light)
- **75%** = Three-quarter open (most light)
- **100%** = Fully open (maximum encoder position)

### Examples

#### Basic Position Setting
```yaml
service: renkei_poe.set_position
target:
  entity_id: cover.office_shade
data:
  position: 75  # 75% open
```

#### Delayed Position Change
```yaml
service: renkei_poe.set_position
target:
  entity_id: cover.bedroom_shade
data:
  position: 25   # Quarter open for privacy
  delay: 10      # Wait 10 seconds before moving
```

#### Multiple Motors with Different Positions
```yaml
service: renkei_poe.set_position
target:
  entity_id:
    - cover.living_room_shade
    - cover.kitchen_shade
data:
  position: 50  # Both to 50%
```

### Scene Integration
```yaml
scene:
  name: "Morning Light"
  entities:
    cover.east_window_shade:
      service: renkei_poe.set_position
      service_data:
        position: 75
        delay: 0
    cover.south_window_shade:
      service: renkei_poe.set_position  
      service_data:
        position: 50
        delay: 5  # Stagger the movement
```

### Automation Examples

#### Gradual Opening Sequence
```yaml
automation:
  - alias: "Gradual morning opening"
    trigger:
      platform: sun
      event: sunrise
    action:
      - service: renkei_poe.set_position
        target:
          entity_id: cover.bedroom_shade
        data:
          position: 25  # Start with privacy level
          delay: 0
      - delay: "00:15:00"  # Wait 15 minutes
      - service: renkei_poe.set_position
        target:
          entity_id: cover.bedroom_shade
        data:
          position: 75  # More light
          delay: 0
```

#### Weather-Based Adjustment
```yaml
automation:
  - alias: "Close on high UV"
    trigger:
      platform: numeric_state
      entity_id: sensor.uv_index
      above: 7
    action:
      service: renkei_poe.set_position
      target:
        entity_id: 
          - cover.south_facing_shade
          - cover.west_facing_shade
      data:
        position: 20  # Mostly closed for UV protection
        delay: 2
```

---

## `renkei_poe.absolute_move`

Moves the motor to a specific absolute encoder position (0-65536) for maximum precision. This service provides the finest control possible.

### Use Cases
- **Precision Positioning**: When exact positioning is critical
- **Calibration**: Setting precise reference points
- **Advanced Automation**: Fine-grained position control
- **Motor Limits**: Setting physical position boundaries

### Parameters

| Parameter | Type | Required | Default | Range | Unit | Description |
|-----------|------|----------|---------|-------|------|-------------|
| `position` | integer | **Yes** | - | 0-65536 | encoder steps | Target encoder position |
| `delay` | integer | No | 0 | 0-10000 | milliseconds | Delay before starting movement |

### Encoder Reference
- **0** = Fully closed (minimum physical position)
- **16384** = Approximately 25% open
- **32768** = Approximately 50% open  
- **49152** = Approximately 75% open
- **65536** = Fully open (maximum physical position)

*Note: Exact percentage varies by motor installation and mechanical limits.*

### Examples

#### Precise Positioning
```yaml
service: renkei_poe.absolute_move
target:
  entity_id: cover.precision_shade
data:
  position: 32768  # Exact centre position
```

#### Fine Adjustment with Delay
```yaml
service: renkei_poe.absolute_move
target:
  entity_id: cover.laboratory_shade
data:
  position: 45000  # Specific research position
  delay: 500       # 500ms delay for synchronization
```

#### Calibration Sequence
```yaml
service: renkei_poe.absolute_move
target:
  entity_id: cover.calibration_shade
data:
  position: 0      # Move to fully closed position
  delay: 1000      # 1 second delay
```

### Advanced Automation Examples

#### Input Number Integration
```yaml
# Input number for precise control
input_number:
  shade_encoder_position:
    name: "Shade Encoder Position"
    min: 0
    max: 65536
    step: 100
    mode: slider

automation:
  - alias: "Manual encoder position control"
    trigger:
      platform: state
      entity_id: input_number.shade_encoder_position
    action:
      service: renkei_poe.absolute_move
      target:
        entity_id: cover.manual_shade
      data:
        position: "{{ trigger.to_state.state | int }}"
```

#### Synchronized Multi-Motor Movement
```yaml
automation:
  - alias: "Synchronized precise opening"
    trigger:
      platform: time
      at: "08:00:00"
    action:
      # Move all motors to exact same encoder position simultaneously
      - service: renkei_poe.absolute_move
        target:
          entity_id:
            - cover.left_shade
            - cover.centre_shade  
            - cover.right_shade
        data:
          position: 30000
          delay: 0  # No delay for synchronization
```

#### Position Mapping Function
```yaml
# Script to convert percentage to encoder value
script:
  set_shade_percentage:
    alias: "Set shade to percentage (precise)"
    variables:
      encoder_position: "{{ (percentage / 100 * 65536) | int }}"
    sequence:
      - service: renkei_poe.absolute_move
        target:
          entity_id: "{{ entity_id }}"
        data:
          position: "{{ encoder_position }}"
          delay: "{{ delay | default(0) }}"
```

---

## `renkei_poe.get_status`

Retrieves comprehensive diagnostic information from the motor. The detailed status is logged to Home Assistant logs for analysis.

### Use Cases
- **Troubleshooting**: Diagnose connectivity or motor issues
- **System Monitoring**: Regular health checks of motor systems
- **Diagnostics**: Gather data for support requests
- **Automation Logic**: Make decisions based on motor status

### Parameters

This service takes no parameters - it retrieves all available status information.

### Retrieved Information

The status includes:
- **Position Data**: Current position, limit positions, target position
- **Motor State**: Movement flags, error conditions, operational status  
- **Network Info**: IP address, MAC address, firmware version
- **Connection Health**: Signal strength, communication statistics
- **Hardware Status**: Temperature, voltage, error flags

### Examples

#### Basic Status Check
```yaml
service: renkei_poe.get_status
target:
  entity_id: cover.main_shade
```

#### Status Check for All Motors
```yaml
service: renkei_poe.get_status
target:
  entity_id: all  # Check status of all RENKEI motors
```

### Automation Examples

#### Daily Health Check
```yaml
automation:
  - alias: "Daily motor health check"
    trigger:
      platform: time
      at: "06:00:00"
    action:
      service: renkei_poe.get_status
      target:
        entity_id: 
          - cover.living_room_shade
          - cover.bedroom_shade
          - cover.kitchen_shade
```

#### Status Check After Error
```yaml
automation:
  - alias: "Motor error recovery check"
    trigger:
      platform: state
      entity_id: cover.problematic_shade
      to: "unavailable"
      for: "00:05:00"  # Unavailable for 5 minutes
    action:
      - delay: "00:01:00"  # Wait for potential recovery
      - service: renkei_poe.get_status
        target:
          entity_id: cover.problematic_shade
```

#### Conditional Status Logging
```yaml
automation:
  - alias: "Status check on position mismatch"
    trigger:
      platform: template
      value_template: >
        {{ states('cover.precision_shade') == 'open' and 
           state_attr('cover.precision_shade', 'current_position') < 90 }}
    action:
      - service: renkei_poe.get_status
        target:
          entity_id: cover.precision_shade
      - service: persistent_notification.create
        data:
          title: "Motor Position Mismatch"
          message: "Check logs for detailed status information"
```

### Reading Status Output

After calling `get_status`, check the Home Assistant logs:

1. **Navigate** to Settings → System → Logs
2. **Filter** by "renkei_poe" or search for "Full motor status"
3. **Look for** entries like:
   ```
   INFO (MainThread) [custom_components.renkei_poe] Full motor status: {
     'current_pos': 32768,
     'limit_pos': 65536, 
     'target_pos': 32768,
     'run_flags': 0,
     'err_flags': 0,
     'firmware': '1.0.5a',
     'mac': 'A0:B7:65:31:11:5B',
     'ip': '192.168.1.100'
   }
   ```

---

## Service Targeting

All RENKEI services support Home Assistant's standard service targeting:

### Single Entity
```yaml
target:
  entity_id: cover.living_room_shade
```

### Multiple Entities
```yaml
target:
  entity_id:
    - cover.living_room_shade
    - cover.bedroom_shade
```

### Device Targeting
```yaml
target:
  device_id: "device_id_from_device_registry"
```

### Area Targeting
```yaml
target:
  area_id: "living_room"
```

### Label Targeting
```yaml
target:
  label_id: "window_coverings"
```

---

## Error Handling

All services include comprehensive error handling with translated messages:

### Common Error Messages
- **"Failed to jog motor: Connection timeout"** - Network connectivity issue
- **"Position is required"** - Missing required position parameter
- **"Position X is out of range (0-100)"** - Invalid position value
- **"Failed to move motor: Motor error 5"** - Hardware error condition

### Error Response Actions
1. **Check Connection**: Verify motor is powered and networked
2. **Validate Parameters**: Ensure all parameters are within valid ranges  
3. **Review Logs**: Check Home Assistant logs for detailed error information
4. **Use Diagnostics**: Download diagnostic data for troubleshooting
5. **Try get_status**: Use status service to check motor health

---

## Best Practices

### Performance Optimization
- **Avoid Rapid Commands**: Allow motors to complete movements before sending new commands
- **Use Delays Wisely**: Stagger movements of multiple motors to reduce network load
- **Batch Operations**: Group related position changes into scenes or scripts

### Automation Design
- **Include Error Handling**: Always account for potential communication failures
- **Use Appropriate Service**: Choose percentage vs. absolute positioning based on precision needs
- **Test Thoroughly**: Verify automations work correctly across different network conditions

### Maintenance
- **Regular Status Checks**: Use `get_status` periodically to monitor motor health
- **Monitor Logs**: Watch for patterns in connection or error messages
- **Update Firmware**: Keep motor firmware current for best compatibility

---

For additional information, see the [main documentation](README.md) or [troubleshooting guide](TROUBLESHOOTING.md).