"""Mock Modbus client for testing."""

from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock


class MockModbusResponse:
    """Mock Modbus response object."""

    def __init__(self, registers: Optional[List[int]] = None, is_error: bool = False):
        """Initialize mock response.

        Args:
            registers: List of register values to return
            is_error: Whether this response represents an error
        """
        self._registers = registers or []
        self._is_error = is_error

    @property
    def registers(self) -> List[int]:
        """Return the register values."""
        return self._registers

    def isError(self) -> bool:
        """Check if this is an error response."""
        return self._is_error


class MockModbusClient:
    """Mock AsyncModbusClient for testing.

    Simulates Modbus device behavior with configurable responses.
    """

    def __init__(self):
        """Initialize the mock client."""
        self._registers: Dict[int, int] = {}
        self._connected = False
        self._connect_calls = 0
        self._read_calls: List[Dict[str, Any]] = []
        self._write_calls: List[Dict[str, Any]] = []

        # Default behavior
        self._next_read_result: Optional[MockModbusResponse] = None
        self._read_error = False
        self._write_error = False

    @property
    def connected(self) -> bool:
        """Return connection status."""
        return self._connected

    async def connect(self) -> bool:
        """Simulate connecting to the Modbus device."""
        self._connect_calls += 1
        self._connected = True
        return True

    def close(self):
        """Simulate closing the connection."""
        self._connected = False

    def set_register(self, address: int, value: int):
        """Set a register value for testing.

        Args:
            address: Register address
            value: Register value
        """
        self._registers[address] = value

    def set_registers(self, registers: Dict[int, int]):
        """Set multiple register values.

        Args:
            registers: Dict mapping addresses to values
        """
        self._registers.update(registers)

    def set_next_read_result(self, response: Optional[MockModbusResponse]):
        """Set the next read result (overrides register-based reads).

        Args:
            response: MockModbusResponse to return, or None to use registers
        """
        self._next_read_result = response

    def set_read_error(self, error: bool = True):
        """Configure reads to return errors.

        Args:
            error: True to return errors, False for normal operation
        """
        self._read_error = error

    def set_write_error(self, error: bool = True):
        """Configure writes to return errors.

        Args:
            error: True to return errors, False for normal operation
        """
        self._write_error = error

    async def read_holding_registers(self, address: int, count: int, device_id: int = 1) -> MockModbusResponse:
        """Read holding registers (function code 0x03).

        Args:
            address: Starting register address
            count: Number of registers to read
            device_id: Slave/unit ID

        Returns:
            MockModbusResponse with register values
        """
        self._read_calls.append(
            {
                "type": "holding",
                "address": address,
                "count": count,
                "device_id": device_id,
            }
        )

        if self._read_error:
            return MockModbusResponse(is_error=True)

        if self._next_read_result is not None:
            result = self._next_read_result
            self._next_read_result = None
            return result

        # Read from stored registers
        registers = []
        for i in range(count):
            reg_addr = address + i
            registers.append(self._registers.get(reg_addr, 0))

        return MockModbusResponse(registers=registers)

    async def read_input_registers(self, address: int, count: int, device_id: int = 1) -> MockModbusResponse:
        """Read input registers (function code 0x04).

        Args:
            address: Starting register address
            count: Number of registers to read
            device_id: Slave/unit ID

        Returns:
            MockModbusResponse with register values
        """
        self._read_calls.append(
            {
                "type": "input",
                "address": address,
                "count": count,
                "device_id": device_id,
            }
        )

        if self._read_error:
            return MockModbusResponse(is_error=True)

        if self._next_read_result is not None:
            result = self._next_read_result
            self._next_read_result = None
            return result

        # Read from stored registers
        registers = []
        for i in range(count):
            reg_addr = address + i
            registers.append(self._registers.get(reg_addr, 0))

        return MockModbusResponse(registers=registers)

    async def write_registers(self, address: int, values: List[int], device_id: int = 1) -> MockModbusResponse:
        """Write multiple registers (function code 0x10).

        Args:
            address: Starting register address
            values: List of values to write
            device_id: Slave/unit ID

        Returns:
            MockModbusResponse indicating success or failure
        """
        self._write_calls.append(
            {
                "address": address,
                "values": values,
                "device_id": device_id,
            }
        )

        if self._write_error:
            return MockModbusResponse(is_error=True)

        # Write to stored registers
        for i, value in enumerate(values):
            self._registers[address + i] = value

        return MockModbusResponse()

    async def write_single_register(self, address: int, value: int, device_id: int = 1) -> MockModbusResponse:
        """Write a single register (function code 0x06).

        Args:
            address: Register address
            value: Value to write
            device_id: Slave/unit ID

        Returns:
            MockModbusResponse indicating success or failure
        """
        return await self.write_registers(address, [value], device_id)

    def get_read_calls(self) -> List[Dict[str, Any]]:
        """Get list of all read calls made.

        Returns:
            List of call records with type, address, count, device_id
        """
        return self._read_calls.copy()

    def get_write_calls(self) -> List[Dict[str, Any]]:
        """Get list of all write calls made.

        Returns:
            List of call records with address, values, device_id
        """
        return self._write_calls.copy()

    def reset_calls(self):
        """Reset call history."""
        self._read_calls.clear()
        self._write_calls.clear()


def create_mock_modbus_client() -> MagicMock:
    """Create a MagicMock-based Modbus client for simpler test cases.

    Returns:
        MagicMock configured as an AsyncModbusClient
    """
    mock = MagicMock()
    mock.connected = True
    mock.connect = AsyncMock(return_value=True)
    mock.close = MagicMock()
    mock.read_holding_registers = AsyncMock(return_value=MockModbusResponse(registers=[0]))
    mock.read_input_registers = AsyncMock(return_value=MockModbusResponse(registers=[0]))
    mock.write_registers = AsyncMock(return_value=MockModbusResponse())
    return mock
