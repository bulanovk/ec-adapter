"""ectoControl Adapter"""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import (
    DOMAIN,
    OPT_NAME,
    DEVICE_TYPE_NAMES,
    DEVICE_TYPE_CONTACT_SPLITTER,
    DEVICE_TYPE_RELAY_BLOCK_2CH,
    DEVICE_TYPE_RELAY_BLOCK_10CH,
)
from .coordinator import ModbusDataUpdateCoordinator
from .master import ModbusMasterCoordinator
from .pool import ModbusClientPool, POOL_KEY
from .registers import REGISTERS_R, REGISTERS_W, REG_DEFAULT_SCAN_INTERVAL, DEVICE_TYPE_DEFS

_LOGGER = logging.getLogger(__name__)

_PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the ectoControl Adapter integration."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][POOL_KEY] = ModbusClientPool()
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up sensors from a config entry."""
    config = config_entry.options or config_entry.data

    # Create device
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, config_entry.entry_id)},
        name=config.get(OPT_NAME) or config_entry.data.get(OPT_NAME),
        manufacturer="ectoControl",
    )

    # Acquire a pooled client connection
    pool: ModbusClientPool = hass.data[DOMAIN][POOL_KEY]
    pool_key, pooled_client = await pool.acquire(config)

    # Create master coordinator with pooled client
    master_coordinator = ModbusMasterCoordinator(
        hass=hass, config_entry=config_entry, pool=pool, pool_key=pool_key, pooled_client=pooled_client
    )

    # Detect device type
    device_info = await master_coordinator.detect_device_type()
    if device_info:
        device_type = device_info["device_type"]
        channel_count = device_info.get("channel_count", 0)

        # For Contact Splitter, use composite type key (type, channels)
        if device_type == DEVICE_TYPE_CONTACT_SPLITTER:
            # Map to specific variant based on channel count
            if channel_count <= 8:
                device_type_key = (DEVICE_TYPE_CONTACT_SPLITTER, 8)
            else:
                device_type_key = (DEVICE_TYPE_CONTACT_SPLITTER, 10)
        # For Relay modules, use composite type key (type, channels)
        elif device_type == DEVICE_TYPE_RELAY_BLOCK_2CH:
            device_type_key = (DEVICE_TYPE_RELAY_BLOCK_2CH, 2)
        elif device_type == DEVICE_TYPE_RELAY_BLOCK_10CH:
            device_type_key = (DEVICE_TYPE_RELAY_BLOCK_10CH, 10)
        else:
            device_type_key = device_type

        _LOGGER.info(
            "Detected device type: 0x%02X (%s)",
            device_type,
            DEVICE_TYPE_NAMES.get(device_type_key, DEVICE_TYPE_NAMES.get(device_type, "Unknown")),
        )

        # Get register configuration for this device type
        device_def = DEVICE_TYPE_DEFS.get(device_type_key)
        if device_def:
            read_regs = device_def.get("read_registers", REGISTERS_R)
            write_regs = device_def.get("write_registers", REGISTERS_W)
        else:
            # Fallback to default registers
            _LOGGER.warning("Unknown device type 0x%02X, using default register configuration", device_type)
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
            scan_interval=scan_interval,
        )

        # Fetch initial data
        await update_coordinator.async_config_entry_first_refresh()
        update_coordinators[scan_interval] = update_coordinator

    hass.data[DOMAIN][config_entry.entry_id] = {
        "master_coordinator": master_coordinator,
        "device_id": device.id,
        "update_coordinators": update_coordinators,
        "update_register_groups": update_register_groups,
        "write_registers": write_regs,
        "pool_key": pool_key,
    }

    # Set up sensors
    await hass.config_entries.async_forward_entry_setups(config_entry, _PLATFORMS)

    return True


async def async_update_options(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Update options for entry that was configured via user interface."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms(config_entry, _PLATFORMS)

    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    pool_key = entry_data.get("pool_key")

    # Release the pooled client
    if pool_key:
        pool: ModbusClientPool = hass.data[DOMAIN][POOL_KEY]
        await pool.release(pool_key)

    return True
