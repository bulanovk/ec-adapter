"""Tests for ModbusDataUpdateCoordinator."""
from typing import List, Tuple

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.ectocontrol_adapter.coordinator import ModbusDataUpdateCoordinator
from custom_components.ectocontrol_adapter.master import ModbusMasterCoordinator
from custom_components.ectocontrol_adapter.registers import (
    REG_R_ADAPTER_STATUS,
    REG_R_ADAPTER_VERSION,
    REG_R_ADAPTER_UPTIME,
    REG_R_CONTACT_CHANNELS,
    REG_RW_RELAY_CHANNELS,
    REGISTERS_R,
    REGISTERS_INPUT_8CH,
    REGISTERS_RELAY_R,
)
from tests.mocks.modbus_mock import MockModbusResponse


class TestModbusDataUpdateCoordinator:
    """Tests for ModbusDataUpdateCoordinator class."""

    @pytest.fixture
    def coordinator(self, hass, config_entry, pooled_client):
        """Create a ModbusDataUpdateCoordinator for testing."""
        master = ModbusMasterCoordinator(
            hass=hass,
            config_entry=config_entry,
            pool=None,  # type: ignore
            pool_key="tcp:192.168.1.100:502",
            pooled_client=pooled_client,
        )

        # Create data coordinator with sample registers
        registers: List[Tuple[int, dict]] = [
            (REG_R_ADAPTER_STATUS, REGISTERS_R[REG_R_ADAPTER_STATUS]),
            (REG_R_ADAPTER_VERSION, REGISTERS_R[REG_R_ADAPTER_VERSION]),
        ]

        return ModbusDataUpdateCoordinator(
            hass=hass,
            config_entry=config_entry,
            master=master,
            registers=registers,
            scan_interval=15,
        )

    @pytest.fixture
    def coordinator_with_input_registers(self, hass, config_entry, pooled_client):
        """Create coordinator with input registers (function code 0x04)."""
        master = ModbusMasterCoordinator(
            hass=hass,
            config_entry=config_entry,
            pool=None,  # type: ignore
            pool_key="tcp:192.168.1.100:502",
            pooled_client=pooled_client,
        )

        registers: List[Tuple[int, dict]] = [
            (REG_R_CONTACT_CHANNELS, REGISTERS_INPUT_8CH[REG_R_CONTACT_CHANNELS]),
        ]

        return ModbusDataUpdateCoordinator(
            hass=hass,
            config_entry=config_entry,
            master=master,
            registers=registers,
            scan_interval=5,
        )

    @pytest.mark.asyncio
    async def test_async_update_data_success(self, coordinator, mock_modbus_client):
        """Test successful data update."""
        mock_modbus_client.set_register(REG_R_ADAPTER_STATUS, 0x0865)
        mock_modbus_client.set_register(REG_R_ADAPTER_VERSION, 0x0102)

        data = await coordinator._async_update_data()

        assert data is not None
        assert REG_R_ADAPTER_STATUS in data
        assert REG_R_ADAPTER_VERSION in data
        assert data[REG_R_ADAPTER_STATUS] == [0x0865]
        assert data[REG_R_ADAPTER_VERSION] == [0x0102]

    @pytest.mark.asyncio
    async def test_async_update_data_input_registers(
        self, coordinator_with_input_registers, mock_modbus_client
    ):
        """Test data update with input registers (function code 0x04)."""
        mock_modbus_client.set_register(REG_R_CONTACT_CHANNELS, 0xFF00)

        data = await coordinator_with_input_registers._async_update_data()

        assert data is not None
        assert REG_R_CONTACT_CHANNELS in data
        # Verify data was read
        assert data[REG_R_CONTACT_CHANNELS] == [0xFF00]

    @pytest.mark.asyncio
    async def test_async_update_data_partial_failure(
        self, coordinator, mock_modbus_client
    ):
        """Test data update with partial register read failure."""
        # First register succeeds
        mock_modbus_client.set_register(REG_R_ADAPTER_STATUS, 0x0865)

        # Second register fails - set up error for next read
        def side_effect_read(address, count, device_id=1):
            if address == REG_R_ADAPTER_VERSION:
                return MockModbusResponse(is_error=True)
            return MockModbusResponse(registers=[mock_modbus_client._registers.get(address, 0)])

        original_read = mock_modbus_client.read_holding_registers
        mock_modbus_client.read_holding_registers = side_effect_read

        data = await coordinator._async_update_data()

        assert data is not None
        assert data[REG_R_ADAPTER_STATUS] == [0x0865]
        assert data[REG_R_ADAPTER_VERSION] is None  # Failed read

    @pytest.mark.asyncio
    async def test_async_update_data_all_fail(self, coordinator, mock_modbus_client):
        """Test data update when all reads fail."""
        mock_modbus_client._read_error = True

        data = await coordinator._async_update_data()

        assert data is not None
        # All registers should have None values
        assert all(value is None for value in data.values())

    @pytest.mark.asyncio
    async def test_async_update_data_exception(self, coordinator, mock_modbus_client):
        """Test data update raises UpdateFailed on exception."""
        # Make the read throw an exception
        async def raise_error(address, count, device_id=1):
            raise Exception("Connection lost")

        mock_modbus_client.read_holding_registers = raise_error

        with pytest.raises(UpdateFailed) as exc_info:
            await coordinator._async_update_data()

        assert "Connection lost" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_async_update_data_multi_register(
        self, mock_modbus_client, hass, config_entry, pooled_client
    ):
        """Test reading multi-register values (e.g., uint32 uptime)."""
        master = ModbusMasterCoordinator(
            hass=hass,
            config_entry=config_entry,
            pool=None,  # type: ignore
            pool_key="tcp:192.168.1.100:502",
            pooled_client=pooled_client,
        )

        registers: List[Tuple[int, dict]] = [
            (REG_R_ADAPTER_UPTIME, REGISTERS_R[REG_R_ADAPTER_UPTIME]),
        ]

        coordinator = ModbusDataUpdateCoordinator(
            hass=hass,
            config_entry=config_entry,
            master=master,
            registers=registers,
        )

        # Set up two registers for uint32 value
        mock_modbus_client.set_register(REG_R_ADAPTER_UPTIME, 0x0001)
        mock_modbus_client.set_register(REG_R_ADAPTER_UPTIME + 1, 0x0002)

        data = await coordinator._async_update_data()

        assert data is not None
        assert REG_R_ADAPTER_UPTIME in data
        # Should have read 2 registers
        assert len(data[REG_R_ADAPTER_UPTIME]) == 2

    def test_coordinator_stores_registers(self, coordinator):
        """Test that coordinator stores register list correctly."""
        assert hasattr(coordinator, "_registers")
        assert len(coordinator._registers) == 2

    def test_scan_interval(self, coordinator):
        """Test that scan interval is set correctly."""
        assert coordinator.update_interval.total_seconds() == 15

    @pytest.mark.asyncio
    async def test_unknown_register_raises_error(self, hass, config_entry, pooled_client):
        """Test that unknown register addresses raise ValueError."""
        master = ModbusMasterCoordinator(
            hass=hass,
            config_entry=config_entry,
            pool=None,  # type: ignore
            pool_key="tcp:192.168.1.100:502",
            pooled_client=pooled_client,
        )

        # Try to create coordinator with unknown register address
        unknown_address = 0xFFFF  # Not in REGISTERS_R
        registers: List[Tuple[int, dict]] = [
            (unknown_address, {"name": "unknown", "count": 1}),
        ]

        with pytest.raises(ValueError) as exc_info:
            ModbusDataUpdateCoordinator(
                hass=hass,
                config_entry=config_entry,
                master=master,
                registers=registers,
            )

        assert "Unknown registers" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_data_caching(self, coordinator, mock_modbus_client):
        """Test that data is cached between updates."""
        mock_modbus_client.set_register(REG_R_ADAPTER_STATUS, 0x0865)
        mock_modbus_client.set_register(REG_R_ADAPTER_VERSION, 0x0102)

        # First update
        data1 = await coordinator._async_update_data()

        # Change register values
        mock_modbus_client.set_register(REG_R_ADAPTER_STATUS, 0x0000)

        # Second update should get new values
        data2 = await coordinator._async_update_data()

        assert data1[REG_R_ADAPTER_STATUS] == [0x0865]
        assert data2[REG_R_ADAPTER_STATUS] == [0x0000]


class TestCoordinatorWithDeviceTypes:
    """Tests for coordinator with device-specific registers."""

    @pytest.mark.asyncio
    async def test_contact_splitter_coordinator(
        self, hass, config_entry, pooled_client, mock_modbus_client
    ):
        """Test coordinator with contact splitter registers."""
        master = ModbusMasterCoordinator(
            hass=hass,
            config_entry=config_entry,
            pool=None,  # type: ignore
            pool_key="tcp:192.168.1.100:502",
            pooled_client=pooled_client,
        )

        registers: List[Tuple[int, dict]] = [
            (REG_R_CONTACT_CHANNELS, REGISTERS_INPUT_8CH[REG_R_CONTACT_CHANNELS]),
        ]

        coordinator = ModbusDataUpdateCoordinator(
            hass=hass,
            config_entry=config_entry,
            master=master,
            registers=registers,
        )

        # Set contact states (channels 1-4 active in MSB)
        mock_modbus_client.set_register(REG_R_CONTACT_CHANNELS, 0x0F00)

        data = await coordinator._async_update_data()

        assert data is not None
        assert REG_R_CONTACT_CHANNELS in data
        # Value should represent channels 1-4 active
        assert data[REG_R_CONTACT_CHANNELS] == [0x0F00]

    @pytest.mark.asyncio
    async def test_relay_module_coordinator(
        self, hass, config_entry, pooled_client, mock_modbus_client
    ):
        """Test coordinator with relay module registers."""
        master = ModbusMasterCoordinator(
            hass=hass,
            config_entry=config_entry,
            pool=None,  # type: ignore
            pool_key="tcp:192.168.1.100:502",
            pooled_client=pooled_client,
        )

        registers: List[Tuple[int, dict]] = [
            (REG_RW_RELAY_CHANNELS, REGISTERS_RELAY_R[REG_RW_RELAY_CHANNELS]),
        ]

        coordinator = ModbusDataUpdateCoordinator(
            hass=hass,
            config_entry=config_entry,
            master=master,
            registers=registers,
        )

        # Set relay states (channels 1, 3, 5 active)
        mock_modbus_client.set_register(REG_RW_RELAY_CHANNELS, 0x1500)

        data = await coordinator._async_update_data()

        assert data is not None
        assert REG_RW_RELAY_CHANNELS in data
        assert data[REG_RW_RELAY_CHANNELS] == [0x1500]
