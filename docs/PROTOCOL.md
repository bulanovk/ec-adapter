# Ectocontrol Modbus Protocol Specification

**Version:** 1.0
**Last Updated:** February 2025
**Based on:** Official Ectostroy Protocol Documentation (Russian)

---

## Table of Contents

1. [Protocol Overview](#1-protocol-overview)
2. [Communication Parameters](#2-communication-parameters)
3. [Modbus Function Codes](#3-modbus-function-codes)
4. [Generic Device Information](#4-generic-device-information)
5. [Device Types](#5-device-types)
6. [Register Maps by Device Type](#6-register-maps-by-device-type)
   - [6.1 Boiler Adapters (OpenTherm/eBus/Navien)](#61-boiler-adapters-openterm-ebus-navien)
   - [6.2 Contact Sensor Splitter](#62-contact-sensor-splitter)
   - [6.3 Temperature/Humidity Sensors](#63-temperaturehumidity-sensors)
   - [6.4 Relay Control Blocks](#64-relay-control-blocks)
7. [Data Types and Scaling](#7-data-types-and-scaling)
8. [Invalid/Unsupported Value Markers](#8-invalidunsupported-value-markers)
9. [Error Handling](#9-error-handling)
10. [Implementation Notes](#10-implementation-notes)

---

## 1. Protocol Overview

The Ectocontrol system uses Modbus RTU protocol over RS-485 for communication with adapters and sensors. All devices act as Modbus slaves, responding to requests from a master device (Home Assistant, Ectocontrol system, etc.).

### Key Characteristics

| Characteristic | Value |
|---------------|-------|
| **Protocol** | Modbus RTU |
| **Interface** | RS-485 half-duplex |
| **Baud Rate** | 19200 bps |
| **Data Bits** | 8 |
| **Parity** | None |
| **Stop Bits** | 1 |
| **Slave ID Range** | 1-32 (0x01-0x20) |
| **Response Timeout** | 2-5 seconds |

### Wiring

The 4P4C connector pinout:
| Pin | Signal |
|-----|--------|
| 1 | +12V (7-14V DC) |
| 2 | GND |
| 3 | A (RS-485) |
| 4 | B (RS-485) |

---

## 2. Communication Parameters

### Serial Configuration

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Baud Rate** | 19200 | Fixed |
| **Data Bits** | 8 | |
| **Parity** | None (N) | |
| **Stop Bits** | 1 | |
| **Mode** | Half-duplex | Requires operation serialization |
| **Timeout** | 2-5 seconds | Depends on device response time |

### TCP/UDP Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| **Port** | 502 | Standard Modbus TCP port |
| **Timeout** | 3-5s | Response timeout |

---

## 3. Modbus Function Codes

The Ectocontrol protocol uses the following Modbus function codes:

| Code | Name | Usage |
|------|------|-------|
| **0x03** | Read Holding Registers | Read configuration and status registers |
| **0x04** | Read Input Registers | Read sensor data (contact states, temperatures) |
| **0x06** | Write Single Register | Write to control registers |
| **0x10** | Write Multiple Registers | Write multiple control registers |
| **0x46** | PROG_READ | Read device address (programming mode) |
| **0x47** | PROG_WRITE | Write device address (programming mode) |

### Access Type Notation

| Notation | Meaning | Function Code |
|----------|---------|---------------|
| **R** | Read-only | 0x04 (Input Registers) |
| **RW** | Read/Write | 0x03/0x10 (Holding Registers) |
| **W** | Write-only | 0x06/0x10 (Holding Registers) |

---

## 4. Generic Device Information

All Ectocontrol devices share a common information structure at addresses 0x0000-0x0003.

**Register Type:** Holding Registers (Function 0x03)

| Address | Byte | Field | Access | Description |
|---------|------|-------|--------|-------------|
| 0x0000 | 0 | RSVD | R | Reserved |
| 0x0000 | 1 | UID[0] | R | UID MSB (bits 23:16) |
| 0x0001 | 0 | UID[1] | R | UID middle (bits 15:8) |
| 0x0001 | 1 | UID[2] | R | UID LSB (bits 7:0) |
| 0x0002 | 0 | RSVD | R | Reserved |
| 0x0002 | 1 | ADDR | R | Device Modbus address (0x01-0x20) |
| 0x0003 | 0 | TYPE | R | Device type code |
| 0x0003 | 1 | CHN_CNT | R | Channel count (1-10) |

### UID Format

The 24-bit Unique Identifier (UID) is encoded across registers 0x0000-0x0001:

```
Register 0x0000: [RSVD:8][UID[0]:8]   → LSB contains UID MSB
Register 0x0001: [UID[1]:8][UID[2]:8] → MSB=UID middle, LSB=UID LSB

Example: UID = 0x8ABCDE
  Register 0x0000 = 0x008A (RSVD=0x00, UID[0]=0x8A)
  Register 0x0001 = 0xBCDE (UID[1]=0xBC, UID[2]=0xDE)
```

**Python extraction:**
```python
uid_msb = regs[0] & 0xFF           # UID[0] from 0x0000 LSB
uid_mid = (regs[1] >> 8) & 0xFF    # UID[1] from 0x0001 MSB
uid_lsb = regs[1] & 0xFF           # UID[2] from 0x0001 LSB
device_uid = (uid_msb << 16) | (uid_mid << 8) | uid_lsb
```

**Valid UID Range:** 0x800000 to 0xFFFFFF

---

## 5. Device Types

Device type is read from the MSB of register 0x0003.

### Boiler Adapters

| Code | Name | Description |
|------|------|-------------|
| 0x11 | OpenTherm Adapter v1 | Discontinued, blue PCB |
| **0x14** | **OpenTherm Adapter v2** | Current version, yellow PCB |
| 0x15 | eBus Adapter | For boilers with eBus interface |
| 0x16 | Navien Adapter | For Navien boilers |

### Sensors

| Code | Name | Description |
|------|------|-------------|
| 0x22 | Temperature Sensor | Multi-channel temperature sensor |
| 0x23 | Humidity Sensor | Multi-channel humidity sensor |
| 0x50 | Contact Sensor | Universal single contact sensor |
| **0x59** | **Contact Splitter** | 10-channel contact sensor splitter |

### Control Devices

| Code | Name | Description |
|------|------|-------------|
| 0xC0 | Relay Block 2ch | 2-channel relay control block |
| 0xC1 | Relay Block 10ch | 10-channel relay control block |

---

## 6. Register Maps by Device Type

### 6.1 Boiler Adapters (OpenTherm/eBus/Navien)

**Device Types:** 0x14, 0x15, 0x16
**Register Type:** Holding Registers (Function 0x03)

#### Read Registers

| Address | MSB | LSB | Access | Description |
|---------|-----|-----|--------|-------------|
| **0x0010** | Adapter Type (bits 2-0) + Comm Status (bit 3) | Last Reboot Code (u8) | R | Status register |
| **0x0011** | HW Version (u8) | SW Version (u8) | R | Adapter versions |
| **0x0012** | Uptime (u32, high word) | | R | Adapter uptime in seconds |
| **0x0013** | Uptime (u32, low word) | | R | Adapter uptime in seconds |
| **0x0014** | - | Coolant Min Temp (u8) | R | Lower coolant temp limit (°C) |
| **0x0015** | - | Coolant Max Temp (u8) | R | Upper coolant temp limit (°C) |
| **0x0016** | - | DHW Min Temp (u8) | R | Lower DHW temp limit (°C) |
| **0x0017** | - | DHW Max Temp (u8) | R | Upper DHW temp limit (°C) |
| **0x0018** | Coolant Temperature (i16) | | R | Current coolant temp (÷10 = °C) |
| **0x0019** | DHW Temperature (u16) | | R | Current DHW temp (÷10 = °C) |
| **0x001A** | - | Pressure (u8) | R | System pressure (÷10 = bar) |
| **0x001B** | - | Flow Rate (u8) | R | DHW flow rate (÷10 = L/min) |
| **0x001C** | - | Modulation (u8) | R | Burner modulation (0-100%) |
| **0x001D** | - | States (bitfield) | R | Burner/Heating/DHW states |
| **0x001E** | Main Error (u16) | | R | Boiler error code (primary) |
| **0x001F** | AddError (u16) | | R | Boiler error code (additional) |
| **0x0020** | - | Outdoor Temp (s8) | R | Outdoor temperature (°C) |
| **0x0021** | Manufacturer Code (u16) | | R | Boiler manufacturer ID |
| **0x0022** | Model Code (u16) | | R | Boiler model ID |
| **0x0023** | - | OT Error Flags (s8) | R | OpenTherm error flags |

#### Status Register (0x0010) Bitfield

```
MSB (bits 15-8): Last Reboot Code (u8)
  0 = Normal startup
  1-255 = Various reset codes

LSB (bits 7-0):
  Bits 2-0: Adapter Type
    000 = OpenTherm
    001 = eBus
    010 = Navien
    011-111 = Reserved

  Bit 3: Boiler Communication Status
    0 = No response from boiler to last command
    1 = Response received from boiler to last command

  Bits 7-4: Reserved
```

#### States Register (0x001D) Bitfield

```
Bit 0: Burner state (0=off, 1=on)
Bit 1: Heating enabled (0=no, 1=yes)
Bit 2: DHW enabled (0=no, 1=yes)
Bits 7-3: Reserved
```

#### Write Registers

| Address | MSB | LSB | Access | Description |
|---------|-----|-----|--------|-------------|
| **0x0030** | - | Connection Type (u8) | W | 0=adapter to boiler, 1=boiler to external |
| **0x0031** | Coolant Setpoint (i16) | | W | Target CH temp (×10, saved to EPROM) |
| **0x0032** | Emergency Setpoint (i16) | | W | Emergency CH temp (×10) |
| **0x0033** | - | CH Min Limit (u8) | W | CH minimum temp (°C) |
| **0x0034** | - | CH Max Limit (u8) | W | CH maximum temp (°C) |
| **0x0035** | - | DHW Min Limit (u8) | W | DHW minimum temp (°C) |
| **0x0036** | - | DHW Max Limit (u8) | W | DHW maximum temp (°C) |
| **0x0037** | - | DHW Setpoint (u8) | W | DHW target temp (°C, saved to EPROM) |
| **0x0038** | - | Max Modulation (u8) | W | Max burner modulation (0-100%) |
| **0x0039** | - | Circuit Enable (bitfield) | W | Heating/DHW enable bits |

#### Circuit Enable Register (0x0039) Bitfield

```
Bit 0: Heating circuit enable (0=off, 1=on)
Bit 1: DHW circuit enable (0=off, 1=on)
Bit 2: Second circuit enable (OpenTherm only, for indirect boiler)
Bits 15-3: Reserved (write as 0)
```

#### Register Health Status (0x0040-0x006F)

Status registers for data registers 0x0010-0x003F. Status for register R is at address R + 0x30.

| Value | Meaning |
|-------|---------|
| -2 | Read/write error with boiler |
| -1 | Register not supported by boiler |
| 0 | Data valid (read) / Accepted by boiler (write) |
| 1 | Not initialized |

#### Command Registers

| Address | Type | Access | Description |
|---------|------|--------|-------------|
| **0x0080** | u16 | W | Command register |
| **0x0081** | i16 | R | Command result |

**Command Codes (0x0080):**
| Value | Command |
|-------|---------|
| 0 | No command (default) |
| 1 | CH water filling (reserved) |
| 2 | Reboot adapter |
| 3 | Reset boiler errors |
| 4-65525 | Reserved |

**Command Results (0x0081):**
| Value | Meaning |
|-------|---------|
| -5 | Command execution error |
| -4 | Command not supported by boiler |
| -3 | Device ID not supported by boiler |
| -2 | Command not supported by adapter |
| -1 | Timeout (no response) |
| 0 | Success |
| 1 | No command (default after reboot) |
| 2 | Processing |

---

### 6.2 Contact Sensor Splitter

**Device Type:** 0x59
**Register Type:** **INPUT Registers** (Function 0x04)

> **IMPORTANT:** Contact Splitter uses INPUT registers (function code 0x04), NOT holding registers!
> The Contact Splitter does NOT have adapter status/version/uptime registers like boiler adapters.

#### Home Assistant Entities

Each channel is exposed as a **binary sensor** with:
- **Device class:** `opening` (on=closed, off=open)
- **Scan interval:** 5 seconds
- **Translation keys:** `contact_1` through `contact_10`

| Entity | Translation (EN) | Translation (RU) |
|--------|------------------|------------------|
| contact_1 | Contact Sensor 1 | Контактный датчик 1 |
| contact_2 | Contact Sensor 2 | Контактный датчик 2 |
| contact_3 | Contact Sensor 3 | Контактный датчик 3 |
| contact_4 | Contact Sensor 4 | Контактный датчик 4 |
| contact_5 | Contact Sensor 5 | Контактный датчик 5 |
| contact_6 | Contact Sensor 6 | Контактный датчик 6 |
| contact_7 | Contact Sensor 7 | Контактный датчик 7 |
| contact_8 | Contact Sensor 8 | Контактный датчик 8 |
| contact_9 | Contact Sensor 9 | Контактный датчик 9 |
| contact_10 | Contact Sensor 10 | Контактный датчик 10 |

#### Input Registers

| Address | Field | Access | Description |
|---------|-------|--------|-------------|
| **0x0010** | Channels 1-8 | R | Bitfield for channels 1-8 |
| **0x0011** | Channels 9-10 | R | Bitfield for channels 9-10 |

#### Bitfield Structure

**Register 0x0010 (Channels 1-8):**

| Bit | Channel | State Meaning |
|-----|---------|---------------|
| 0 | Channel 1 | 0=Open, 1=Closed |
| 1 | Channel 2 | 0=Open, 1=Closed |
| 2 | Channel 3 | 0=Open, 1=Closed |
| 3 | Channel 4 | 0=Open, 1=Closed |
| 4 | Channel 5 | 0=Open, 1=Closed |
| 5 | Channel 6 | 0=Open, 1=Closed |
| 6 | Channel 7 | 0=Open, 1=Closed |
| 7 | Channel 8 | 0=Open, 1=Closed |

**Register 0x0011 (Channels 9-10):**

| Bit | Channel | State Meaning |
|-----|---------|---------------|
| 0 | Channel 9 | 0=Open, 1=Closed |
| 1 | Channel 10 | 0=Open, 1=Closed |

#### Channel Extraction Formula

```
Register number: REG_NO = CHN_NO / 16
Byte number: BYTE_NO = CHN_NO / 8
Bit number: BIT_NO = CHN_NO % 8
```

**Python Example:**
```python
def get_channel_state(channel: int, reg_0x0010: int, reg_0x0011: int) -> bool:
    """Extract channel state from bitfield registers."""
    if channel <= 8:
        bit_position = channel - 1
        return bool((reg_0x0010 >> bit_position) & 0x01)
    else:  # channels 9-10
        bit_position = channel - 9
        return bool((reg_0x0011 >> bit_position) & 0x01)
```

#### Dynamic Polling

Only read the registers needed based on channel count:

```python
channel_count = device_info['channel_count']  # From register 0x0003 LSB

if channel_count <= 8:
    # Read only register 0x0010
    regs = await read_input_registers(slave_id, 0x0010, 1)
else:
    # Read both registers 0x0010-0x0011
    regs = await read_input_registers(slave_id, 0x0010, 2)
```

---

### 6.3 Temperature/Humidity Sensors

**Device Types:** 0x22 (Temperature), 0x23 (Humidity)
**Register Type:** **INPUT Registers** (Function 0x04)

#### Input Registers

| Address | Field | Access | Description |
|---------|-------|--------|-------------|
| **0x0020** | Channel 1 | R | Sensor data for channel 1 |
| **0x0021** | Channel 2 | R | Sensor data for channel 2 |
| ... | ... | R | ... |
| 0x0020+N-1 | Channel N | R | Sensor data for channel N |

Where N = channel count from register 0x0003 LSB (1-10 channels).

#### Temperature Sensor (0x22)

- **Data Type:** i16 (signed 16-bit)
- **Scale:** ÷10 = °C
- **Range:** -400 to +990 (representing -40.0°C to +99.0°C)
- **Invalid Marker:** 0x7FFF

**Example:**
```
Raw value: 0x0123 = 291
Temperature: 291 / 10 = 29.1°C
```

#### Humidity Sensor (0x23)

- **Data Type:** u16 (unsigned 16-bit)
- **Scale:** ÷10 = %
- **Range:** 0 to 1000 (representing 0.0% to 100.0%)
- **Invalid Marker:** 0x7FFF

**Example:**
```
Raw value: 0x0381 = 897
Humidity: 897 / 10 = 89.7%
```

---

### 6.4 Relay Control Blocks

**Device Types:** 0xC0 (2-channel), 0xC1 (10-channel)
**Register Type:** Holding Registers (Function 0x03/0x10)

> **NOTE:** The relay register (0x0010) is RW - the same register is used for both reading state and writing control. The integration uses `BITMASK_SWITCH_INPUT` which creates Switch entities that read their bit state from the register for display and use read-modify-write for changes.

#### Home Assistant Entities

Each channel is exposed as:
- **Switch entity** - Controls relay on/off state
- **Number entity** - Timer value in seconds (0-16383.5s)

| Entity Type | Count | Platform | Translation Keys |
|-------------|-------|----------|------------------|
| Switch | 10 | `switch.py` | `relay_1` through `relay_10` |
| Number | 10 | `number.py` | `relay_1_timer` through `relay_10_timer` |

**2-channel variant (0xC0):** 2 switches + 2 number entities
**10-channel variant (0xC1):** 10 switches + 10 number entities

#### Channel State Register (0x0010)

| Address | MSB | LSB | Access | Description |
|---------|-----|-----|--------|-------------|
| **0x0010** | Channels 0-7 | Channels 8-10 | RW | Channel enable bitfield |

**Bitfield Structure (per MODBUS_PROTOCOL_RU.md):**
> Byte 0 = MSB, Byte 1 = LSB

| Channel | Bit Position | Bitmask | State Meaning |
|---------|-------------|---------|---------------|
| 1 (ch 0) | Bit 8 | 0x0100 | 0=OFF, 1=ON |
| 2 (ch 1) | Bit 9 | 0x0200 | 0=OFF, 1=ON |
| 3 (ch 2) | Bit 10 | 0x0400 | 0=OFF, 1=ON |
| 4 (ch 3) | Bit 11 | 0x0800 | 0=OFF, 1=ON |
| 5 (ch 4) | Bit 12 | 0x1000 | 0=OFF, 1=ON |
| 6 (ch 5) | Bit 13 | 0x2000 | 0=OFF, 1=ON |
| 7 (ch 6) | Bit 14 | 0x4000 | 0=OFF, 1=ON |
| 8 (ch 7) | Bit 15 | 0x8000 | 0=OFF, 1=ON |
| 9 (ch 8) | Bit 0 | 0x0001 | 0=OFF, 1=ON |
| 10 (ch 9) | Bit 1 | 0x0002 | 0=OFF, 1=ON |

#### Timer Registers (0x0020-0x0029)

| Address | Field | Access | Description |
|---------|-------|--------|-------------|
| **0x0020** | Channel 1 Timer | RW | Timer for channel 1 |
| **0x0021** | Channel 2 Timer | RW | Timer for channel 2 |
| **0x0022** | Channel 3 Timer | RW | Timer for channel 3 |
| **0x0023** | Channel 4 Timer | RW | Timer for channel 4 |
| **0x0024** | Channel 5 Timer | RW | Timer for channel 5 |
| **0x0025** | Channel 6 Timer | RW | Timer for channel 6 |
| **0x0026** | Channel 7 Timer | RW | Timer for channel 7 |
| **0x0027** | Channel 8 Timer | RW | Timer for channel 8 |
| **0x0028** | Channel 9 Timer | RW | Timer for channel 9 |
| **0x0029** | Channel 10 Timer | RW | Timer for channel 10 |

**Timer Format (16-bit):**
```
Bit 15: Initial state (applied immediately on write, then cleared by device)
  0 = OFF
  1 = ON

Bits 14-0: Timer value
  Unit: 500ms per count
  Range: 0x0001-0x7FFF (0.5s to 16383.5s ≈ 4.5 hours)
  0x0000 = Timer not running

Behavior:
  1. Write value with bit 15 set → relay turns ON immediately
  2. Bit 15 is cleared automatically by device
  3. Remaining value counts down
  4. When value reaches 0 → relay toggles to opposite state
```

**Home Assistant Timer Entity:**
- **Unit:** Seconds
- **Scale:** ×2 (converts seconds to 500ms units for protocol)
- **Range:** 0 to 16383.5 seconds
- **Step:** 0.5 seconds

**Example - Turn ON channel 2 for 5 seconds:**
```
User sets timer to 5.0 seconds in Home Assistant
Internal conversion: 5.0 × 2 = 10 counts
Initial state = ON (bit 15 set)
Register value = 0x8000 | 0x000A = 0x800A
Write 0x800A to register 0x0021
```

---

## 7. Data Types and Scaling

### Type Definitions

| Type | Size | Range | Notes |
|------|------|-------|-------|
| u8 | 8-bit unsigned | 0 to 255 | Extract from LSB or MSB |
| s8 / i8 | 8-bit signed | -128 to +127 | Extract from MSB |
| u16 | 16-bit unsigned | 0 to 65535 | Full register |
| i16 | 16-bit signed | -32768 to +32767 | Full register, two's complement |
| u32 | 32-bit unsigned | 0 to 4294967295 | Two consecutive registers |
| i32 | 32-bit signed | -2147483648 to +2147483647 | Two consecutive registers |

### Byte Extraction

```python
# Extract MSB (bits 15-8)
msb = (register_value >> 8) & 0xFF

# Extract LSB (bits 7-0)
lsb = register_value & 0xFF
```

### Signed Conversion

```python
# Convert u16 to i16
if raw >= 0x8000:
    signed_value = raw - 0x10000
else:
    signed_value = raw

# Convert u8 to i8 (for MSB values)
msb = (raw >> 8) & 0xFF
if msb >= 0x80:
    msb = msb - 0x100
```

### Scaling Formulas

| Data Type | Scale | Formula | Example |
|-----------|-------|---------|---------|
| Temperature (CH/DHW) | ×10 | `raw / 10.0` | 291 → 29.1°C |
| Temperature (Setpoint Active) | ×256 | `raw / 256.0` | 11520 → 45.0°C |
| Pressure | ×10 | `lsb / 10.0` | 12 → 1.2 bar |
| Flow Rate | ×10 | `lsb / 10.0` | 8 → 0.8 L/min |
| Temperature (Setpoint Write) | ×10 | `target × 10` | 45.0°C → 450 |
| Timer | ×0.5s | `value × 0.5` | 10 → 5.0 seconds |

---

## 8. Invalid/Unsupported Value Markers

| Marker | Type | Used For | Meaning |
|--------|------|----------|---------|
| **0x7FFF** | i16 | Temperature, setpoint | Sensor not available or error |
| **0xFFFF** | u16 | Version, error codes | Invalid or unavailable |
| **0xFF** | u8 | Pressure, flow, modulation | Sensor not available |
| **0x7F** | s8/i8 | Outdoor temperature | Invalid reading |

### Handling Invalid Values

```python
def get_temperature(raw_value: int) -> Optional[float]:
    """Convert raw temperature register to Celsius."""
    if raw_value == 0x7FFF:
        return None  # Sensor not available

    # Convert to signed
    if raw_value >= 0x8000:
        raw_value = raw_value - 0x10000

    return raw_value / 10.0
```

---

## 9. Error Handling

### Modbus Exception Codes

| Code | Name | Meaning |
|------|------|---------|
| 0x01 | Illegal Function | Function code not supported by device |
| 0x02 | Illegal Data Address | Register address invalid for this device |
| 0x03 | Illegal Data Value | Data value out of range |
| 0x04 | Slave Device Failure | Internal device error |

### Error Handling Strategy

1. **Read errors:** Return `None`, log error
2. **Write errors:** Return `False`, log error
3. **Timeout:** Retry with exponential backoff
4. **Exception code 0x02:** Register not supported by this device type

### Retry Strategy

```python
async def read_with_retry(slave_id, address, count, max_retries=3):
    for attempt in range(max_retries):
        try:
            result = await read_registers(slave_id, address, count)
            if result is not None:
                return result
        except TimeoutError:
            if attempt < max_retries - 1:
                await asyncio.sleep(0.5 * (attempt + 1))  # Exponential backoff
    return None
```

---

## 10. Implementation Notes

### Register Type Selection

**Critical:** Different device types use different register types:

| Device Type | Data Registers | Function Code |
|-------------|----------------|---------------|
| Boiler Adapters | Holding | 0x03 |
| Contact Splitter | **INPUT** | **0x04** |
| Temp/Humidity Sensors | **INPUT** | **0x04** |
| Relay Blocks | Holding | 0x03 |

### Read-Modify-Write Pattern

For bitfield registers like Circuit Enable (0x0039):

```python
async def set_circuit_enable_bit(address: int, bit: int, enabled: bool):
    # Read current value
    current = await read_holding_registers(slave_id, address, 1)
    if current is None:
        return False

    # Modify the bit
    if enabled:
        new_value = current[0] | (1 << bit)
    else:
        new_value = current[0] & ~(1 << bit)

    # Write back
    return await write_register(slave_id, address, new_value)
```

### Half-Duplex Considerations

RS-485 is half-duplex - only one transaction at a time:

```python
class ModbusProtocol:
    def __init__(self):
        self._lock = asyncio.Lock()

    async def read_registers(self, slave_id, address, count):
        async with self._lock:
            # Perform Modbus operation
            return await self._execute_read(...)
```

### Polling Strategy

- **Default interval:** 15 seconds
- **Batch read:** Read all needed registers in one request
- **Dynamic:** Adjust register count based on device channel count

---

## Appendix: Quick Reference

### Device Type Summary

| Code | Name | Register Type | Key Registers |
|------|------|---------------|---------------|
| 0x14 | OpenTherm v2 | Holding | 0x0010-0x0039 |
| 0x15 | eBus | Holding | 0x0010-0x0039 |
| 0x16 | Navien | Holding | 0x0010-0x0039 |
| 0x22 | Temp Sensor | **INPUT** | 0x0020+ |
| 0x23 | Humidity Sensor | **INPUT** | 0x0020+ |
| 0x59 | Contact Splitter | **INPUT** | 0x0010-0x0011 |
| **0xC0** | **Relay 2ch** | Holding | 0x0010, 0x0020-0x0021 |
| **0xC1** | **Relay 10ch** | Holding | 0x0010, 0x0020-0x0029 |

### Function Code Summary

| Device | Read Function | Write Function |
|--------|---------------|----------------|
| Boiler Adapters | 0x03 | 0x06/0x10 |
| Contact Splitter | **0x04** | - |
| Temp/Humidity | **0x04** | - |
| **Relay Blocks** | 0x03 | 0x06/0x10 |

---

**Document End**
