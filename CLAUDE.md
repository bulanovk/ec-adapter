# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Documentation

- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture and design
- **[docs/PROTOCOL.md](docs/PROTOCOL.md)** - Modbus protocol and register definitions
- **[docs/README.md](docs/README.md)** - Documentation index

## Project Overview

This is a Home Assistant custom component that integrates ectoControl adapters for controlling gas and electric boilers via Modbus (TCP, UDP, Serial, RTU-over-TCP protocols). The integration supports eBUS, OpenTherm, and Navien boiler protocols.

**Component location:** `custom_components/ectocontrol_adapter/`

**External dependency:** pymodbus==3.11.2

## File Structure

| File | Purpose |
|------|---------|
| `__init__.py` | Integration setup, pool initialization, entry lifecycle |
| `pool.py` | Connection pooling with reference counting |
| `master.py` | ModbusMasterCoordinator - delegates to pooled client |
| `coordinator.py` | ModbusDataUpdateCoordinator - polls registers |
| `config_flow.py` | UI configuration flow with pool-aware validation |
| `registers.py` | Register definitions and device type configurations |
| `const.py` | Constants and configuration options |
| `helpers.py` | Modbus client factory |
| `converters.py` | Data transformation functions |
| `sensor.py` | Sensor entity generation |
| `binary_sensor.py` | Binary sensor entity generation |
| `number.py` | Number input entity generation |
| `select.py` | Select dropdown entity generation |
| `switch.py` | Switch entity generation |
| `button.py` | Button entity generation |

## Architecture

### Connection Pooling

The integration uses a connection pooling system to allow multiple devices to share the same serial port or network connection:

1. **ModbusClientPool** (`pool.py`) - Singleton that manages shared connections keyed by connection configuration (e.g., `serial:/dev/pts/3:9600:N:1:8` or `tcp:192.168.1.100:502`)
2. **PooledClient** (`pool.py`) - Holds the actual Modbus client, async operation queue, and reference count. Serializes all Modbus operations to prevent concurrent access issues.

**Key concepts:**
- Multiple config entries with the same connection settings share one `PooledClient`
- Each `PooledClient` has a reference count - connects on first acquire, disconnects on last release
- All operations are serialized through an async queue within each `PooledClient`
- Different slave IDs are distinguished via the `device_id` parameter in each Modbus request
- Config flow reuses existing pooled connections for validation (no port lock conflicts)

```
Entry 1 (slave 1) ─┐
Entry 2 (slave 2) ─┼──► PooledClient ──► Single Serial Port Lock
Entry 3 (slave 3) ─┘         │
                             ▼
                    Operation Queue (serialized)
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
         device_id=1    device_id=2    device_id=3
```

### Dual Coordinator Pattern

The integration uses a two-tier coordinator architecture:

1. **ModbusMasterCoordinator** (`master.py`) - Wrapper that delegates Modbus operations to a `PooledClient`. Each config entry has its own instance, but they share the underlying pooled connection.
2. **ModbusDataUpdateCoordinator** (`coordinator.py`) - Multiple instances, one per scan interval group. Polls read registers and caches data for sensor entities.

Key implication: All read operations go through data coordinators, while write operations go directly through the master coordinator. All operations are serialized through the shared `PooledClient` queue.

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

### Pool Key Generation

Pool keys uniquely identify connections for sharing:

| Connection Type | Pool Key Format |
|-----------------|-----------------|
| Serial | `serial:{device}:{baudrate}:{parity}:{stopbits}:{bytesize}` |
| TCP | `tcp:{host}:{port}` |
| UDP | `udp:{host}:{port}` |
| RTU-over-TCP | `rtuovertcp:{host}:{port}` |

Example: `serial:/dev/pts/3:9600:N:1:8`

### Reference Counting Lifecycle

```
async_setup_entry()     → pool.acquire()  → ref_count++ (connect if first)
                                              ↓
                                        [Device Operating]
                                              ↓
async_unload_entry()    → pool.release()  → ref_count-- (disconnect if last)
```

### Auto-Write on Reconnect

Some number entities have `write_after_connected` configuration that causes them to automatically write their value when the adapter connectivity binary sensor turns on. This ensures boiler parameters are restored after reconnection.

### Config Flow Validation

The config flow validates device connectivity before creating an entry:

1. **First device on a port**: Creates a temporary client, validates, then closes it
2. **Subsequent devices on same port**: Reuses existing pooled connection for validation

This prevents port lock conflicts when adding multiple devices on the same serial port.

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

## Debugging

### Transport-Level Logging

To see actual Modbus requests/responses, enable pymodbus logging in Home Assistant's `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.ectocontrol_adapter: debug
    pymodbus: debug
```

For more granular transport logging:
```yaml
logger:
  logs:
    pymodbus.client: debug
    pymodbus.framer: debug
    pymodbus.pdu: debug
```

### Adding New Modbus Operations

When adding a new operation type (e.g., `read_input_registers`), update **both**:
1. `master.py` - Add the method that calls `submit_operation()`
2. `pool.py` - Add handler in `_execute_client_operation()` (easy to miss!)

The pool serializes all operations, so unhandled operation types will throw "Unknown operation type" errors.

### Register Input Types

| input_type | Function Code | Description |
|------------|---------------|-------------|
| `"holding"` | 0x03 | Read holding registers |
| `"input"` | 0x04 | Read input registers (read-only) |

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
