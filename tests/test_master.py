"""Tests for ModbusMasterCoordinator."""

import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ectocontrol_adapter.master import ModbusMasterCoordinator
from custom_components.ectocontrol_adapter.registers import (
    REG_DEFAULT_MAX_RETRIES,
    REG_DEFAULT_RETRY_DELAY,
    REG_STATUS_OK,
    REG_STATUS_OFFSET,
)
from tests.mocks.modbus_mock import MockModbusResponse


class TestModbusMasterCoordinator:
    """Tests for ModbusMasterCoordinator class."""

    @pytest.fixture
    def master(self, hass, config_entry, pooled_client):
        """Create a ModbusMasterCoordinator for testing."""
        return ModbusMasterCoordinator(
            hass=hass,
            config_entry=config_entry,
            pool=None,  # type: ignore
            pool_key="tcp:192.168.1.100:502",
            pooled_client=pooled_client,
        )

    @pytest.fixture
    def mock_response(self):
        """Create a mock Modbus response."""
        return MockModbusResponse(registers=[0x1234])

    @pytest.mark.asyncio
    async def test_read_holding_registers_success(self, master, mock_modbus_client):
        """Test successful holding register read."""
        mock_modbus_client.set_register(0x0010, 0x1234)

        result = await master.read_holding_registers(0x0010, 1)

        assert result is not None
        assert not result.isError()
        assert result.registers == [0x1234]

    @pytest.mark.asyncio
    async def test_read_holding_registers_error(self, master, mock_modbus_client):
        """Test holding register read with error."""
        mock_modbus_client._read_error = True

        result = await master.read_holding_registers(0x0010, 1)

        assert result.isError()

    @pytest.mark.asyncio
    async def test_read_input_registers_success(self, master, mock_modbus_client):
        """Test successful input register read."""
        mock_modbus_client.set_register(0x0010, 0x5678)

        result = await master.read_input_registers(0x0010, 1)

        assert result is not None
        assert not result.isError()
        assert result.registers == [0x5678]

    @pytest.mark.asyncio
    async def test_write_registers_success(self, master, mock_modbus_client):
        """Test successful register write with verification."""
        mock_modbus_client.set_register(0x0010, 0x1234)
        # Set status register to OK
        status_reg = 0x0010 + REG_STATUS_OFFSET
        mock_modbus_client.set_register(status_reg, REG_STATUS_OK)

        # Mock write_registers to actually update registers
        original_write = mock_modbus_client.write_registers

        async def mock_write(address, values, device_id=1):
            for i, val in enumerate(values):
                mock_modbus_client._registers[address + i] = val
            return MockModbusResponse()

        mock_modbus_client.write_registers = mock_write

        result = await master.write_registers(0x0010, [0x5678])

        assert result is True

    @pytest.mark.asyncio
    async def test_write_registers_skip_verify(self, master, mock_modbus_client):
        """Test register write without verification."""
        mock_modbus_client.set_register(0x0010, 0x1234)

        result = await master.write_registers(0x0010, [0x5678], skip_verify=True)

        assert result is True

    @pytest.mark.asyncio
    async def test_write_registers_with_custom_status_register(self, master, mock_modbus_client):
        """Test register write with custom status register."""
        mock_modbus_client.set_register(0x0010, 0x1234)
        mock_modbus_client.set_register(0x0050, REG_STATUS_OK)  # Custom status reg

        # Mock write_registers to actually update registers
        async def mock_write(address, values, device_id=1):
            for i, val in enumerate(values):
                mock_modbus_client._registers[address + i] = val
            return MockModbusResponse()

        mock_modbus_client.write_registers = mock_write

        result = await master.write_registers(0x0010, [0x5678], status_register=0x0050)

        assert result is True

    @pytest.mark.asyncio
    async def test_write_register_bit_set(self, master, mock_modbus_client):
        """Test setting a bit in a register."""
        mock_modbus_client.set_register(0x0010, 0x0000)  # Start with all bits clear

        # Mock write_registers to actually update registers
        async def mock_write(address, values, device_id=1):
            for i, val in enumerate(values):
                mock_modbus_client._registers[address + i] = val
            return MockModbusResponse()

        mock_modbus_client.write_registers = mock_write

        result = await master.write_register_bit(0x0010, 3, True)

        assert result is True
        # Bit 3 should be set
        assert mock_modbus_client._registers[0x0010] == 0x0008

    @pytest.mark.asyncio
    async def test_write_register_bit_clear(self, master, mock_modbus_client):
        """Test clearing a bit in a register."""
        mock_modbus_client.set_register(0x0010, 0xFFFF)  # Start with all bits set

        # Mock write_registers to actually update registers
        async def mock_write(address, values, device_id=1):
            for i, val in enumerate(values):
                mock_modbus_client._registers[address + i] = val
            return MockModbusResponse()

        mock_modbus_client.write_registers = mock_write

        result = await master.write_register_bit(0x0010, 3, False)

        assert result is True
        # Bit 3 should be clear
        assert mock_modbus_client._registers[0x0010] == 0xFFF7

    @pytest.mark.asyncio
    async def test_write_register_bit_read_failure(self, master, mock_modbus_client):
        """Test write_register_bit fails when read fails."""
        mock_modbus_client._read_error = True

        result = await master.write_register_bit(0x0010, 3, True)

        assert result is False

    @pytest.mark.asyncio
    async def test_write_register_bit_concurrent_operations(self, master, mock_modbus_client):
        """Test that concurrent bit operations on same register are serialized."""
        mock_modbus_client.set_register(0x0010, 0x0000)

        # Mock write_registers to actually update registers
        async def mock_write(address, values, device_id=1):
            await asyncio.sleep(0.01)  # Simulate some delay
            for i, val in enumerate(values):
                mock_modbus_client._registers[address + i] = val
            return MockModbusResponse()

        mock_modbus_client.write_registers = mock_write

        # Run two concurrent bit operations
        results = await asyncio.gather(
            master.write_register_bit(0x0010, 0, True),
            master.write_register_bit(0x0010, 1, True),
        )

        # Both should succeed
        assert all(results)

        # Both bits should be set
        final_value = mock_modbus_client._registers[0x0010]
        assert final_value & 0x0001  # Bit 0 set
        assert final_value & 0x0002  # Bit 1 set

    @pytest.mark.asyncio
    async def test_detect_device_type_success(self, master, mock_modbus_client):
        """Test successful device type detection."""
        # Set up device info registers
        # Register 0x0000: padding
        # Register 0x0001-0x0002: UID (24-bit)
        # Register 0x0003: MSB=device_type, LSB=channel_count
        mock_modbus_client.set_register(0x0000, 0x0000)
        mock_modbus_client.set_register(0x0001, 0x1234)  # UID MSB and mid
        mock_modbus_client.set_register(0x0002, 0x5600)  # UID LSB
        mock_modbus_client.set_register(0x0003, 0x1402)  # Device type 0x14, 2 channels

        result = await master.detect_device_type()

        assert result is not None
        assert result["device_type"] == 0x14
        assert result["channel_count"] == 2

    @pytest.mark.asyncio
    async def test_detect_device_type_failure(self, master, mock_modbus_client):
        """Test device type detection failure."""
        mock_modbus_client._read_error = True

        result = await master.detect_device_type()

        assert result is None

    def test_pool_key_property(self, master):
        """Test pool_key property."""
        assert master.pool_key == "tcp:192.168.1.100:502"

    def test_is_connected_property(self, master, pooled_client):
        """Test is_connected property."""
        pooled_client.is_connected = True
        assert master.is_connected is True

        pooled_client.is_connected = False
        assert master.is_connected is False

    @pytest.mark.asyncio
    async def test_verify_write_status_success(self, master, mock_modbus_client):
        """Test _verify_write_status succeeds when status is OK."""
        mock_modbus_client.set_register(0x0040, REG_STATUS_OK)

        result = await master._verify_write_status(
            0x0040, REG_STATUS_OK, REG_DEFAULT_MAX_RETRIES, REG_DEFAULT_RETRY_DELAY
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_write_status_retries(self, master, mock_modbus_client):
        """Test _verify_write_status retries on non-OK status."""
        mock_modbus_client.set_register(0x0040, 0xFF)  # Non-OK status

        result = await master._verify_write_status(0x0040, REG_STATUS_OK, 3, 0.01)  # Short delay for testing

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_write_status_eventually_succeeds(self, master, mock_modbus_client):
        """Test _verify_write_status succeeds after status changes to OK."""
        call_count = 0

        original_read = mock_modbus_client.read_holding_registers

        async def mock_read(address, count, device_id=1):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                # Return non-OK status for first 2 attempts
                mock_modbus_client.set_register(address, 0xFF)
            else:
                # Return OK status on 3rd attempt
                mock_modbus_client.set_register(address, REG_STATUS_OK)
            return await original_read(address, count, device_id)

        mock_modbus_client.read_holding_registers = mock_read

        result = await master._verify_write_status(0x0040, REG_STATUS_OK, 5, 0.01)

        assert result is True
        assert call_count == 3


class TestModbusMasterCoordinatorSlaveId:
    """Tests for slave ID handling."""

    @pytest.fixture
    def master_with_options(self, hass, config_entry_options, pooled_client):
        """Create a coordinator with options that override slave ID."""
        return ModbusMasterCoordinator(
            hass=hass,
            config_entry=config_entry_options,
            pool=None,  # type: ignore
            pool_key="tcp:192.168.1.100:502",
            pooled_client=pooled_client,
        )

    @pytest.mark.asyncio
    async def test_uses_options_slave_id(self, master_with_options, mock_modbus_client):
        """Test that options slave ID is used instead of data slave ID."""
        mock_modbus_client.set_register(0x0010, 0x1234)

        await master_with_options.read_holding_registers(0x0010, 1)

        # Check that the read was called with device_id from options (2)
        calls = mock_modbus_client.get_read_calls()
        assert len(calls) == 1
        assert calls[0]["device_id"] == 2  # From options, not data (1)
