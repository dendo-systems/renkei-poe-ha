# RENKEI PoE Motor Troubleshooting Guide

This guide helps resolve common issues with the RENKEI PoE Motor Control integration for Home Assistant.

## Quick Diagnostic Steps

Before diving into specific problems, try these general diagnostic steps:

1. **Download Diagnostics**: Settings → Devices & Services → RENKEI Motor → Download Diagnostics
2. **Check Integration Logs**: Settings → System → Logs → Filter by "renkei_poe"
3. **Verify Network Connectivity**: Ping the motor's IP address
4. **Test Basic Communication**: Use the `renkei_poe.jog` service
5. **Check Motor Power**: Ensure PoE+ power supply is adequate

---

## Discovery and Initial Setup Issues

### Motor Not Discovered Automatically

**Symptoms:**
- No "Discovered" notification appears
- Motor doesn't show up in mDNS discovery
- Integration setup requires manual IP entry

**Causes & Solutions:**

#### 1. Network Segmentation
**Cause**: Home Assistant and motor on different network segments
**Solution**: 
- Verify both devices are on the same subnet
- Check VLAN configuration if using managed switches
- Test with `ping {motor_ip}` from Home Assistant host

#### 2. mDNS/Multicast Blocked
**Cause**: Firewall or network equipment blocking multicast DNS
**Solution**:
- Enable mDNS/Bonjour in firewall settings
- Check if multicast forwarding is disabled on WiFi networks
- Try connecting Home Assistant device to wired network temporarily

#### 3. Motor Firmware Issues
**Cause**: Older firmware may advertise incorrect service information
**Solution**:
- Update motor firmware to latest version
- Use manual configuration with correct IP and port 17002
- Contact Dendo Systems for firmware update procedures

#### 4. Home Assistant mDNS Configuration
**Cause**: Home Assistant mDNS integration disabled or misconfigured
**Solution**:
```yaml
# Ensure this is in your configuration.yaml
discovery:
zeroconf:
```

### Manual Setup Fails with Connection Errors

**Symptoms:**
- "Connection timeout" during setup
- "Cannot connect to the motor controller"
- Setup process hangs indefinitely

**Diagnostic Steps:**

#### 1. Verify Network Connectivity
```bash
# Test basic connectivity (run on HA host)
ping {motor_ip}

# Test TCP port connectivity  
telnet {motor_ip} 17002
# or
nc -zv {motor_ip} 17002
```

#### 2. Check Firewall Rules
- **Home Assistant**: Ensure outbound connections to port 17002 allowed
- **Network Firewall**: Allow TCP traffic on port 17002
- **Motor**: Some motors have built-in firewall (rare)

#### 3. Verify Motor Settings
- **IP Address**: Confirm motor has expected IP address
- **Port Configuration**: Verify motor is listening on port 17002
- **Network Configuration**: Check subnet mask and gateway settings

#### 4. Power and Boot State
- **PoE Power**: Ensure PoE+ (802.3at) power supply
- **Boot Sequence**: Wait 2-3 minutes after power-on for full initialization
- **Status LEDs**: Check motor status indicators if available

---

## Connection and Communication Issues

### Frequent Disconnections

**Symptoms:**
- Motor shows as "unavailable" periodically
- Integration logs show reconnection attempts
- Commands fail intermittently

**Solutions:**

#### 1. Network Infrastructure Issues
**Problem**: Unstable network connection
**Solution**:
- Check network cables and connections
- Replace network switch ports or cables if suspect
- Monitor network error rates with network tools

#### 2. PoE Power Issues  
**Problem**: Insufficient or unstable PoE power
**Solution**:
- Verify PoE+ (802.3at) power supply capability
- Check PoE switch power budget and consumption
- Test with PoE injector to isolate switch issues

#### 3. Adjust Connection Parameters
**Problem**: Default timeouts too aggressive for network conditions
**Solution**:
```yaml
# Reconfigure integration with conservative settings:
# - Reconnect Interval: 30 seconds (instead of 10)
# - Health Check Interval: 60 seconds (instead of disabled)  
# - Connection Stabilise Delay: 2.0 seconds (instead of 0.5)
```

#### 4. Enable Repair System
The integration includes automatic repair detection:
- Navigate to Settings → System → Repairs
- Look for RENKEI-related repair issues
- Follow repair flow instructions to apply fixes

### Commands Not Responding

**Symptoms:**
- Services complete without error but motor doesn't move
- Position updates not received
- Motor appears connected but unresponsive

**Diagnostic Steps:**

#### 1. Test Basic Communication
```yaml
# Try the jog service to test basic communication
service: renkei_poe.jog
target:
  entity_id: cover.your_motor
data:
  count: 1
```

#### 2. Check Motor Status
```yaml
# Get comprehensive motor status
service: renkei_poe.get_status
target:
  entity_id: cover.your_motor
```

#### 3. Review Status Information
Check logs for status response containing:
- `run_flags`: Should be 0 when idle
- `err_flags`: Should be 0 (check error code meanings below)
- `current_pos` vs `target_pos`: Should match when idle

#### 4. Common Error Codes
Motor error flags and their meanings:
- **Error 1**: Overcurrent protection triggered
- **Error 2**: Motor stall detected  
- **Error 3**: Position encoder failure
- **Error 4**: Communication timeout
- **Error 5**: Hardware fault

---

## Position and Movement Issues

### Inaccurate Position Reporting

**Symptoms:**
- Position shows 49% after restart instead of 50%
- Slight position drift over time
- Position doesn't match expected percentage

**Explanation & Solutions:**

#### 1. Encoder Rounding (Normal Behaviour)
**Cause**: Conversion between encoder values (0-65536) and percentages (0-100%)
**Impact**: ±1% accuracy typical
**Solution**: 
- This is normal behaviour due to mathematical rounding
- Use `absolute_move` service for precise positioning if needed
- Expect minor variations after Home Assistant restarts

#### 2. Mechanical Backlash
**Cause**: Normal mechanical play in motor gearing
**Impact**: Small position variations during direction changes
**Solution**:
- Allow motor to complete full movement before issuing new commands
- Consider mechanical tolerance in automation logic

#### 3. Encoder Calibration Issues
**Cause**: Motor limit positions not properly calibrated
**Symptoms**: Position percentages don't match physical position
**Solution**:
- Contact Dendo Systems for calibration procedures
- May require motor firmware update or factory reset

### Motor Doesn't Move to Expected Position

**Symptoms:**
- Motor stops before reaching target position
- Movement appears incomplete
- Position reports correctly but physical position is wrong

**Diagnostic Steps:**

#### 1. Check Physical Obstructions
- **Mechanical Binding**: Inspect motor mount and coupling
- **Physical Obstacles**: Check for objects blocking movement
- **Installation Issues**: Verify proper motor installation

#### 2. Verify Command Parameters
```yaml
# Test with explicit position command
service: renkei_poe.set_position
target:
  entity_id: cover.your_motor
data:
  position: 50  # Try a middle position
  delay: 0
```

#### 3. Check Motor Limits
- **Encoder Limits**: Physical limits may be less than 0-65536 range
- **Safety Stops**: Motor may have built-in position limits
- **Installation Limits**: Mechanical installation may restrict range

### Movement is Jerky or Inconsistent  

**Symptoms:**
- Motor starts and stops during movement
- Movement speed varies
- Unusual motor noises during operation

**Solutions:**

#### 1. Power Supply Issues
**Problem**: Insufficient PoE power causing motor to struggle
**Solution**:
- Verify PoE+ (802.3at) power supply
- Check total PoE budget on switch
- Test with dedicated PoE injector

#### 2. Network Communication Issues
**Problem**: Command interruptions due to network problems
**Solution**:
- Increase "Connection Stabilise Delay" setting
- Check for network congestion or interference
- Use wired connection instead of WiFi if applicable

#### 3. Mechanical Issues
**Problem**: Physical problems with motor or installation
**Solution**:
- Check motor mounting and coupling
- Verify proper load on motor (not overloaded)
- Contact Dendo Systems for hardware support

---

## Integration-Specific Issues

### Entities Show as "Unknown" State

**Symptoms:**
- Cover entity shows "unknown" state instead of open/closed
- Position attributes missing or show null values
- Integration appears connected but no status updates

**Solutions:**

#### 1. Force Status Update
```yaml
# Manually request status update
service: renkei_poe.get_status
target:
  entity_id: cover.your_motor
```

#### 2. Restart Integration
- Settings → Devices & Services → RENKEI Motor → Restart
- Wait 30 seconds for reconnection
- Check if status updates resume

#### 3. Reload Integration
- Remove and re-add the integration
- Use same IP address and configuration
- Monitor logs during setup for error messages

### Services Return Errors

**Common Error Messages:**

#### "Position is required"
**Cause**: Missing position parameter in service call
**Solution**: Include position parameter:
```yaml
service: renkei_poe.set_position
target:
  entity_id: cover.your_motor
data:
  position: 50  # Required parameter
```

#### "Position X is out of range (0-100)"
**Cause**: Invalid position value
**Solution**: Use valid range:
```yaml
service: renkei_poe.set_position
target:
  entity_id: cover.your_motor
data:
  position: 75  # Valid: 0-100
```

#### "Failed to move motor: Connection timeout"  
**Cause**: Network communication failure
**Solution**:
1. Check motor network connectivity
2. Verify motor power status
3. Try command again after a few seconds

#### "Unexpected error: Motor error 3"
**Cause**: Hardware error reported by motor
**Solution**:
1. Check motor status with `get_status` service
2. Power cycle the motor
3. Contact support if error persists

---

## Advanced Diagnostics

### Using Home Assistant Logs

#### Enable Debug Logging
```yaml
# Add to configuration.yaml for detailed logging
logger:
  default: info
  logs:
    custom_components.renkei_poe: debug
```

#### Common Log Patterns

**Successful Connection:**
```
DEBUG (MainThread) [custom_components.renkei_poe] Connection state changed to: CONNECTED
INFO (MainThread) [custom_components.renkei_poe] Motor connected successfully
```

**Connection Issues:**
```
ERROR (MainThread) [custom_components.renkei_poe] Failed to connect: [Errno 111] Connection refused
WARNING (MainThread) [custom_components.renkei_poe] Connection lost, attempting reconnection...
```

**Command Execution:**
```
DEBUG (MainThread) [custom_components.renkei_poe] Sending command: MOVE with position 50
DEBUG (MainThread) [custom_components.renkei_poe] Received response: {'response': 'MOVE', 'data': {...}}
```

### Network Analysis Tools

#### Basic Connectivity Testing
```bash
# Test ping connectivity
ping -c 4 {motor_ip}

# Test TCP port connectivity
telnet {motor_ip} 17002

# Advanced port testing
nmap -p 17002 {motor_ip}
```

#### Packet Capture Analysis
For deep network troubleshooting:
```bash
# Capture packets to/from motor (Linux/macOS)
sudo tcpdump -i any host {motor_ip} and port 17002

# On Windows with Wireshark
# Filter: ip.addr == {motor_ip} and tcp.port == 17002
```

### Motor Network Configuration

#### DHCP vs Static IP Issues
**Problem**: Motor IP address changes unexpectedly
**Solution**:
- Configure DHCP reservation for motor MAC address
- Or configure motor for static IP address
- Update Home Assistant configuration if IP changes

#### mDNS Service Analysis
```bash
# Linux/macOS: Browse mDNS services
avahi-browse -rt _dendo._tcp

# Expected output:
# + eth0 IPv4 RENKEI-A0B76531115B _dendo._tcp local
#    hostname = [RENKEI-A0B76531115B.local]
#    address = [192.168.1.100]
#    port = [17002]
```

---

## Performance Optimization

### Reducing Response Times

#### Connection Settings Optimization
- **Connection Stabilise Delay**: Reduce to 0.1s for faster response (if network is stable)
- **Health Check Interval**: Disable (set to 0) if not needed
- **Reconnect Interval**: Reduce to 5s for faster recovery

#### Network Optimization
- **Wired Connection**: Use Ethernet instead of WiFi for Home Assistant
- **Network Priority**: Configure QoS for motor traffic if needed
- **Switch Configuration**: Ensure full-duplex, no auto-negotiation issues

### Reducing Resource Usage

#### Minimize Status Polling
- Disable health check interval if connection is stable
- Avoid frequent `get_status` service calls in automations
- Use entity state changes instead of constant monitoring

#### Efficient Automation Design
```yaml
# Good: Use state-based triggers
automation:
  - trigger:
      platform: state
      entity_id: cover.your_motor
    condition:
      condition: template
      value_template: "{{ trigger.to_state.state != trigger.from_state.state }}"
    action:
      # Respond to actual state changes

# Avoid: Frequent manual status checks
# - service: renkei_poe.get_status  # Don't do this repeatedly
```

---

## Getting Additional Help

### Information to Collect

Before seeking support, gather:

1. **Home Assistant Version**: Settings → About
2. **Integration Version**: Check manifest.json or HACS
3. **Motor Information**: 
   - Model number and firmware version
   - Network configuration (IP, subnet)
   - Physical installation details
4. **Network Environment**:
   - Router/switch models
   - PoE power specifications
   - Network topology diagram if complex
5. **Diagnostic Data**: Download from integration settings
6. **Log Files**: Recent logs with debug level enabled

### Support Channels

#### GitHub Issues
- **Bug Reports**: [Report Issues](https://github.com/dendo-systems/renkei-poe-homeassistant/issues)
- **Feature Requests**: [Request Features](https://github.com/dendo-systems/renkei-poe-homeassistant/discussions)

#### Community Support  
- **Home Assistant Community**: [Community Forum](https://community.home-assistant.io/)
- **Reddit**: r/homeassistant with [RENKEI] tag
- **Discord**: Home Assistant Discord server

#### Professional Support
- **Dendo Systems**: [Official Support](https://dendosystems.com/support)
- **Local Installers**: For hardware and installation issues

### Creating Effective Support Requests

#### Include This Information:
1. **Clear Problem Description**: What you expected vs what happened
2. **Steps to Reproduce**: Exact sequence that causes the issue
3. **Environment Details**: HA version, network setup, motor model
4. **Log Excerpts**: Relevant error messages with timestamps
5. **Diagnostic Files**: Attach diagnostic download if requested

#### Avoid These Common Issues:
- Vague descriptions like "it doesn't work"
- Screenshots instead of text for log messages
- Missing version information
- No diagnostic data when requested

---

Remember: Most issues are related to network connectivity or power supply. Start with the basics before diving into complex troubleshooting procedures.