"""Binary sensor entities for ectoControl adapter."""

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .mixins import ModbusSensorMixin, ModbusUniqIdMixin
from .registers import BM_BINARY, BM_CONNECTIVITY

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up sensors."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinators = data["update_coordinators"]
    register_groups = data["update_register_groups"]

    sensors = []

    # Create sensors for each coordinator
    for scan_interval, coordinator in coordinators.items():
        registers = register_groups[scan_interval]

        for register, config in registers:
            if "bitmasks" in config:
                for mask, mask_config in config["bitmasks"].items():
                    if mask_config["type"] in (BM_BINARY, BM_CONNECTIVITY):
                        sensor = ModbusBinarySensor(coordinator, register, config, mask)
                        sensors.append(sensor)

    _LOGGER.debug(f"Adding {len(sensors)} binary sensors")
    async_add_entities(sensors)


class ModbusBinarySensor(ModbusSensorMixin, ModbusUniqIdMixin, CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for bitmask values."""

    def __init__(self, coordinator, register_addr, register_config, bitmask):
        """Initialize the binary sensor.

        Args:
            coordinator: Data update coordinator.
            register_addr: Modbus register address.
            register_config: Register configuration dictionary.
            bitmask: Bitmask value for this sensor.
        """
        super().__init__(coordinator)
        self.register_addr = register_addr
        self.register_config = register_config
        self.bitmask = bitmask
        self.bitmask_config = register_config["bitmasks"][bitmask]

        # Entity attributes
        self._attr_has_entity_name = True
        self._attr_translation_key = self.bitmask_config.get("name")
        self._attr_unique_id = f"{self._unique_id_prefix}_{self._attr_translation_key}_{register_addr:#06x}"
        self._attr_device_class = self.bitmask_config.get("device_class")
        self._attr_entity_category = self.bitmask_config.get("category")

        # Device info
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)})

    @property
    def is_on(self):
        """Return True if the bit is set."""
        if self.coordinator.data is None:
            return None

        raw_data = self.coordinator.data.get(self.register_addr)
        if raw_data is None:
            return None

        raw_value = self._get_raw_value(raw_data)
        if raw_value is None:
            return None

        return bool(raw_value & self.bitmask)

    @property
    def icon(self):
        """Return the icon for this sensor."""
        return self.bitmask_config.get("icon")
