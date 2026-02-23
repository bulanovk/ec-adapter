# Modbus Protocol Definition

## Overview

ectoControl adapters communicate via Modbus RTU/TCP protocol. This document defines the register map and communication specifics.

## Connection Parameters

### Serial RTU

| Parameter | Default | Options |
|-----------|---------|---------|
| Baud Rate | 9600 | 9600, 19200, 38400, 57600, 115200 |
| Data Bits | 8 | 8 |
| Parity | N (None) | N, E (Even), O (Odd) |
| Stop Bits | 1 | 1, 2 |
| Response Timeout | 3s | 1-10s |

### TCP/UDP

| Parameter | Default | Description |
|-----------|---------|-------------|
| Port | 502 | Modbus TCP port |
| Response Timeout | 3s | 1-10s |

## Device Types

| Type ID | Name | Description |
|---------|------|-------------|
| 0x01 | OpenTherm v2 | OpenTherm boiler interface |
| 0x02 | eBus | eBus boiler interface |
| 0x03 | Navien | Navien boiler interface |
| 0x04 | Temperature Sensor | Multi-channel temperature sensor |
| 0x05 | OpenTherm v1 | Legacy OpenTherm interface |

## Generic Device Info Registers (All Types)

Registers 0x0000-0x0003 exist on all ectoControl devices for identification.

| Address | Name | Access | Type | Description |
|---------|------|--------|------|-------------|
| 0x0000 | Protocol Version | R | uint16 | Modbus protocol version |
| 0x0001 | Device UID High | R | uint16 | Bits 16-23 of 24-bit UID |
| 0x0002 | Device UID Low | R | uint16 | Bits 0-15 of 24-bit UID |
| 0x0003 | Device Descriptor | R | uint16 | MSB: Device Type, LSB: Channel Count |

### Device Descriptor Format (0x0003)

```
┌────────────────┬────────────────┐
│  Device Type   │  Channel Count │
│    (8 bits)    │    (8 bits)    │
└────────────────┴────────────────┘
      MSB (15-8)      LSB (7-0)
```

### Device UID Format (0x0001-0x0002)

```
0x0001: ┌────────┬────────┐
        │  UID   │  UID   │
        │[23:20] │[19:16] │
        └────────┴────────┘
              Bits 16-23

0x0002: ┌────────┬────────┐
        │  UID   │  UID   │
        │[15:8]  │[7:0]   │
        └────────┴────────┘
              Bits 0-15

Full UID = (0x0001[15:8] << 16) | (0x0001[7:0] << 8) | (0x0002[15:8])
```

## Register Map Template

### Read Registers (Input/Holding)

| Address Range | Purpose | Notes |
|---------------|---------|-------|
| 0x0000-0x000F | Device Info | Generic device identification |
| 0x0010-0x001F | System Status | Adapter status and diagnostics |
| 0x0020-0x003F | Channel 1 Data | Channel 1 sensor readings |
| 0x0040-0x005F | Channel 2 Data | Channel 2 sensor readings |
| 0x0060-0x007F | Channel 3 Data | Channel 3 sensor readings |
| ... | ... | ... |

### Write Registers (Holding)

| Address Range | Purpose | Notes |
|---------------|---------|-------|
| 0x0020-0x003F | Channel 1 Control | Channel 1 setpoints and modes |
| 0x0040-0x005F | Channel 2 Control | Channel 2 setpoints and modes |
| 0x0060-0x007F | Channel 3 Control | Channel 3 setpoints and modes |
| ... | ... | ... |

### Write Verification

Write operations have a status register at offset +1:

```
Write Address: 0x0020
Status Address: 0x0021 (0x0020 + 1)

Status Values:
  0x0000 = Idle/Pending
  0x5908 = Success (OK)
  Other  = Error code
```

## Common Registers

### Adapter Status (0x0010)

```
┌────────┬────────┬────────┬────────┬────────┬────────┬────────┬────────┐
│  Rsv   │  Rsv   │  Rsv   │  ERR   │  Rsv   │  Rsv   │  RST   │  CON   │
│  15    │  14    │  13    │  12    │  11    │  10    │  9-8   │  7-0   │
└────────┴────────┴────────┴────────┴────────┴────────┴────────┴────────┘

  CON (Bits 7-0):   Connection status code
  RST (Bits 9-8):   Last reboot reason
  ERR (Bit 12):     Error flag
```

### Temperature Registers

Temperature values are stored as int16 in tenths of degrees Celsius:

| Raw Value | Temperature |
|-----------|-------------|
| 0x0190 (400) | 40.0°C |
| 0x0384 (900) | 90.0°C |
| 0xFF9C (-100) | -10.0°C |

Formula: `Temperature(°C) = raw_value × 0.1`

### Percentage/Setpoint Registers

Percentage values are stored as uint16 (0-100%):

| Raw Value | Percentage |
|-----------|------------|
| 0x0000 (0) | 0% |
| 0x0032 (50) | 50% |
| 0x0064 (100) | 100% |

## Bitmask Definitions

### Enable/Disable Bits

```
Bit 0: Heating enable
Bit 1: DHW (Domestic Hot Water) enable
Bit 2: Second circuit enable
Bit 3: Cooling enable
...
```

### Mode Select

```
Bits 2-0: Operating mode
  000 = Off
  001 = Heating
  010 = DHW
  011 = Heating + DHW
  100 = Cooling
  ...
```

## Modbus Function Codes Used

| Code | Name | Usage |
|------|------|-------|
| 0x03 | Read Holding Registers | Read all registers |
| 0x10 | Write Multiple Registers | Write to control registers |

## Exception Codes

| Code | Name | Meaning |
|------|------|---------|
| 0x01 | Illegal Function | Function code not supported |
| 0x02 | Illegal Data Address | Register address invalid |
| 0x03 | Illegal Data Value | Data value out of range |
| 0x04 | Slave Device Failure | Internal device error |

## Communication Sequence

### Read Sequence

```
Master                          Slave
  │                               │
  │─── Read Holding Regs ────────►│
  │     (addr, count, slave_id)   │
  │                               │
  │◄── Register Values ───────────│
  │     (data)                    │
  │                               │
```

### Write Sequence

```
Master                          Slave
  │                               │
  │─── Write Multiple Regs ──────►│
  │     (addr, values, slave_id)  │
  │                               │
  │◄── Write Acknowledge ─────────│
  │                               │
  │─── Read Status Register ─────►│
  │                               │
  │◄── Status Value ──────────────│
  │     (0x5908 = success)        │
  │                               │
```

## Timing Requirements

| Parameter | Min | Typical | Max |
|-----------|-----|---------|-----|
| Inter-frame delay (RTU) | 3.5 char | - | - |
| Response timeout | 100ms | 1000ms | 10000ms |
| Turnaround delay | - | 100ms | 500ms |
| Status poll interval (after write) | - | 50ms | - |

## Implementation Notes

### Byte Order

All multi-register values use **Big Endian** (Modbus standard):
- Register 0x0001 value 0x1234 is transmitted as: 0x12 0x34

### Register Alignment

- All addresses are 16-bit aligned
- 32-bit values span 2 consecutive registers
- String values use consecutive registers (2 chars per register)

### Scaling

| Data Type | Scale Factor | Unit |
|-----------|--------------|------|
| Temperature | 0.1 | °C |
| Pressure | 0.01 | bar |
| Percentage | 1 | % |
| Flow Rate | 0.1 | L/min |
| Power | 1 | kW |
