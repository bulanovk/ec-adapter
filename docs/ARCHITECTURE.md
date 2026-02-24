# Architecture Design

## Overview

The ectoControl Adapter is a Home Assistant custom component that integrates ectoControl adapters for controlling gas and electric boilers via Modbus. This document describes the system architecture and design decisions.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Home Assistant                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        Config Entry 1                                │    │
│  │  ┌────────────────────┐    ┌────────────────────────────────────┐   │    │
│  │  │ MasterCoordinator  │    │ DataUpdateCoordinator (per interval)│   │    │
│  │  │   (slave ID: 1)    │    │  • 15s group                       │   │    │
│  │  └─────────┬──────────┘    │  • 60s group                       │   │    │
│  │            │               └────────────────────────────────────┘   │    │
│  │            │                                                        │    │
│  ├────────────┼────────────────────────────────────────────────────────┤    │
│  │            │                                                        │    │
│  │  ┌─────────▼──────────┐                                             │    │
│  │  │ ModbusClientPool   │◄───────────────────────────────────────────┤    │
│  │  │                    │    Shared across all config entries        │    │
│  │  │ ┌────────────────┐ │                                             │    │
│  │  │ │ PooledClient   │ │    ┌───────────────────────────────────┐  │    │
│  │  │ │                │ │    │ PooledClient (per connection)     │  │    │
│  │  │ │ • Modbus Client│ │    │ • Async Operation Queue          │  │    │
│  │  │ │ • Async Queue  │ │    │ • Reference Counting             │  │    │
│  │  │ │ • Ref Count: N │ │    │ • Connection Lifecycle           │  │    │
│  │  │ └────────────────┘ │    └───────────────────────────────────┘  │    │
│  │  └────────────────────┘                                             │    │
│  │            │                                                        │    │
│  └────────────┼────────────────────────────────────────────────────────┘    │
│               │                                                              │
│               ▼                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      Connection Layer                                │    │
│  │  ┌─────────┐  ┌─────────┐  ┌──────────────┐  ┌───────────────────┐  │    │
│  │  │ Serial  │  │   TCP   │  │     UDP      │  │  RTU-over-TCP     │  │    │
│  │  │ RTU     │  │  Modbus │  │   Modbus     │  │                   │  │    │
│  │  └─────────┘  └─────────┘  └──────────────┘  └───────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│               │                                                              │
└───────────────┼──────────────────────────────────────────────────────────────┘
                │
                ▼
        ┌───────────────┐
        │  ectoControl  │
        │    Adapter    │
        │   (RS-485)    │
        └───────────────┘
```

## Core Components

### 1. ModbusClientPool (`pool.py`)

A singleton that manages shared Modbus connections.

**Responsibilities:**
- Create and manage `PooledClient` instances keyed by connection configuration
- Thread-safe acquire/release with reference counting
- Clean up unused connections

**Pool Key Format:**
| Connection Type | Pool Key Format |
|-----------------|-----------------|
| Serial | `serial:{device}:{baudrate}:{parity}:{stopbits}:{bytesize}` |
| TCP | `tcp:{host}:{port}` |
| UDP | `udp:{host}:{port}` |
| RTU-over-TCP | `rtuovertcp:{host}:{port}` |

### 2. PooledClient (`pool.py`)

Holds a shared Modbus connection with operation serialization.

**Responsibilities:**
- Manage Modbus client lifecycle (connect/disconnect)
- Serialize operations through async queue
- Reference counting for connection sharing

**Lifecycle:**
```
ref_count: 0 → 1     : Connect to device, start queue processor
ref_count: N → N+1   : Increment counter only
ref_count: N → N-1   : Decrement counter
ref_count: 1 → 0     : Disconnect, stop queue processor
```

### 3. ModbusMasterCoordinator (`master.py`)

Per-entry coordinator that delegates to a `PooledClient`.

**Responsibilities:**
- Provide read/write API for coordinators and entities
- Handle write verification with status register polling
- Manage device-specific slave ID

### 4. ModbusDataUpdateCoordinator (`coordinator.py`)

Polls registers at configured intervals.

**Responsibilities:**
- Group registers by scan interval
- Poll registers and cache data
- Notify entities of data updates

## Data Flow

### Read Operation Flow

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Sensor Entity   │     │ DataUpdateCoord. │     │ MasterCoordinator│
└────────┬─────────┘     └────────┬─────────┘     └────────┬─────────┘
         │                        │                        │
         │  async_update()        │                        │
         │───────────────────────►│                        │
         │                        │                        │
         │                        │  read_holding_regs()   │
         │                        │───────────────────────►│
         │                        │                        │
         │                        │                        │  submit_operation()
         │                        │                        │──────────►
         │                        │                        │            │
         │                        │                        │            ▼
         │                        │                        │      ┌─────────────┐
         │                        │                        │      │PooledClient │
         │                        │                        │      │   Queue     │
         │                        │                        │      └─────────────┘
         │                        │                        │            │
         │                        │                        │  ◄─────────┘
         │                        │  ◄─────────────────────│
         │  ◄─────────────────────│                        │
         │                        │                        │
```

### Write Operation Flow

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Switch Entity   │     │ MasterCoordinator│     │  PooledClient    │
└────────┬─────────┘     └────────┬─────────┘     └────────┬─────────┘
         │                        │                        │
         │  async_turn_on()       │                        │
         │───────────────────────►│                        │
         │                        │                        │
         │                        │  write_registers()     │
         │                        │───────────────────────►│
         │                        │                        │
         │                        │  _verify_write_status()│
         │                        │───────────────────────►│
         │                        │     (poll status reg)  │
         │                        │                        │
         │  ◄─────────────────────│  return success/fail   │
         │                        │                        │
```

## Entity Generation

Entities are auto-generated from register definitions, not manually coded.

### Generation Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ registers.py    │     │ async_setup_    │     │ Platform Setup  │
│ REGISTERS_R/W   │     │ entry()         │     │ (sensor.py,etc) │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         │ Register configs      │                       │
         │──────────────────────►│                       │
         │                       │                       │
         │                       │ Filter by device type │
         │                       │ Group by scan interval│
         │                       │                       │
         │                       │ Pass to platform setup│
         │                       │──────────────────────►│
         │                       │                       │
         │                       │                       │ Generate entities
         │                       │                       │ from register config
```

### Register to Entity Mapping

| Register Config | Platform | Entity Type |
|-----------------|----------|-------------|
| `REGISTERS_R` entry | `sensor.py` | Sensor |
| `bitmasks[type=BM_BINARY]` | `binary_sensor.py` | BinarySensor |
| `bitmasks[type=BM_VALUE]` | `sensor.py` | Sensor |
| `converters` | `sensor.py` | Sensor (derived) |
| `REGISTERS_W[input_type=NUMBER_INPUT]` | `number.py` | Number |
| `REGISTERS_W[input_type=SELECT_INPUT]` | `select.py` | Select |
| `REGISTERS_W[input_type=SWITCH_INPUT]` | `switch.py` | Switch |
| `REGISTERS_W[input_type=BITMASK_SWITCH_INPUT]` | `switch.py` | Switch (per-bit) |
| `REGISTERS_W[input_type=BUTTON_INPUT]` | `button.py` | Button |

## Device Type Detection

Device type is detected during setup by reading generic registers:

| Register | Address | Content |
|----------|---------|---------|
| Device UID | 0x0001-0x0002 | 24-bit unique identifier |
| Device Type | 0x0003 (MSB) | Adapter type identifier |
| Channel Count | 0x0003 (LSB) | Number of channels |

Detection determines which registers are available for the device.

### Device Variants

Some device types have variants based on channel count. These use composite keys as tuples `(device_type_code, channel_count)`:

| Device Type | Composite Key | Description |
|-------------|---------------|-------------|
| Contact Splitter 8ch | `(0x59, 8)` | 8-channel variant, register 0x0010 only |
| Contact Splitter 10ch | `(0x59, 10)` | 10-channel variant, registers 0x0010-0x0011 |

The detection logic in `__init__.py` maps the base device type and channel count to the appropriate variant definition in `DEVICE_TYPE_DEFS`.

## Error Handling

### Connection Errors

1. **PooledClient reconnects automatically** on next operation if connection lost
2. **DataUpdateCoordinator raises `UpdateFailed`** on read errors
3. **Entities show unavailable** when coordinator fails

### Write Verification

Writes are verified by polling a status register:
1. Write to register at address N
2. Poll status register at address N + offset
3. Retry up to `max_retries` times
4. Return success/failure to entity

## Configuration Flow

### Adding First Device

```
User fills form → check_user_input()
                       │
                       ├─ pool.get(key) → None
                       │
                       ├─ Create temporary client
                       ├─ Connect & validate
                       └─ Close client
                       │
                  async_setup_entry()
                       │
                       ├─ pool.acquire() → Create PooledClient
                       └─ Setup coordinators & entities
```

### Adding Subsequent Device (same port)

```
User fills form → check_user_input()
                       │
                       ├─ pool.get(key) → PooledClient EXISTS
                       │
                       ├─ Reuse pooled connection
                       └─ Validate via existing queue
                       │
                  async_setup_entry()
                       │
                       ├─ pool.acquire() → ref_count++
                       └─ Setup coordinators & entities
```

## Design Decisions

### Why Connection Pooling?

1. **Serial ports require exclusive access** - Only one process can hold the lock
2. **Multiple devices on RS-485 bus** - Different slave IDs share the same physical connection
3. **Resource efficiency** - Avoid duplicating connections and queues

### Why Async Queue per PooledClient?

1. **Serialize Modbus operations** - Prevent concurrent requests on same connection
2. **Request/response correlation** - Each operation gets its own future
3. **Backpressure** - Queue naturally limits concurrent operations

### Why Reference Counting?

1. **Dynamic entry management** - Entries can be added/removed at runtime
2. **Resource cleanup** - Connection closes when no longer needed
3. **Safe sharing** - Multiple entries can safely share connection
