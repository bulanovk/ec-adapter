"""Pytest configuration and shared fixtures."""

import asyncio
import sys
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add custom_components to path for imports
sys.path.insert(0, "custom_components")

# Mock Home Assistant modules before any imports
sys.modules["homeassistant"] = MagicMock()
sys.modules["homeassistant.util"] = MagicMock()
sys.modules["homeassistant.util.dt"] = MagicMock()
sys.modules["homeassistant.core"] = MagicMock()
sys.modules["homeassistant.helpers"] = MagicMock()
sys.modules["homeassistant.helpers.update_coordinator"] = MagicMock()
sys.modules["homeassistant.helpers.entity"] = MagicMock()
sys.modules["homeassistant.const"] = MagicMock()
sys.modules["homeassistant.components"] = MagicMock()
sys.modules["homeassistant.components.sensor"] = MagicMock()
sys.modules["homeassistant.components.binary_sensor"] = MagicMock()
sys.modules["homeassistant.components.number"] = MagicMock()
sys.modules["homeassistant.components.select"] = MagicMock()
sys.modules["homeassistant.components.switch"] = MagicMock()
sys.modules["homeassistant.components.button"] = MagicMock()

# Mock pymodbus before any imports
sys.modules["pymodbus"] = MagicMock()
sys.modules["pymodbus.client"] = MagicMock()
sys.modules["pymodbus.pdu"] = MagicMock()

# Home Assistant test fixtures - disabled for unit tests
# pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations():
    """Enable custom integrations in HA tests."""
    yield


@pytest.fixture
def hass() -> MagicMock:
    """Create a mock Home Assistant instance.

    Returns:
        Mock HomeAssistant instance with basic setup
    """
    hass = MagicMock()
    hass.data = {}
    hass.config_entries = MagicMock()
    hass.config_entries.async_entries = MagicMock(return_value=[])
    hass.loop = asyncio.get_event_loop()
    return hass


@pytest.fixture
def config_entry() -> MagicMock:
    """Create a mock config entry for TCP connection.

    Returns:
        Mock ConfigEntry with TCP connection settings
    """
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = {
        "name": "Test Device",
        "modbus_type": "tcp",
        "host": "192.168.1.100",
        "port": 502,
        "slave": 1,
        "response_timeout": 5,
    }
    entry.options = {}
    entry.runtime_data = None
    return entry


@pytest.fixture
def config_entry_serial() -> MagicMock:
    """Create a mock config entry for serial connection.

    Returns:
        Mock ConfigEntry with serial connection settings
    """
    entry = MagicMock()
    entry.entry_id = "test_entry_serial"
    entry.data = {
        "name": "Test Serial Device",
        "modbus_type": "serial",
        "device": "/dev/ttyUSB0",
        "baudrate": 19200,
        "parity": "N",
        "stopbits": 1,
        "bytesize": 8,
        "slave": 1,
        "response_timeout": 5,
    }
    entry.options = {}
    entry.runtime_data = None
    return entry


@pytest.fixture
def config_entry_options() -> MagicMock:
    """Create a mock config entry with options.

    Returns:
        Mock ConfigEntry with options set (options override data)
    """
    entry = MagicMock()
    entry.entry_id = "test_entry_options"
    entry.data = {
        "name": "Test Device",
        "modbus_type": "tcp",
        "host": "192.168.1.100",
        "port": 502,
        "slave": 1,
        "response_timeout": 5,
    }
    entry.options = {
        "slave": 2,  # Override slave ID via options
    }
    entry.runtime_data = None
    return entry


@pytest.fixture
def mock_modbus_client():
    """Create a mock Modbus client with default behavior.

    Returns:
        MockModbusClient instance
    """
    from tests.mocks.modbus_mock import MockModbusClient

    client = MockModbusClient()
    client._connected = True
    return client


@pytest.fixture
def pooled_client(mock_modbus_client) -> MagicMock:
    """Create a mock PooledClient with a mock Modbus client.

    Returns:
        Mock PooledClient instance
    """
    from tests.mocks.modbus_mock import MockModbusResponse

    pooled = MagicMock()
    pooled._client = mock_modbus_client
    pooled._ref_count = 1
    pooled._is_running = True
    pooled.is_connected = True

    async def mock_submit_operation(op: str, data: Dict[str, Any]):
        """Mock submit_operation that delegates to the client."""
        if op == "read_holding_registers":
            return await mock_modbus_client.read_holding_registers(
                address=data["address"],
                count=data["count"],
                device_id=data["device_id"],
            )
        elif op == "read_input_registers":
            return await mock_modbus_client.read_input_registers(
                address=data["address"],
                count=data["count"],
                device_id=data["device_id"],
            )
        elif op == "write_registers":
            return await mock_modbus_client.write_registers(
                address=data["address"],
                values=data["values"],
                device_id=data["device_id"],
            )
        else:
            raise ValueError(f"Unknown operation: {op}")

    pooled.submit_operation = mock_submit_operation

    async def mock_acquire():
        pooled._ref_count += 1
        return True

    async def mock_release():
        pooled._ref_count -= 1

    pooled.acquire = mock_acquire
    pooled.release = mock_release
    pooled.ref_count = 1

    return pooled


@pytest.fixture
def mock_pool(pooled_client) -> MagicMock:
    """Create a mock ModbusClientPool.

    Returns:
        Mock ModbusClientPool instance
    """
    pool = MagicMock()
    pool._pools = {}

    async def mock_acquire(config: Dict[str, Any]):
        return ("tcp:192.168.1.100:502", pooled_client)

    async def mock_release(pool_key: str):
        pass

    pool.acquire = mock_acquire
    pool.release = mock_release
    pool.get = MagicMock(return_value=pooled_client)

    return pool


@pytest.fixture
def master_coordinator(hass, config_entry, pooled_client) -> "ModbusMasterCoordinator":
    """Create a ModbusMasterCoordinator for testing.

    Returns:
        ModbusMasterCoordinator instance with mock dependencies
    """
    from custom_components.ectocontrol_adapter.master import ModbusMasterCoordinator

    coordinator = ModbusMasterCoordinator(
        hass=hass,
        config_entry=config_entry,
        pool=None,  # type: ignore
        pool_key="tcp:192.168.1.100:502",
        pooled_client=pooled_client,
    )
    return coordinator


@pytest.fixture
def device_info_registers() -> Dict[str, Any]:
    """Sample device info registers for device type detection.

    Returns:
        Dict with device_type, device_uid, channel_count for testing
    """
    return {
        "registers": [0x0000, 0x1234, 0x5678, 0x1402],  # Device type 0x14 (OpenTherm v2), 2 channels
        "expected": {
            "device_type": 0x14,
            "device_uid": 0x123456,
            "channel_count": 2,
        },
    }


@pytest.fixture
def sample_adapter_status_registers() -> Dict[int, int]:
    """Sample adapter status register values.

    Returns:
        Dict mapping register addresses to sample values
    """
    return {
        0x0010: 0x0865,  # Status with connectivity bit set (0x0800) and reboot code 0x65
        0x0011: 0x0102,  # Version: HW 0x01, SW 0x02
        0x0012: 3600,  # Uptime: 1 hour
        0x0013: 0,  # Uptime MSB
    }


@pytest.fixture
def event_loop():
    """Create an event loop for async tests.

    Returns:
        Event loop for the test session
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Mark all tests in this directory as asyncio
def pytest_collection_modifyitems(config, items):
    """Add asyncio marker to all async tests."""
    for item in items:
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.asyncio)
