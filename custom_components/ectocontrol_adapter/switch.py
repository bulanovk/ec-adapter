import logging
from typing import Optional

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .mixins import ModbusUniqIdMixin
from .registers import SWITCH_INPUT, BITMASK_SWITCH_INPUT

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """ Set up switch entities  """
    data = hass.data[DOMAIN][config_entry.entry_id]
    master_coordinator = data["master_coordinator"]
    write_registers = data["write_registers"]
    update_coordinators = data["update_coordinators"]
    update_register_groups = data["update_register_groups"]

    entities = []

    for register, config in write_registers.items():
        input_type = config.get("input_type")

        # Regular switch
        if input_type == SWITCH_INPUT:
            entities.append(ModbusSwitch(hass, master_coordinator, register, config))

        # Bitmask switches - multiple entities from one register
        elif input_type == BITMASK_SWITCH_INPUT:
            # Find the data coordinator that polls this register
            data_coordinator = None
            for scan_interval, coordinator in update_coordinators.items():
                registers = update_register_groups[scan_interval]
                for reg_addr, _ in registers:
                    if reg_addr == register:
                        data_coordinator = coordinator
                        break
                if data_coordinator:
                    break

            for bit_config in config.get("bit_switches", []):
                entities.append(ModbusBitmaskSwitch(
                    hass, master_coordinator, data_coordinator, register, config, bit_config, bit_config["bit"]
                ))

    async_add_entities(entities)


class ModbusSwitch(ModbusUniqIdMixin, SwitchEntity, RestoreEntity):
    """ Modbus Switch entity """

    def __init__(self, hass, master_coordinator, register_addr, register_config):
        self.hass = hass
        self.coordinator = master_coordinator
        self.register_addr = register_addr
        self.register_config = register_config

        self._attr_has_entity_name = True
        self._attr_translation_key = self.register_config.get("name")
        self._attr_unique_id = f"{self._unique_id_prefix}_{self._attr_translation_key}_{register_addr:#06x}"
        self._attr_is_on = None  # Initial state is unknown
        self._attr_device_class = register_config.get("device_class")
        self._attr_entity_category = register_config.get("category")

        # Device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)}
        )

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()

        if last_state is not None:
            if last_state.state == "on":
                self._attr_is_on = True
            elif last_state.state == "off":
                self._attr_is_on = False
            else:
                self._attr_is_on = None

    async def async_turn_on(self, **kwargs):
        wrval = self.register_config["on_value"]
        success = await self.coordinator.write_registers(
            address=self.register_addr, values=[wrval])

        if success:
            self._attr_is_on = True
            self.async_write_ha_state()
            _LOGGER.info(f"Successfully set '{self._attr_translation_key}' to '{wrval}'")
        else:
            raise Exception(f"Failed to write value '{wrval}' to register={self.register_addr:#06x}")

    async def async_turn_off(self, **kwargs):
        wrval = self.register_config["off_value"]
        success = await self.coordinator.write_registers(
            address=self.register_addr, values=[wrval])

        if success:
            self._attr_is_on = False
            self.async_write_ha_state()
            _LOGGER.info(f"Successfully set '{self._attr_translation_key}' to '{wrval}'")
        else:
            raise Exception(f"Failed to write value '{wrval}' to register={self.register_addr:#06x}")

    @property
    def assumed_state(self) -> bool:
        return True

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def icon(self):
        return self.register_config.get("icon")


class ModbusBitmaskSwitch(ModbusUniqIdMixin, CoordinatorEntity, SwitchEntity, RestoreEntity):
    """Switch entity that controls a single bit in a register.

    Syncs state from coordinator data and restores persisted state on reboot.
    """

    def __init__(self, hass, master_coordinator, data_coordinator, register_addr, register_config, bit_config, bit_position):
        # Initialize CoordinatorEntity with data coordinator for state syncing
        super().__init__(data_coordinator)
        self.hass = hass
        self._master_coordinator = master_coordinator
        self.register_addr = register_addr
        self.register_config = register_config
        self.bit_position = bit_position
        self.bit_config = bit_config

        self._attr_has_entity_name = True
        self._attr_translation_key = bit_config.get("name")
        self._attr_unique_id = f"{self._unique_id_prefix}_{bit_config['name']}_{register_addr:#06x}_bit{bit_position}"
        self._attr_icon = bit_config.get("icon")
        self._attr_device_class = bit_config.get("device_class")
        self._attr_entity_category = bit_config.get("category")

        # State restoration
        self._restored_state: Optional[bool] = None
        self._initial_sync_done = False

        # Device info (use master_coordinator for config_entry)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._master_coordinator.config_entry.entry_id)}
        )

    async def async_added_to_hass(self):
        """Restore state from persistence."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()

        if last_state is not None:
            if last_state.state == "on":
                self._restored_state = True
            elif last_state.state == "off":
                self._restored_state = False

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator.

        On first update, sync restored state to device if different.
        """
        if not self._initial_sync_done and self._restored_state is not None:
            self._initial_sync_done = True
            device_state = self._get_device_state()
            if device_state is not None and device_state != self._restored_state:
                _LOGGER.info(
                    "Syncing relay '%s': device state=%s, restored state=%s, writing to device",
                    self._attr_translation_key, device_state, self._restored_state
                )
                # Schedule write of restored state
                self.hass.async_create_task(self._sync_restored_state())

        self.async_write_ha_state()

    async def _sync_restored_state(self):
        """Write restored state to device."""
        if self._restored_state:
            await self.async_turn_on(write_to_device=True)
        else:
            await self.async_turn_off(write_to_device=True)

    def _get_device_state(self) -> Optional[bool]:
        """Get current device state from coordinator data."""
        if not self.coordinator.data:
            return None
        raw_data = self.coordinator.data.get(self.register_addr)
        if raw_data is None:
            return None
        return bool(raw_data[0] & (1 << self.bit_position))

    @property
    def is_on(self) -> Optional[bool]:
        """Return true if the switch is on (from device state)."""
        return self._get_device_state()

    async def async_turn_on(self, write_to_device: bool = True, **kwargs):
        if write_to_device:
            success = await self._master_coordinator.write_register_bit(
                address=self.register_addr,
                bit=self.bit_position,
                value=True
            )
            if not success:
                raise Exception(f"Failed to set bit {self.bit_position} in register {self.register_addr:#06x}")
        # Request coordinator refresh to get actual device state
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, write_to_device: bool = True, **kwargs):
        if write_to_device:
            success = await self._master_coordinator.write_register_bit(
                address=self.register_addr,
                bit=self.bit_position,
                value=False
            )
            if not success:
                raise Exception(f"Failed to clear bit {self.bit_position} in register {self.register_addr:#06x}")
        # Request coordinator refresh to get actual device state
        await self.coordinator.async_request_refresh()

    @property
    def assumed_state(self) -> bool:
        return False  # We read actual state from device

    @property
    def should_poll(self) -> bool:
        return False  # CoordinatorEntity handles updates

    @property
    def icon(self):
        return self.bit_config.get("icon")
