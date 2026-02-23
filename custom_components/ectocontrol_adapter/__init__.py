""" ectoControl Adapter """
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, OPT_NAME, DEVICE_TYPE_NAMES
from .coordinator import ModbusDataUpdateCoordinator
from .master import ModbusMasterCoordinator
from .registers import (
    REGISTERS_R,
    REGISTERS_W,
    REG_DEFAULT_SCAN_INTERVAL,
    DEVICE_TYPE_DEFS
)

_LOGGER = logging.getLogger(__name__)

_PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH
]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """ Set up sensors from a config entry. """
    hass.data.setdefault(DOMAIN, {})

    # Create device
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, config_entry.entry_id)},
        name=config_entry.options.get(OPT_NAME) or config_entry.data.get(OPT_NAME),
        manufacturer="ectoControl"
    )

    # Create and start Modbus master coordinator
    master_coordinator = ModbusMasterCoordinator(
        hass=hass,
        config_entry=config_entry
    )
    await master_coordinator.async_start()

    # Detect device type
    device_info = await master_coordinator.detect_device_type()
    if device_info:
        device_type = device_info["device_type"]
        _LOGGER.info(
            "Detected device type: 0x%02X (%s)",
            device_type,
            DEVICE_TYPE_NAMES.get(device_type, "Unknown")
        )

        # Get register configuration for this device type
        device_def = DEVICE_TYPE_DEFS.get(device_type)
        if device_def:
            read_regs = device_def.get("read_registers", REGISTERS_R)
            write_regs = device_def.get("write_registers", REGISTERS_W)
        else:
            # Fallback to default registers
            _LOGGER.warning(
                "Unknown device type 0x%02X, using default register configuration",
                device_type
            )
            read_regs = REGISTERS_R
            write_regs = REGISTERS_W
    else:
        # Fallback to default registers if detection fails
        _LOGGER.warning("Device type detection failed, using default register configuration")
        read_regs = REGISTERS_R
        write_regs = REGISTERS_W

    # Group registers by scan interval
    update_register_groups = {}
    for register_addr, config in read_regs.items():
        scan_interval = config.get("scan_interval", REG_DEFAULT_SCAN_INTERVAL)
        if scan_interval not in update_register_groups:
            update_register_groups[scan_interval] = []
        update_register_groups[scan_interval].append((register_addr, config))

    # Create coordinators for each scan interval group
    update_coordinators = {}
    for scan_interval, registers in update_register_groups.items():
        update_coordinator = ModbusDataUpdateCoordinator(
            hass=hass,
            config_entry=config_entry,
            master=master_coordinator,
            registers=registers,
            scan_interval=scan_interval
        )

        # Fetch initial data
        await update_coordinator.async_config_entry_first_refresh()
        update_coordinators[scan_interval] = update_coordinator

    hass.data[DOMAIN][config_entry.entry_id] = {
        "master_coordinator": master_coordinator,
        "device_id": device.id,
        "update_coordinators": update_coordinators,
        "update_register_groups": update_register_groups,
        "write_registers": write_regs
    }

    # Set up sensors
    await hass.config_entries.async_forward_entry_setups(config_entry, _PLATFORMS)

    return True


async def async_update_options(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """ Update options for entry that was configured via user interface. """
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """ Unload a config entry. """
    await hass.config_entries.async_unload_platforms(config_entry, _PLATFORMS)

    master_coordinator = hass.data[DOMAIN][config_entry.entry_id]["master_coordinator"]
    await master_coordinator.async_stop()

    return True
