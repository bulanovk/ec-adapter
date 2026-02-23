import asyncio
import logging
from typing import Any, Dict, List, Optional

from .const import (
    OPT_SLAVE,
    DEVICE_TYPE_NAMES,
)
from .registers import (
    REG_DEFAULT_MAX_RETRIES,
    REG_DEFAULT_RETRY_DELAY,
    REG_STATUS_OFFSET,
    REG_STATUS_OK
)

_LOGGER = logging.getLogger(__name__)


class ModbusMasterCoordinator:
    """Coordinator for Modbus operations using a shared connection pool."""

    def __init__(self, hass, config_entry, pool, pool_key: str, pooled_client):
        self.hass = hass
        self.config_entry = config_entry
        self._config = config_entry.options or config_entry.data
        self._pool = pool
        self._pool_key = pool_key
        self._pooled_client = pooled_client
        self._slave_id = int(self._config[OPT_SLAVE])

    async def detect_device_type(self) -> Optional[dict]:
        """Detect device type by reading generic device info registers.

        Returns:
            dict with keys: 'device_type', 'device_uid', 'channel_count'
            or None if detection fails
        """
        # Read registers 0x0000-0x0003 (generic device info)
        result = await self._pooled_client.submit_operation(
            "read_holding_registers",
            {"address": 0x0000, "count": 4, "device_id": self._slave_id}
        )

        if result is None or result.isError() or len(result.registers) < 4:
            _LOGGER.error("Failed to read device info registers")
            return None

        regs = result.registers

        # Extract UID (24-bit from registers 0x0001-0x0002)
        uid_msb = regs[1] >> 8
        uid_mid = regs[1] & 0xFF
        uid_lsb = regs[2] >> 8
        device_uid = (uid_msb << 16) | (uid_mid << 8) | uid_lsb

        # Extract device type (MSB of register 0x0003)
        device_type = (regs[3] >> 8) & 0xFF
        channel_count = regs[3] & 0xFF

        _LOGGER.info(
            "Device detected: type=0x%02X (%s), UID=0x%06X, channels=%d",
            device_type,
            DEVICE_TYPE_NAMES.get(device_type, "Unknown"),
            device_uid,
            channel_count
        )

        return {
            "device_type": device_type,
            "device_uid": device_uid,
            "channel_count": channel_count
        }

    async def write_register_bit(self, address: int, bit: int, value: bool) -> bool:
        """Write a single bit in a register using read-modify-write.

        Args:
            address: Register address
            bit: Bit position (0-15)
            value: True to set bit, False to clear bit

        Returns:
            True if successful, False otherwise
        """
        # Read current value
        result = await self.read_holding_registers(address, 1)
        if result is None or result.isError():
            return False

        current = result.registers[0]

        # Modify the bit
        if value:
            new_value = current | (1 << bit)
        else:
            new_value = current & ~(1 << bit)

        # Write back
        return await self.write_registers(address, [new_value])

    async def read_holding_registers(self, address: int, count: int) -> Any:
        """Read holding registers from the device."""
        return await self._pooled_client.submit_operation(
            "read_holding_registers",
            {"address": address, "count": count, "device_id": self._slave_id}
        )

    async def write_registers(
        self,
        address: int,
        values: List[int],
        status_register: Optional[int] = None
    ) -> bool:
        """Write registers to the device with optional status verification."""
        result = await self._pooled_client.submit_operation(
            "write_registers",
            {"address": address, "values": values, "device_id": self._slave_id}
        )

        if result is None or result.isError():
            return False

        # Verify write status
        status_reg = (
            status_register or
            address + REG_STATUS_OFFSET
        )

        return await self._verify_write_status(
            status_reg,
            REG_STATUS_OK,
            REG_DEFAULT_MAX_RETRIES,
            REG_DEFAULT_RETRY_DELAY
        )

    async def _verify_write_status(
            self,
            status_register: int,
            success_status: int,
            max_retries: int,
            retry_delay: float) -> bool:
        """Check write status by polling status register."""
        for attempt in range(max_retries):
            try:
                result = await self._pooled_client.submit_operation(
                    "read_holding_registers",
                    {"address": status_register, "count": 1, "device_id": self._slave_id}
                )
                if result is not None:
                    if result.isError():
                        _LOGGER.error("Modbus read status register=0x%04x error", status_register)
                    elif len(result.registers) and result.registers[0] == success_status:
                        return True
            except Exception as e:
                _LOGGER.error("Attempt %d failed to read status register: %s", attempt + 1, e)

            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)

        return False

    @property
    def pool_key(self) -> str:
        """Return the pool key for this coordinator."""
        return self._pool_key

    @property
    def is_connected(self) -> bool:
        """Check if the pooled client is connected."""
        return self._pooled_client.is_connected
