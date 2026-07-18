"""Data update coordinator for ectoControl adapter."""

import logging
import time
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .master import ModbusMasterCoordinator
from .registers import REG_DEFAULT_SCAN_INTERVAL, REGISTERS_R

_LOGGER = logging.getLogger(__name__)


class ModbusDataUpdateCoordinator(DataUpdateCoordinator):
    """Modbus data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry,
        master: ModbusMasterCoordinator,
        registers,
        scan_interval=REG_DEFAULT_SCAN_INTERVAL,
    ):
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance.
            config_entry: Config entry instance.
            master: Master coordinator for Modbus operations.
            registers: List of (address, config) tuples to poll.
            scan_interval: Polling interval in seconds.
        """
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=scan_interval))
        self.hass = hass
        self.config_entry = config_entry
        self._config = config_entry.options or config_entry.data
        self._master = master

        # Store registers as list of (address, config) tuples to preserve device-specific config
        # Important: Different device types may use same register address with different settings
        # (e.g., 0x0010 is "adapter_status" with holding type for OpenTherm, but "contact_channels"
        # with input type for Contact Splitter)
        self._registers = registers
        register_addrs = [addr for addr, config in registers]
        if not set(register_addrs).issubset(REGISTERS_R.keys()):
            error = f"Unknown registers found in: {register_addrs}"
            _LOGGER.error(error)
            raise ValueError(error)

    async def _async_update_data(self):
        data = {}
        t_cycle_start = time.monotonic()
        try:
            for register, reg_config in self._registers:
                input_type = reg_config.get("input_type", "holding")
                t0 = time.monotonic()

                # Choose read method based on input_type
                if input_type == "input":
                    result = await self._master.read_input_registers(address=register, count=reg_config["count"])
                else:
                    result = await self._master.read_holding_registers(address=register, count=reg_config["count"])

                elapsed = time.monotonic() - t0
                _LOGGER.debug(
                    "⏱️ COORD_SCAN reg=0x%04X type=%s → %.3fs",
                    register,
                    input_type,
                    elapsed,
                )

                if result is None or result.isError():
                    _LOGGER.error("Modbus read error for register 0x%04X", register)
                    data[register] = None
                else:
                    data[register] = result.registers
        except Exception as e:
            raise UpdateFailed(f"Exception while Modbus read: {e}")
        finally:
            _LOGGER.debug(
                "⏱️ COORD_CYCLE total=%d regs → %.3fs",
                len(self._registers),
                time.monotonic() - t_cycle_start,
            )
        return data
