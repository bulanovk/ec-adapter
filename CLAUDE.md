# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Home Assistant custom component that integrates ectoControl adapters for controlling gas and electric boilers via Modbus (TCP, UDP, Serial, RTU-over-TCP protocols). The integration supports eBUS, OpenTherm, and Navien boiler protocols.

**Component location:** `custom_components/ectocontrol_adapter/`

**External dependency:** pymodbus==3.11.2

## Architecture

### Dual Coordinator Pattern

The integration uses a two-tier coordinator architecture:

1. **ModbusMasterCoordinator** (`master.py`) - Singleton that manages the Modbus connection and serializes all Modbus operations through an async queue. Prevents concurrent access issues.
2. **ModbusDataUpdateCoordinator** (`coordinator.py`) - Multiple instances, one per scan interval group. Polls read registers and caches data for sensor entities.

Key implication: All read operations go through data coordinators, while write operations go directly through the master coordinator.

### Entity Generation Pattern

Entities are **auto-generated** from register definitions in `registers.py`, not manually coded. The `REGISTERS_R` dict defines read registers, `REGISTERS_W` defines write registers.

Each register config can generate multiple entities through:
- **bitmasks**: Extract individual bits or bit fields from a register value (BM_BINARY for binary sensors, BM_VALUE for sensor values)
- **converters**: Transform raw data into derived values (e.g., uptime_to_boottime)

### Platform Entity Types

| Type | File | Usage |
|------|------|-------|
| Sensor | `sensor.py` | Generated from `REGISTERS_R`, supports bitmask value extraction and converters |
| Binary Sensor | `binary_sensor.py` | Generated from bitmask config with `type: BM_BINARY` |
| Number | `number.py` | Generated from `REGISTERS_W` with `input_type: NUMBER_INPUT` |
| Select | `select.py` | Generated from `REGISTERS_W` with `input_type: SELECT_INPUT` |
| Switch | `switch.py` | Generated from `REGISTERS_W` with `input_type: SWITCH_INPUT` or `BITMASK_SWITCH_INPUT` |
| Button | `button.py` | Generated from `REGISTERS_W` with `input_type: BUTTON_INPUT` |

### Device Type Detection

The integration automatically detects the connected device type during setup by reading generic device info registers (0x0000-0x0003):
- **Device Type** (MSB of register 0x0003): Identifies the adapter type (OpenTherm v2, eBus, Navien, Temperature Sensor, etc.)
- **Device UID** (registers 0x0001-0x0002): 24-bit unique identifier for each adapter
- **Channel Count** (LSB of register 0x0003): Number of channels supported by the device

Register configurations are filtered based on the detected device type using `DEVICE_TYPE_DEFS` in `registers.py`. This allows different device types to expose different entities based on their capabilities.

### Write Verification

Write operations verify success by polling a status register (offset by `REG_STATUS_OFFSET` from the write address). The master coordinator retries reads up to `REG_DEFAULT_MAX_RETRIES` times with `REG_DEFAULT_RETRY_DELAY` delay.

### Auto-Write on Reconnect

Some number entities have `write_after_connected` configuration that causes them to automatically write their value when the adapter connectivity binary sensor turns on. This ensures boiler parameters are restored after reconnection.

## Register Configuration Reference

### Read Register Fields

```python
{
    "name": "entity_name",              # Translation key
    "count": 1,                         # Number of Modbus registers
    "data_type": "uint16",              # For struct unpacking (see REG_TYPE_MAPPING)
    "input_type": "holding",            # Always "holding" for this integration
    "scan_interval": 15,                # Seconds (groups registers by interval)
    "scale": 0.1,                       # Multiply unpacked value by this
    "unit_of_measurement": UnitOfTemperature.CELSIUS,
    "device_class": SensorDeviceClass.TEMPERATURE,
    "icon": "mdi:thermometer",
    "category": EntityCategory.DIAGNOSTIC,
    "bitmasks": { ... },                # Create additional entities
    "converters": { ... }               # Create derived value entities
}
```

### Bitmask Configuration

```python
bitmasks: {
    0x0800: {
        "type": BM_BINARY,              # Creates binary_sensor
        "name": "connectivity",
        "device_class": BinarySensorDeviceClass.CONNECTIVITY
    },
    0x00FF: {
        "type": BM_VALUE,               # Creates additional sensor
        "name": "last_reboot_code",
        "rshift": 0                     # Optional: right-shift before use
    }
}
```

### Write Register Fields

```python
{
    "name": "entity_name",
    "input_type": NUMBER_INPUT,         # NUMBER_INPUT, SELECT_INPUT, SWITCH_INPUT, BUTTON_INPUT, BITMASK_SWITCH_INPUT
    "min_value": 0,                     # For numbers
    "max_value": 100,
    "initial_value": 40,
    "step": 1,
    "scale": 10,                        # User value multiplied before writing
    "unit_of_measurement": UnitOfTemperature.CELSIUS,
    "choices": { "label": value },      # For selects
    "buttons": [ ... ],                 # For buttons
    "bit_switches": [ ... ],            # For bitmask switches
    "write_after_connected": (REG_R_ADDR, "sensor_name"),  # Auto-write on reconnect
    "status_register": REG_R_ADDR,      # For buttons: verify success
    "icon": "mdi:thermometer",
    "category": EntityCategory.CONFIG
}
```

### Bitmask Switch Configuration

Bitmask switches allow controlling individual bits within a single register. Each bit creates a separate switch entity:

```python
REG_W_CIRCUIT_ENABLE = 0x003A

REGISTERS_W = {
    REG_W_CIRCUIT_ENABLE: {
        "name": "circuit_enable",
        "input_type": BITMASK_SWITCH_INPUT,
        "bit_switches": [
            {
                "bit": 0,
                "name": "heating_enable",
                "icon": "mdi:heating-coil",
            },
            {
                "bit": 1,
                "name": "dhw_enable",
                "icon": "mdi:water-pump",
            },
            {
                "bit": 2,
                "name": "second_circuit_enable",
                "icon": "mdi:heating-coil",
            },
        ]
    },
}
```

This creates three independent switch entities that control bits 0, 1, and 2 of register 0x003A using read-modify-write operations.

## Code Style

- Line length: 119 characters (`.flake8`)
- Max complexity: 15
- F405 (unused import) is ignored for `from .const import *`

## Common Development Tasks

### Adding a New Read Register

1. Define the register address constant in `registers.py`
2. Add entry to `REGISTERS_R` dict with appropriate configuration
3. No code changes needed - entities auto-generated

### Adding a New Write Register

1. Define the register address constant in `registers.py`
2. Add entry to `REGISTERS_W` dict with appropriate configuration
3. No code changes needed - entities auto-generated

### Adding a New Converter

1. Create converter function in `converters.py`
2. Add `converters` dict to register config with converter and output entity config

### Adding a New Device Type

To add support for a new device type:

1. Add device type constant to `const.py`:
   ```python
   DEVICE_TYPE_NEW_DEVICE = 0xXX
   ```

2. Add device type name to `DEVICE_TYPE_NAMES` in `const.py`

3. Define device-specific registers in `registers.py` (if needed):
   ```python
   REG_R_NEW_DEVICE_SPECIFIC = 0x00XX
   ```

4. Add device type definition to `DEVICE_TYPE_DEFS` in `registers.py`:
   ```python
   DEVICE_TYPE_DEFS = {
       # ... existing types ...
       DEVICE_TYPE_NEW_DEVICE: {
           "name": "New Device",
           "read_registers": {
               # Device-specific read registers
               REG_R_ADAPTER_STATUS: REGISTERS_R[REG_R_ADAPTER_STATUS],
               REG_R_NEW_DEVICE_SPECIFIC: {
                   "name": "new_sensor",
                   "count": 1,
                   "data_type": "uint16",
                   "input_type": "holding",
                   "scan_interval": 15,
               },
           },
           "write_registers": {
               # Device-specific write registers
           },
       },
   }
   ```

The integration will automatically detect the device type and create entities based on the configured registers.
