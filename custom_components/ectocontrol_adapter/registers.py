from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.button import ButtonDeviceClass
from homeassistant.components.number import NumberDeviceClass
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.switch import SwitchDeviceClass  # noqa: F401
from homeassistant.const import PERCENTAGE, UnitOfPressure, UnitOfTemperature, UnitOfTime, UnitOfVolumeFlowRate
from homeassistant.helpers.entity import EntityCategory

from .converters import uptime_to_boottime

# Register type maping for struct python module
REG_TYPE_MAPPING = {
    # 8-bit types (single byte)
    "uint8": "B",
    "int8": "b",
    # 16-bit types (single register)
    "uint16": "H",
    "int16": "h",
    # 32-bit types (two registers)
    "uint32": "I",
    "int32": "i",
    "float32": "f",
    # 64-bit types (four registers)
    "uint64": "Q",
    "int64": "q",
    "float64": "d",
}

# Bitmasks value types
BM_VALUE = 1
BM_BINARY = 2
BM_CONNECTIVITY = 3  # Special type: returns True when data is available (device connected)

# Input types for write registers
BUTTON_INPUT = "button"
NUMBER_INPUT = "number"
SWITCH_INPUT = "switch"
SELECT_INPUT = "select"
BITMASK_SWITCH_INPUT = "bitmask_switch"

# One byte types
BYTE_TYPES = ["int8", "uint8"]

# Default scan interval
REG_DEFAULT_SCAN_INTERVAL = 15

# Default max write retries
REG_DEFAULT_MAX_RETRIES = 3

# Default retry delay (float, seconds)
REG_DEFAULT_RETRY_DELAY = 0.3

# Default step for numbers
REG_DEFAULT_NUMBER_STEP = 1.0

# Status register offset
REG_STATUS_OFFSET = 0x30

# Status values
REG_STATUS_ERROR_OP = -2  # boiler read/write error
REG_STATUS_UNSUPPORTED = -1
REG_STATUS_OK = 0
REG_STATUS_NOT_INIT = 1

# Reading registers of the ectoControl adapter
REG_R_ADAPTER_STATUS = 0x0010
REG_R_ADAPTER_VERSION = 0x0011
REG_R_ADAPTER_UPTIME = 0x0012
REG_R_COOLANT_MIN_TEMP = 0x0014
REG_R_COOLANT_MAX_TEMP = 0x0015
REG_R_DHW_MIN_TEMP = 0x0016
REG_R_DHW_MAX_TEMP = 0x0017
REG_R_COOLANT_TEMP = 0x0018
REG_R_DHW_TEMP = 0x0019
REG_R_CURRENT_PRESSURE = 0x001A
REG_R_CURRENT_VOLUME_FLOW_RATE = 0x001B
REG_R_BURNER_MODULATION = 0x001C
REG_R_BURNER_STATUS = 0x001D
REG_R_ERROR_CODE_MAIN = 0x001E
REG_R_ERROR_CODE_ADD = 0x001F
REG_R_OUTER_TEMP = 0x0020
REG_R_VENDOR_CODE = 0x0021
REG_R_MODEL_CODE = 0x0022
REG_R_OPENTHERM_ERRORS = 0x0023

# Writing registers of the ectoControl adapter
REG_W_CONNECT_TYPE = 0x0030
REG_W_COOLANT_TEMP = 0x0031
REG_W_COOLANT_EMERGENCY_TEMP = 0x0032
REG_W_COOLANT_MIN_TEMP = 0x0033
REG_W_COOLANT_MAX_TEMP = 0x0034
REG_W_DHW_MIN_TEMP = 0x0035
REG_W_DHW_MAX_TEMP = 0x0036
REG_W_DHW_TEMP = 0x0037
REG_W_BURNER_MODULATION = 0x0038
REG_W_MODE = 0x0039
REG_W_CIRCUIT_ENABLE = 0x003A

# Command registers
REG_W_COMMAND = 0x0080
REG_R_COMMAND_REPLY = 0x0081

# Relay Module Registers (Device Types 0xC0, 0xC1)
# Same register for read and write - RW holding register
REG_RW_RELAY_CHANNELS = 0x0010  # Channel control/state (bitfield, RW)
REG_RW_RELAY_TIMER_BASE = 0x0020  # Timer registers base (0x0020-0x0029)

# Data types for unpack via python `struct` module
REGISTERS_R = {
    REG_R_ADAPTER_STATUS: {
        "name": "adapter_status_raw",
        "count": 1,
        "data_type": "uint16",
        "input_type": "holding",
        "scan_interval": 5,
        "category": EntityCategory.DIAGNOSTIC,
        "bitmasks": {
            0x00FF: {
                "type": BM_VALUE,
                "name": "last_reboot_code",
                "category": EntityCategory.DIAGNOSTIC,
                "icon": "mdi:code-braces-box",
            },
            0x0700: {
                "type": BM_VALUE,
                "name": "adapter_bus",
                "device_class": SensorDeviceClass.ENUM,
                "choices": {0b00000000000: "Opentherm", 0b00100000000: "eBus", 0b01000000000: "Navien"},
                "icon": "mdi:alphabetical-variant",
            },
            0x0800: {"type": BM_BINARY, "name": "connectivity", "device_class": BinarySensorDeviceClass.CONNECTIVITY},
        },
    },
    REG_R_ADAPTER_VERSION: {
        "name": "adapter_version_raw",
        "count": 1,
        "data_type": "uint16",
        "input_type": "holding",
        "scan_interval": 300,
        "category": EntityCategory.DIAGNOSTIC,
        "bitmasks": {
            0x00FF: {
                "type": BM_VALUE,
                "name": "adapter_sw_version",
                "category": EntityCategory.DIAGNOSTIC,
                "icon": "mdi:github",
            },
            0xFF00: {
                "rshift": 8,
                "type": BM_VALUE,
                "name": "adapter_hw_version",
                "category": EntityCategory.DIAGNOSTIC,
                "icon": "mdi:chip",
            },
        },
    },
    REG_R_ADAPTER_UPTIME: {
        "name": "adapter_uptime",
        "count": 2,
        "data_type": "uint32",
        "input_type": "holding",
        "scan_interval": 60,
        "unit_of_measurement": UnitOfTime.SECONDS,
        "device_class": SensorDeviceClass.DURATION,
        "category": EntityCategory.DIAGNOSTIC,
        "converters": {
            "uptime_to_boottime": {
                "converter": uptime_to_boottime,
                "name": "adapter_boot_time",
                "device_class": SensorDeviceClass.TIMESTAMP,
            }
        },
    },
    REG_R_COOLANT_MIN_TEMP: {
        "name": "coolant_min_temp",
        "count": 1,
        "data_type": "uint8",
        "input_type": "holding",
        "scan_interval": 60,
        "unit_of_measurement": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "category": EntityCategory.DIAGNOSTIC,
    },
    REG_R_COOLANT_MAX_TEMP: {
        "name": "coolant_max_temp",
        "count": 1,
        "data_type": "uint8",
        "input_type": "holding",
        "scan_interval": 60,
        "unit_of_measurement": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "category": EntityCategory.DIAGNOSTIC,
    },
    REG_R_DHW_MIN_TEMP: {
        "name": "dhw_min_temp",
        "count": 1,
        "data_type": "uint8",
        "input_type": "holding",
        "scan_interval": 60,
        "unit_of_measurement": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "category": EntityCategory.DIAGNOSTIC,
    },
    REG_R_DHW_MAX_TEMP: {
        "name": "dhw_max_temp",
        "count": 1,
        "data_type": "uint8",
        "input_type": "holding",
        "scan_interval": 60,
        "unit_of_measurement": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "category": EntityCategory.DIAGNOSTIC,
    },
    REG_R_COOLANT_TEMP: {
        "name": "coolant_temp",
        "count": 1,
        "data_type": "int16",
        "input_type": "holding",
        "scan_interval": 15,
        "unit_of_measurement": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "scale": 0.1,
        "icon": "mdi:coolant-temperature",
    },
    REG_R_DHW_TEMP: {
        "name": "dhw_temp",
        "count": 1,
        "data_type": "uint16",
        "input_type": "holding",
        "scan_interval": 15,
        "unit_of_measurement": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "scale": 0.1,
        "icon": "mdi:thermometer-water",
    },
    REG_R_CURRENT_PRESSURE: {
        "name": "current_pressure",
        "count": 1,
        "data_type": "uint8",
        "input_type": "holding",
        "scan_interval": 15,
        "unit_of_measurement": UnitOfPressure.BAR,
        "device_class": SensorDeviceClass.PRESSURE,
        "scale": 0.1,
    },
    REG_R_CURRENT_VOLUME_FLOW_RATE: {
        "name": "current_flow_rate",
        "count": 1,
        "data_type": "uint8",
        "input_type": "holding",
        "scan_interval": 15,
        "unit_of_measurement": UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        "device_class": SensorDeviceClass.VOLUME_FLOW_RATE,
        "scale": 0.1,
    },
    REG_R_BURNER_MODULATION: {
        "name": "burner_modulation",
        "count": 1,
        "data_type": "uint8",
        "input_type": "holding",
        "scan_interval": 5,
        "unit_of_measurement": PERCENTAGE,
        "device_class": SensorDeviceClass.POWER_FACTOR,
    },
    REG_R_BURNER_STATUS: {
        "name": "burner_status_raw",
        "count": 1,
        "data_type": "uint16",
        "input_type": "holding",
        "scan_interval": 5,
        "category": EntityCategory.DIAGNOSTIC,
        "bitmasks": {
            0b001: {
                "type": BM_BINARY,
                "name": "burner_status",
                "device_class": BinarySensorDeviceClass.RUNNING,
                "icon": "mdi:fire",
            },
            0b010: {
                "type": BM_BINARY,
                "name": "burner_heating",
                "device_class": BinarySensorDeviceClass.RUNNING,
                "icon": "mdi:heating-coil",
            },
            0b100: {
                "type": BM_BINARY,
                "name": "burner_dhw",
                "device_class": BinarySensorDeviceClass.RUNNING,
                "icon": "mdi:faucet",
            },
        },
    },
    REG_R_ERROR_CODE_MAIN: {
        "name": "main_error_code",
        "count": 1,
        "data_type": "uint16",
        "input_type": "holding",
        "scan_interval": 60,
        "category": EntityCategory.DIAGNOSTIC,
    },
    REG_R_ERROR_CODE_ADD: {
        "name": "add_error_code",
        "count": 1,
        "data_type": "uint16",
        "input_type": "holding",
        "scan_interval": 60,
        "category": EntityCategory.DIAGNOSTIC,
    },
    REG_R_OUTER_TEMP: {
        "name": "outer_temp",
        "count": 1,
        "data_type": "int8",
        "input_type": "holding",
        "scan_interval": 15,
        "unit_of_measurement": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "icon": "mdi:home-thermometer",
    },
    REG_R_VENDOR_CODE: {
        "name": "vendor_code",
        "count": 1,
        "data_type": "uint16",
        "input_type": "holding",
        "scan_interval": 300,
        "category": EntityCategory.DIAGNOSTIC,
    },
    REG_R_MODEL_CODE: {
        "name": "model_code",
        "count": 1,
        "data_type": "uint16",
        "input_type": "holding",
        "scan_interval": 300,
        "category": EntityCategory.DIAGNOSTIC,
    },
    REG_R_OPENTHERM_ERRORS: {
        "name": "opentherm_errors",
        "count": 1,
        "data_type": "uint8",
        "input_type": "holding",
        "scan_interval": 60,
        "category": EntityCategory.DIAGNOSTIC,
        "bitmasks": {
            0x0001: {
                "type": BM_BINARY,
                "name": "opentherm_maintenance_required",
                "device_class": BinarySensorDeviceClass.PROBLEM,
                "category": EntityCategory.DIAGNOSTIC,
            },
            0x0002: {
                "type": BM_BINARY,
                "name": "opentherm_boiler_blocked",
                "device_class": BinarySensorDeviceClass.PROBLEM,
                "category": EntityCategory.DIAGNOSTIC,
            },
            0x0004: {
                "type": BM_BINARY,
                "name": "opentherm_low_pressure",
                "device_class": BinarySensorDeviceClass.PROBLEM,
                "category": EntityCategory.DIAGNOSTIC,
            },
            0x0008: {
                "type": BM_BINARY,
                "name": "opentherm_ignition_error",
                "device_class": BinarySensorDeviceClass.PROBLEM,
                "category": EntityCategory.DIAGNOSTIC,
            },
            0x0010: {
                "type": BM_BINARY,
                "name": "opentherm_low_air_pressure",
                "device_class": BinarySensorDeviceClass.PROBLEM,
                "category": EntityCategory.DIAGNOSTIC,
            },
            0x0020: {
                "type": BM_BINARY,
                "name": "opentherm_coolant_overheating",
                "device_class": BinarySensorDeviceClass.PROBLEM,
                "category": EntityCategory.DIAGNOSTIC,
            },
        },
    },
}

# Contact Splitter Input Registers (function code 0x04)
# Per MODBUS_PROTOCOL_RU.md section 3.2 - contact states are INPUT registers
#
# Register layout (16-bit value):
#   MSB (byte 0) = channels 0-7, mapped to bits 15-8 of register value
#   LSB (byte 1) = channels 8-15, mapped to bits 7-0 of register value
#
# Channel N mapping:
#   Register = N / 16 (0x10 for channels 0-15, 0x11 for channels 16-31)
#   Byte = N / 8 (0=MSB, 1=LSB for reg 0x10)
#   Bit = N % 8
#   Bit in 16-bit value = (N % 16) for channels 8-15, or (N % 16) + 8 for channels 0-7

REG_R_CONTACT_CHANNELS = 0x0010  # Channels 0-15 (bits 15-8 = ch 0-7, bits 7-0 = ch 8-15)

# 8-channel variant: channels 0-7 (bits 15-8 of register 0x10)
REGISTERS_INPUT_8CH = {
    REG_R_CONTACT_CHANNELS: {
        "name": "contact_channels",
        "count": 1,
        "data_type": "uint16",
        "input_type": "input",  # INPUT register (function code 0x04)
        "scan_interval": 5,
        "category": EntityCategory.DIAGNOSTIC,
        "bitmasks": {
            0x0100: {"type": BM_BINARY, "name": "contact_1", "device_class": BinarySensorDeviceClass.OPENING},
            0x0200: {"type": BM_BINARY, "name": "contact_2", "device_class": BinarySensorDeviceClass.OPENING},
            0x0400: {"type": BM_BINARY, "name": "contact_3", "device_class": BinarySensorDeviceClass.OPENING},
            0x0800: {"type": BM_BINARY, "name": "contact_4", "device_class": BinarySensorDeviceClass.OPENING},
            0x1000: {"type": BM_BINARY, "name": "contact_5", "device_class": BinarySensorDeviceClass.OPENING},
            0x2000: {"type": BM_BINARY, "name": "contact_6", "device_class": BinarySensorDeviceClass.OPENING},
            0x4000: {"type": BM_BINARY, "name": "contact_7", "device_class": BinarySensorDeviceClass.OPENING},
            0x8000: {"type": BM_BINARY, "name": "contact_8", "device_class": BinarySensorDeviceClass.OPENING},
        },
    }
}

# 10-channel variant: channels 0-7 (bits 15-8) + channels 8-9 (bits 1-0)
REGISTERS_INPUT_10CH = {
    REG_R_CONTACT_CHANNELS: {
        "name": "contact_channels",
        "count": 1,
        "data_type": "uint16",
        "input_type": "input",  # INPUT register (function code 0x04)
        "scan_interval": 5,
        "category": EntityCategory.DIAGNOSTIC,
        "bitmasks": {
            0x0100: {"type": BM_BINARY, "name": "contact_1", "device_class": BinarySensorDeviceClass.OPENING},
            0x0200: {"type": BM_BINARY, "name": "contact_2", "device_class": BinarySensorDeviceClass.OPENING},
            0x0400: {"type": BM_BINARY, "name": "contact_3", "device_class": BinarySensorDeviceClass.OPENING},
            0x0800: {"type": BM_BINARY, "name": "contact_4", "device_class": BinarySensorDeviceClass.OPENING},
            0x1000: {"type": BM_BINARY, "name": "contact_5", "device_class": BinarySensorDeviceClass.OPENING},
            0x2000: {"type": BM_BINARY, "name": "contact_6", "device_class": BinarySensorDeviceClass.OPENING},
            0x4000: {"type": BM_BINARY, "name": "contact_7", "device_class": BinarySensorDeviceClass.OPENING},
            0x8000: {"type": BM_BINARY, "name": "contact_8", "device_class": BinarySensorDeviceClass.OPENING},
            0x0001: {"type": BM_BINARY, "name": "contact_9", "device_class": BinarySensorDeviceClass.OPENING},
            0x0002: {"type": BM_BINARY, "name": "contact_10", "device_class": BinarySensorDeviceClass.OPENING},
        },
    }
}

# Legacy aliases for backwards compatibility
REGISTERS_INPUT = REGISTERS_INPUT_8CH  # Default to 8-channel

# Merge all input register configs into REGISTERS_R for coordinator access
# (coordinator.py looks up register configs from REGISTERS_R)
REGISTERS_R.update(REGISTERS_INPUT_8CH)
REGISTERS_R.update(REGISTERS_INPUT_10CH)

# Relay Module Read Register (Device Types 0xC0, 0xC1)
# Register 0x0010 is RW - coordinator polls it so switches can read their state
REGISTERS_RELAY_R = {
    REG_RW_RELAY_CHANNELS: {
        "name": "relay_channels_raw",
        "count": 1,
        "data_type": "uint16",
        "input_type": "holding",
        "scan_interval": 5,
        "category": EntityCategory.DIAGNOSTIC,
    }
}

# Merge relay read registers into REGISTERS_R for coordinator access
REGISTERS_R.update(REGISTERS_RELAY_R)

# Relay Module Write Registers (Device Types 0xC0, 0xC1)
# Channel control uses BITMASK_SWITCH_INPUT - creates switches that read/write same register
# Bit positions: channels 1-8 in bits 8-15, channels 9-10 in bits 0-1
REGISTERS_RELAY_W = {
    REG_RW_RELAY_CHANNELS: {
        "name": "relay_channels",
        "input_type": BITMASK_SWITCH_INPUT,
        "bit_switches": [
            # Channels 1-8 (bits 8-15, MSB byte)
            {"bit": 8, "name": "relay_1"},
            {"bit": 9, "name": "relay_2"},
            {"bit": 10, "name": "relay_3"},
            {"bit": 11, "name": "relay_4"},
            {"bit": 12, "name": "relay_5"},
            {"bit": 13, "name": "relay_6"},
            {"bit": 14, "name": "relay_7"},
            {"bit": 15, "name": "relay_8"},
            # Channels 9-10 (bits 0-1, LSB byte)
            {"bit": 0, "name": "relay_9"},
            {"bit": 1, "name": "relay_10"},
        ],
    },
}

# Timer registers for 10-channel relay module
# Timer value in seconds, scale=2 converts to 500ms units
# Max timer: 32767 * 0.5 = 16383.5 seconds
REGISTERS_RELAY_TIMERS_10CH = {
    REG_RW_RELAY_TIMER_BASE
    + 0: {
        "name": "relay_1_timer",
        "input_type": NUMBER_INPUT,
        "min_value": 0,
        "max_value": 16383.5,
        "step": 0.5,
        "scale": 2,  # seconds → 500ms units
        "unit_of_measurement": UnitOfTime.SECONDS,
        "skip_verify": True,  # Relay timers have no status register
    },
    REG_RW_RELAY_TIMER_BASE
    + 1: {
        "name": "relay_2_timer",
        "input_type": NUMBER_INPUT,
        "min_value": 0,
        "max_value": 16383.5,
        "step": 0.5,
        "scale": 2,
        "unit_of_measurement": UnitOfTime.SECONDS,
        "skip_verify": True,
    },
    REG_RW_RELAY_TIMER_BASE
    + 2: {
        "name": "relay_3_timer",
        "input_type": NUMBER_INPUT,
        "min_value": 0,
        "max_value": 16383.5,
        "step": 0.5,
        "scale": 2,
        "unit_of_measurement": UnitOfTime.SECONDS,
        "skip_verify": True,
    },
    REG_RW_RELAY_TIMER_BASE
    + 3: {
        "name": "relay_4_timer",
        "input_type": NUMBER_INPUT,
        "min_value": 0,
        "max_value": 16383.5,
        "step": 0.5,
        "scale": 2,
        "unit_of_measurement": UnitOfTime.SECONDS,
        "skip_verify": True,
    },
    REG_RW_RELAY_TIMER_BASE
    + 4: {
        "name": "relay_5_timer",
        "input_type": NUMBER_INPUT,
        "min_value": 0,
        "max_value": 16383.5,
        "step": 0.5,
        "scale": 2,
        "unit_of_measurement": UnitOfTime.SECONDS,
        "skip_verify": True,
    },
    REG_RW_RELAY_TIMER_BASE
    + 5: {
        "name": "relay_6_timer",
        "input_type": NUMBER_INPUT,
        "min_value": 0,
        "max_value": 16383.5,
        "step": 0.5,
        "scale": 2,
        "unit_of_measurement": UnitOfTime.SECONDS,
        "skip_verify": True,
    },
    REG_RW_RELAY_TIMER_BASE
    + 6: {
        "name": "relay_7_timer",
        "input_type": NUMBER_INPUT,
        "min_value": 0,
        "max_value": 16383.5,
        "step": 0.5,
        "scale": 2,
        "unit_of_measurement": UnitOfTime.SECONDS,
        "skip_verify": True,
    },
    REG_RW_RELAY_TIMER_BASE
    + 7: {
        "name": "relay_8_timer",
        "input_type": NUMBER_INPUT,
        "min_value": 0,
        "max_value": 16383.5,
        "step": 0.5,
        "scale": 2,
        "unit_of_measurement": UnitOfTime.SECONDS,
        "skip_verify": True,
    },
    REG_RW_RELAY_TIMER_BASE
    + 8: {
        "name": "relay_9_timer",
        "input_type": NUMBER_INPUT,
        "min_value": 0,
        "max_value": 16383.5,
        "step": 0.5,
        "scale": 2,
        "unit_of_measurement": UnitOfTime.SECONDS,
        "skip_verify": True,
    },
    REG_RW_RELAY_TIMER_BASE
    + 9: {
        "name": "relay_10_timer",
        "input_type": NUMBER_INPUT,
        "min_value": 0,
        "max_value": 16383.5,
        "step": 0.5,
        "scale": 2,
        "unit_of_measurement": UnitOfTime.SECONDS,
        "skip_verify": True,
    },
}

# Timer registers for 2-channel relay module (only channels 1-2)
REGISTERS_RELAY_TIMERS_2CH = {
    REG_RW_RELAY_TIMER_BASE + 0: REGISTERS_RELAY_TIMERS_10CH[REG_RW_RELAY_TIMER_BASE + 0],
    REG_RW_RELAY_TIMER_BASE + 1: REGISTERS_RELAY_TIMERS_10CH[REG_RW_RELAY_TIMER_BASE + 1],
}

REGISTERS_W = {
    # Switch
    # REG_W_CONNECT_TYPE: {
    #     "name": "connect_type",
    #     "on_value": 1,
    #     "off_value": 0,
    #     "input_type": SWITCH_INPUT,
    #     "icon": "mdi:alarm-panel-outline",
    #     "device_class": SwitchDeviceClass.SWITCH
    # },
    # or Select
    REG_W_CONNECT_TYPE: {
        "name": "connect_type",
        "input_type": SELECT_INPUT,
        "icon": "mdi:alarm-panel-outline",
        "initial_value": "adapter",
        "choices": {"adapter": 0, "boiler_panel": 1},
        "category": EntityCategory.CONFIG,
    },
    REG_W_COOLANT_TEMP: {
        "name": "coolant_temp",
        "min_value": 0,
        "max_value": 100,
        "initial_value": 40,
        "step": 1,
        "scale": 10,
        "input_type": NUMBER_INPUT,
        "unit_of_measurement": UnitOfTemperature.CELSIUS,
        "icon": "mdi:coolant-temperature",
        "device_class": NumberDeviceClass.TEMPERATURE,
        "write_after_connected": (REG_R_ADAPTER_STATUS, "connectivity"),
    },
    REG_W_COOLANT_EMERGENCY_TEMP: {
        "name": "coolant_emergency_temp",
        "min_value": 0,
        "max_value": 100,
        "initial_value": 40,
        "step": 1,
        "scale": 10,
        "input_type": NUMBER_INPUT,
        "unit_of_measurement": UnitOfTemperature.CELSIUS,
        "icon": "mdi:thermometer-alert",
        "device_class": NumberDeviceClass.TEMPERATURE,
    },
    REG_W_COOLANT_MIN_TEMP: {
        "name": "coolant_min_temp",
        "min_value": 0,
        "max_value": 100,
        "initial_value": 40,
        "step": 1,
        "input_type": NUMBER_INPUT,
        "unit_of_measurement": UnitOfTemperature.CELSIUS,
        "icon": "mdi:thermometer-minus",
        "device_class": NumberDeviceClass.TEMPERATURE,
        "category": EntityCategory.CONFIG,
        "write_after_connected": (REG_R_ADAPTER_STATUS, "connectivity"),
    },
    REG_W_COOLANT_MAX_TEMP: {
        "name": "coolant_max_temp",
        "min_value": 0,
        "max_value": 100,
        "initial_value": 80,
        "step": 1,
        "input_type": NUMBER_INPUT,
        "unit_of_measurement": UnitOfTemperature.CELSIUS,
        "icon": "mdi:thermometer-plus",
        "device_class": NumberDeviceClass.TEMPERATURE,
        "category": EntityCategory.CONFIG,
        "write_after_connected": (REG_R_ADAPTER_STATUS, "connectivity"),
    },
    REG_W_DHW_MIN_TEMP: {
        "name": "dhw_min_temp",
        "min_value": 0,
        "max_value": 100,
        "initial_value": 40,
        "step": 1,
        "input_type": NUMBER_INPUT,
        "unit_of_measurement": UnitOfTemperature.CELSIUS,
        "icon": "mdi:thermometer-minus",
        "device_class": NumberDeviceClass.TEMPERATURE,
        "category": EntityCategory.CONFIG,
        "write_after_connected": (REG_R_ADAPTER_STATUS, "connectivity"),
    },
    REG_W_DHW_MAX_TEMP: {
        "name": "dhw_max_temp",
        "min_value": 0,
        "max_value": 100,
        "initial_value": 55,
        "step": 1,
        "input_type": NUMBER_INPUT,
        "unit_of_measurement": UnitOfTemperature.CELSIUS,
        "icon": "mdi:thermometer-plus",
        "device_class": NumberDeviceClass.TEMPERATURE,
        "category": EntityCategory.CONFIG,
        "write_after_connected": (REG_R_ADAPTER_STATUS, "connectivity"),
    },
    REG_W_DHW_TEMP: {
        "name": "dhw_temp",
        "min_value": 0,
        "max_value": 100,
        "initial_value": 40,
        "step": 1,
        "input_type": NUMBER_INPUT,
        "unit_of_measurement": UnitOfTemperature.CELSIUS,
        "icon": "mdi:thermometer-water",
        "device_class": NumberDeviceClass.TEMPERATURE,
    },
    REG_W_BURNER_MODULATION: {
        "name": "burner_modulation",
        "min_value": 0,
        "max_value": 100,
        "initial_value": 0,
        "step": 1,
        "input_type": NUMBER_INPUT,
        "unit_of_measurement": PERCENTAGE,
        "icon": "mdi:gas-burner",
        "device_class": NumberDeviceClass.POWER_FACTOR,
    },
    REG_W_MODE: {
        "name": "work_mode",
        "input_type": SELECT_INPUT,
        "icon": "mdi:application-cog",
        "initial_value": "disabled",
        "choices": {
            "disabled": 0b000,
            "dwh_only": 0b010,
            "heating_only": 0b001,
            "second_only": 0b100,
            "heating_dwh": 0b011,
            "heating_second": 0b101,
        },
    },
    # Bitmask switch - multiple switches from one register
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
        ],
    },
    REG_W_COMMAND: {
        "name": "command",
        "input_type": BUTTON_INPUT,
        "status_register": REG_R_COMMAND_REPLY,
        "buttons": [
            {
                "name": "reboot",
                "value": 2,
                "icon": "mdi:reload",
                "device_class": ButtonDeviceClass.RESTART,
            },
            {
                "name": "reset_boiler_errors",
                "value": 3,
                "icon": "mdi:lock-reset",
                "device_class": ButtonDeviceClass.RESTART,
            },
        ],
    },
}

# Import device type constants from const.py
from .const import (
    DEVICE_TYPE_OPENTHERM_V2,
    DEVICE_TYPE_EBUS,
    DEVICE_TYPE_CONTACT_SPLITTER_8CH,
    DEVICE_TYPE_CONTACT_SPLITTER_10CH,
    DEVICE_TYPE_TEMP_SENSOR,
    DEVICE_TYPE_HUMIDITY_SENSOR,
    DEVICE_TYPE_CONTACT_SENSOR,
    DEVICE_TYPE_NAVIEN,
    DEVICE_TYPE_RELAY_2CH,
    DEVICE_TYPE_RELAY_10CH,
)

# Device type definitions
DEVICE_TYPE_DEFS = {
    DEVICE_TYPE_OPENTHERM_V2: {
        "name": "OpenTherm Adapter v2",
        "read_registers": REGISTERS_R,  # Uses all default registers
        "write_registers": REGISTERS_W,
    },
    DEVICE_TYPE_EBUS: {
        "name": "eBus Adapter",
        "read_registers": REGISTERS_R,
        "write_registers": REGISTERS_W,
    },
    DEVICE_TYPE_CONTACT_SPLITTER_8CH: {
        "name": "Contact Sensor Splitter (8 channels)",
        "read_registers": REGISTERS_INPUT_8CH,
        "write_registers": {},
    },
    DEVICE_TYPE_CONTACT_SPLITTER_10CH: {
        "name": "Contact Sensor Splitter (10 channels)",
        "read_registers": REGISTERS_INPUT_10CH,
        "write_registers": {},
    },
    DEVICE_TYPE_RELAY_2CH: {
        "name": "Relay Block (2 channels)",
        "read_registers": REGISTERS_RELAY_R,
        "write_registers": {
            **REGISTERS_RELAY_W,  # Channel switches (only bits 8-9 used)
            **REGISTERS_RELAY_TIMERS_2CH,  # Timers for channels 1-2
        },
    },
    DEVICE_TYPE_RELAY_10CH: {
        "name": "Relay Block (10 channels)",
        "read_registers": REGISTERS_RELAY_R,
        "write_registers": {
            **REGISTERS_RELAY_W,  # All 10 channel switches
            **REGISTERS_RELAY_TIMERS_10CH,  # All 10 timers
        },
    },
    # Add more device types as needed
}
