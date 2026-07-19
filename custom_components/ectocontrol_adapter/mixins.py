"""Mixin classes for ectoControl adapter entities."""

import logging
import struct

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .registers import BYTE_TYPES, REG_BOILER_DEPENDENT, REG_BOILER_WRITES, REG_TYPE_MAPPING

_LOGGER = logging.getLogger(__name__)


def _unique_id_prefix(config: dict):
    mb_type = config.get("modbus_type")
    slave = config.get("slave")
    if mb_type == "serial":
        device = config.get("device")
        return f"{DOMAIN}_{mb_type}_{device}_{slave}"
    else:
        host = config.get("host")
        port = config.get("port")
        return f"{DOMAIN}_{mb_type}_{host}_{port}_{slave}"


def get_device_info_for_register(config_entry, hass, register_addr=None, *, is_write=False) -> DeviceInfo:
    """Build DeviceInfo for an entity, routing boiler-side registers to the Boiler sub-device.

    For devices with boiler communication (OpenTherm, eBUS, Navien), a "Boiler"
    sub-device is created via ``async_get_or_create`` with ``via_device`` pointing
    to the adapter. Boiler-side read registers (in ``REG_BOILER_DEPENDENT``) and
    write registers (in ``REG_BOILER_WRITES``) are routed there; everything else
    stays on the main adapter device.

    For relay/contact-splitter device types (no boiler sub-device), all entities
    are placed on the main device.
    """
    entry_id = config_entry.entry_id
    entry_data = hass.data.get(DOMAIN, {}).get(entry_id, {})
    has_boiler_sub_device = entry_data.get("boiler_device_id") is not None

    if has_boiler_sub_device and register_addr is not None:
        boiler_set = REG_BOILER_WRITES if is_write else REG_BOILER_DEPENDENT
        if register_addr in boiler_set:
            return DeviceInfo(
                identifiers={(DOMAIN, f"{entry_id}_boiler")},
                via_device=(DOMAIN, entry_id),
            )

    return DeviceInfo(identifiers={(DOMAIN, entry_id)})


class ModbusSensorMixin:
    """Mixin providing raw value conversion for Modbus sensors."""

    def __init__(self, *args, **kwargs):
        """Initialize the mixin."""
        super().__init__(*args, **kwargs)

    def _get_raw_value(self, raw_data):
        """Convert raw register data to sensor value."""
        try:
            data_type = self.register_config.get("data_type")
            scale = self.register_config.get("scale", 1.0)
            count = self.register_config.get("count", 1)

            if not data_type:
                return raw_data[0] if raw_data else None

            # Convert registers to bytes
            byte_data = b""
            for register in raw_data:
                byte_data += register.to_bytes(2, byteorder="big")

            # Check config count for one byte values
            if data_type in BYTE_TYPES and count > 1:
                _LOGGER.error(
                    "Invalid configuration for register %s: " "8-bit data types require count=1, got count=%d",
                    self.register_addr,
                    count,
                )
                return None

            struct_data_type = REG_TYPE_MAPPING[data_type]
            if data_type in BYTE_TYPES:  # for one byte values
                value = struct.unpack(f">{struct_data_type}", bytes([byte_data[1]]))[0]
            else:
                value = struct.unpack(f">{struct_data_type}", byte_data)[0]

            # Apply scaling if needed
            if scale != 1.0:
                value *= scale

            return value

        except Exception as e:
            _LOGGER.error("Error converting register %s data: %s", self.register_addr, e)
            return None


class ModbusUniqIdMixin:
    """Mixin providing unique ID generation for Modbus entities."""

    def __init__(self, *args, **kwargs):
        """Initialize the mixin."""
        super().__init__(*args, **kwargs)

    @property
    def _unique_id_prefix(self):
        """Generate unique ID prefix based on connection config."""
        return _unique_id_prefix(self.coordinator._config)
