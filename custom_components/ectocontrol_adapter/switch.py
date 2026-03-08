"""Switch entities for ectoControl adapter."""

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .mixins import ModbusUniqIdMixin
from .registers import BITMASK_SWITCH_INPUT, SWITCH_INPUT

if TYPE_CHECKING:
    from .master import ModbusMasterCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up switch entities."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    master_coordinator = data["master_coordinator"]
    write_registers = data["write_registers"]

    entities: List[ModbusSwitch] = []
    bitmask_switches: List["ModbusBitmaskSwitch"] = []

    for register, config in write_registers.items():
        input_type = config.get("input_type")

        # Regular switch
        if input_type == SWITCH_INPUT:
            entities.append(ModbusSwitch(hass, master_coordinator, register, config))

        # Bitmask switches - multiple entities from one register
        elif input_type == BITMASK_SWITCH_INPUT:
            for bit_config in config.get("bit_switches", []):
                switch_entity = ModbusBitmaskSwitch(
                    hass, master_coordinator, register, config, bit_config, bit_config["bit"]
                )
                entities.append(switch_entity)
                bitmask_switches.append(switch_entity)

    async_add_entities(entities)

    # After entities are added, restore relay states in parallel
    if bitmask_switches:
        hass.async_create_task(
            config_entry.runtime_data,
            _batch_restore_relays(bitmask_switches),
            "ectocontrol_relay_restore",
        )


async def _batch_restore_relays(bitmask_switches: List["ModbusBitmaskSwitch"]) -> None:
    """Restore all relay states to device in parallel after startup.

    This batches relay restoration to avoid sequential blocking. All relay
    writes are executed in parallel using asyncio.gather.
    """
    restore_tasks = []

    for switch in bitmask_switches:
        if switch._pending_restore_state is not None:
            restore_tasks.append(switch._restore_state_to_device())

    if restore_tasks:
        _LOGGER.info(f"Restoring {len(restore_tasks)} relay states in parallel")
        await asyncio.gather(*restore_tasks, return_exceptions=True)


class ModbusSwitch(ModbusUniqIdMixin, SwitchEntity, RestoreEntity):
    """Modbus switch entity."""

    def __init__(
        self,
        hass,
        master_coordinator: "ModbusMasterCoordinator",
        register_addr: int,
        register_config: Dict[str, Any],
    ) -> None:
        """Initialize the switch entity.

        Args:
            hass: Home Assistant instance.
            master_coordinator: Master coordinator for Modbus operations.
            register_addr: Modbus register address.
            register_config: Register configuration dictionary.
        """
        self.hass = hass
        self.coordinator = master_coordinator
        self.register_addr = register_addr
        self.register_config = register_config

        self._attr_has_entity_name = True
        self._attr_translation_key = self.register_config.get("name")
        self._attr_unique_id = f"{self._unique_id_prefix}_{self._attr_translation_key}_{register_addr:#06x}"
        self._attr_is_on: Optional[bool] = None
        self._attr_device_class = register_config.get("device_class")
        self._attr_entity_category = register_config.get("category")

        # Device info
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)})

    async def async_added_to_hass(self):
        """Restore state from HA persistence."""
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
        """Turn the switch on."""
        wrval = self.register_config["on_value"]
        success = await self.coordinator.write_registers(address=self.register_addr, values=[wrval])

        if success:
            self._attr_is_on = True
            self.async_write_ha_state()
            _LOGGER.info(f"Successfully set '{self._attr_translation_key}' to '{wrval}'")
        else:
            raise Exception(f"Failed to write value '{wrval}' to register={self.register_addr:#06x}")

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        wrval = self.register_config["off_value"]
        success = await self.coordinator.write_registers(address=self.register_addr, values=[wrval])

        if success:
            self._attr_is_on = False
            self.async_write_ha_state()
            _LOGGER.info(f"Successfully set '{self._attr_translation_key}' to '{wrval}'")
        else:
            raise Exception(f"Failed to write value '{wrval}' to register={self.register_addr:#06x}")

    @property
    def assumed_state(self) -> bool:
        """Return True as state is assumed."""
        return True

    @property
    def should_poll(self) -> bool:
        """Return False as polling is not needed."""
        return False

    @property
    def icon(self):
        """Return the icon for this switch."""
        return self.register_config.get("icon")


class ModbusBitmaskSwitch(ModbusUniqIdMixin, SwitchEntity, RestoreEntity):
    """Switch entity that controls a single bit in a register.

    HA is the source of truth. State is restored from HA persistence on reboot
    and synced to device in parallel with other relays after startup.
    """

    def __init__(
        self,
        hass,
        master_coordinator: "ModbusMasterCoordinator",
        register_addr: int,
        register_config: Dict[str, Any],
        bit_config: Dict[str, Any],
        bit_position: int,
    ) -> None:
        """Initialize the bitmask switch.

        Args:
            hass: Home Assistant instance.
            master_coordinator: Master coordinator for Modbus operations.
            register_addr: Modbus register address.
            register_config: Register configuration dictionary.
            bit_config: Bit configuration dictionary.
            bit_position: Bit position (0-15).
        """
        self.hass = hass
        self.coordinator = master_coordinator  # For _unique_id_prefix access
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

        # HA is source of truth - default to False so switch shows as toggle
        self._attr_is_on: bool = False
        # Pending state for batch restoration (None = no restoration needed)
        self._pending_restore_state: Optional[bool] = None

        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, self._master_coordinator.config_entry.entry_id)})

    async def async_added_to_hass(self):
        """Restore state from persistence and queue for batch restoration."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()

        if last_state is not None:
            if last_state.state == "on":
                self._attr_is_on = True
                self._pending_restore_state = True
            elif last_state.state == "off":
                self._attr_is_on = False
                self._pending_restore_state = False
            # If state was unknown, no restoration needed

    async def _restore_state_to_device(self) -> None:
        """Restore the pending state to device.

        Called by _batch_restore_relays() after all entities are added.
        """
        if self._pending_restore_state is None:
            return

        value = self._pending_restore_state
        _LOGGER.info(f"Restoring relay '{self._attr_translation_key}' " f"state={'ON' if value else 'OFF'} to device")
        success = await self._write_state_to_device(value)
        if not success:
            _LOGGER.warning(f"Failed to restore relay '{self._attr_translation_key}' state to device")
        # Clear pending state after restoration attempt
        self._pending_restore_state = None

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        success = await self._write_state_to_device(True)
        if success:
            self._attr_is_on = True
            self.async_write_ha_state()
            _LOGGER.info(f"Relay '{self._attr_translation_key}' turned ON")
        else:
            raise Exception(f"Failed to set bit {self.bit_position} in register {self.register_addr:#06x}")

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        success = await self._write_state_to_device(False)
        if success:
            self._attr_is_on = False
            self.async_write_ha_state()
            _LOGGER.info(f"Relay '{self._attr_translation_key}' turned OFF")
        else:
            raise Exception(f"Failed to clear bit {self.bit_position} in register {self.register_addr:#06x}")

    async def _write_state_to_device(self, value: bool) -> bool:
        """Write state to device using read-modify-write."""
        return await self._master_coordinator.write_register_bit(
            address=self.register_addr, bit=self.bit_position, value=value
        )

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on (from HA state, not device)."""
        return self._attr_is_on

    @property
    def assumed_state(self) -> bool:
        """Return False - HA is source of truth, show as toggle."""
        return False

    @property
    def should_poll(self) -> bool:
        """No polling needed - state is managed internally."""
        return False

    @property
    def icon(self):
        """Return the icon for this switch."""
        return self.bit_config.get("icon")
