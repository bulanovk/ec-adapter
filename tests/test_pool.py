"""Tests for Modbus client connection pool."""
import asyncio
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ectocontrol_adapter.const import (
    QUEUE_TIMEOUT,
    OPT_MODBUS_TYPE,
    OPT_DEVICE,
    OPT_BAUDRATE,
    OPT_PARITY,
    OPT_STOPBITS,
    OPT_BYTESIZE,
    OPT_HOST,
    OPT_PORT,
)
from custom_components.ectocontrol_adapter.pool import (
    _get_pool_key,
    PooledClient,
    ModbusClientPool,
)


class TestGetPoolKey:
    """Tests for pool key generation."""

    def test_tcp_config(self):
        """Test pool key for TCP connection."""
        config = {
            OPT_MODBUS_TYPE: "tcp",
            OPT_HOST: "192.168.1.100",
            OPT_PORT: 502,
        }
        key = _get_pool_key(config)
        assert key == "tcp:192.168.1.100:502"

    def test_udp_config(self):
        """Test pool key for UDP connection."""
        config = {
            OPT_MODBUS_TYPE: "udp",
            OPT_HOST: "192.168.1.101",
            OPT_PORT: 5020,
        }
        key = _get_pool_key(config)
        assert key == "udp:192.168.1.101:5020"

    def test_rtuovertcp_config(self):
        """Test pool key for RTU-over-TCP connection."""
        config = {
            OPT_MODBUS_TYPE: "rtuovertcp",
            OPT_HOST: "192.168.1.102",
            OPT_PORT: 502,
        }
        key = _get_pool_key(config)
        assert key == "rtuovertcp:192.168.1.102:502"

    def test_serial_config(self):
        """Test pool key for serial connection."""
        config = {
            OPT_MODBUS_TYPE: "serial",
            OPT_DEVICE: "/dev/ttyUSB0",
            OPT_BAUDRATE: "19200",
            OPT_PARITY: "N",
            OPT_STOPBITS: "1",
            OPT_BYTESIZE: "8",
        }
        key = _get_pool_key(config)
        assert key == "serial:/dev/ttyUSB0:19200:N:1:8"

    def test_serial_config_different_settings(self):
        """Test that different serial settings produce different keys."""
        config1 = {
            OPT_MODBUS_TYPE: "serial",
            OPT_DEVICE: "/dev/ttyUSB0",
            OPT_BAUDRATE: "9600",
            OPT_PARITY: "N",
            OPT_STOPBITS: "1",
            OPT_BYTESIZE: "8",
        }
        config2 = {
            OPT_MODBUS_TYPE: "serial",
            OPT_DEVICE: "/dev/ttyUSB0",
            OPT_BAUDRATE: "19200",
            OPT_PARITY: "N",
            OPT_STOPBITS: "1",
            OPT_BYTESIZE: "8",
        }
        key1 = _get_pool_key(config1)
        key2 = _get_pool_key(config2)
        assert key1 != key2

    def test_unknown_config(self):
        """Test pool key for unknown connection type."""
        config = {
            OPT_MODBUS_TYPE: "unknown",
        }
        key = _get_pool_key(config)
        assert key.startswith("unknown:")


class TestPooledClient:
    """Tests for PooledClient class."""

    @pytest.fixture
    def pooled_client(self):
        """Create a PooledClient instance for testing."""
        config = {
            OPT_MODBUS_TYPE: "tcp",
            OPT_HOST: "192.168.1.100",
            OPT_PORT: 502,
        }
        return PooledClient(config)

    @pytest.mark.asyncio
    async def test_acquire_first_reference(self, pooled_client):
        """Test acquiring first reference starts processing."""
        with patch.object(
            pooled_client, "_connect", new_callable=AsyncMock
        ) as mock_connect:
            mock_connect.return_value = None

            result = await pooled_client.acquire()

            assert pooled_client._ref_count == 1
            assert pooled_client._is_running is True
            mock_connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_acquire_multiple_references(self, pooled_client):
        """Test acquiring multiple references increments count."""
        with patch.object(pooled_client, "_connect", new_callable=AsyncMock):
            await pooled_client.acquire()
            await pooled_client.acquire()
            await pooled_client.acquire()

            assert pooled_client._ref_count == 3

    @pytest.mark.asyncio
    async def test_release_last_reference(self, pooled_client):
        """Test releasing last reference stops processing."""
        with patch.object(pooled_client, "_connect", new_callable=AsyncMock):
            await pooled_client.acquire()
            await pooled_client.release()

            assert pooled_client._ref_count == 0
            assert pooled_client._is_running is False

    @pytest.mark.asyncio
    async def test_release_multiple_references(self, pooled_client):
        """Test releasing references decrements count."""
        with patch.object(pooled_client, "_connect", new_callable=AsyncMock):
            await pooled_client.acquire()
            await pooled_client.acquire()
            await pooled_client.release()

            assert pooled_client._ref_count == 1
            assert pooled_client._is_running is True

    @pytest.mark.asyncio
    async def test_submit_operation_not_running(self, pooled_client):
        """Test submitting operation when not running raises error."""
        with pytest.raises(RuntimeError, match="not running"):
            await pooled_client.submit_operation("read_holding_registers", {})

    @pytest.mark.asyncio
    async def test_submit_operation_success(self, pooled_client):
        """Test successful operation submission."""
        from tests.mocks.modbus_mock import MockModbusResponse

        mock_client = MagicMock()
        mock_client.connected = True
        mock_client.read_holding_registers = AsyncMock(
            return_value=MockModbusResponse(registers=[42])
        )
        pooled_client._client = mock_client

        with patch.object(
            pooled_client, "ensure_connected", new_callable=AsyncMock
        ) as mock_ensure:
            mock_ensure.return_value = True

            # Start the processing loop manually
            pooled_client._is_running = True
            pooled_client._processing_task = asyncio.create_task(
                pooled_client._process_queue()
            )

            result = await pooled_client.submit_operation(
                "read_holding_registers",
                {"address": 0x0010, "count": 1, "device_id": 1},
            )

            assert result.registers == [42]

            # Cleanup
            pooled_client._is_running = False
            pooled_client._processing_task.cancel()
            try:
                await pooled_client._processing_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_ensure_connected_already_connected(self, pooled_client):
        """Test ensure_connected when already connected."""
        mock_client = MagicMock()
        mock_client.connected = True
        pooled_client._client = mock_client

        result = await pooled_client.ensure_connected()

        assert result is True

    @pytest.mark.asyncio
    async def test_ensure_connected_reconnect(self, pooled_client):
        """Test ensure_connected triggers reconnection."""
        mock_client = MagicMock()
        mock_client.connected = False
        pooled_client._client = mock_client

        with patch.object(
            pooled_client, "_connect", new_callable=AsyncMock
        ) as mock_connect:
            mock_client.connected = True
            result = await pooled_client.ensure_connected()

            mock_connect.assert_called_once()
            assert result is True

    def test_ref_count_property(self, pooled_client):
        """Test ref_count property."""
        pooled_client._ref_count = 5
        assert pooled_client.ref_count == 5

    def test_is_connected_property(self, pooled_client):
        """Test is_connected property."""
        mock_client = MagicMock()
        mock_client.connected = True
        pooled_client._client = mock_client

        assert pooled_client.is_connected is True

    def test_is_connected_no_client(self, pooled_client):
        """Test is_connected when no client exists."""
        pooled_client._client = None
        assert pooled_client.is_connected is False


class TestModbusClientPool:
    """Tests for ModbusClientPool class."""

    @pytest.fixture
    def pool(self):
        """Create a ModbusClientPool instance for testing."""
        return ModbusClientPool()

    @pytest.fixture
    def tcp_config(self) -> Dict[str, Any]:
        """Return a TCP connection configuration."""
        return {
            OPT_MODBUS_TYPE: "tcp",
            OPT_HOST: "192.168.1.100",
            OPT_PORT: 502,
        }

    @pytest.fixture
    def tcp_config_same(self) -> Dict[str, Any]:
        """Return a TCP configuration with same key as tcp_config."""
        return {
            OPT_MODBUS_TYPE: "tcp",
            OPT_HOST: "192.168.1.100",
            OPT_PORT: 502,
        }

    @pytest.fixture
    def tcp_config_different(self) -> Dict[str, Any]:
        """Return a TCP configuration with different host."""
        return {
            OPT_MODBUS_TYPE: "tcp",
            OPT_HOST: "192.168.1.101",
            OPT_PORT: 502,
        }

    @pytest.mark.asyncio
    async def test_acquire_creates_new_client(self, pool, tcp_config):
        """Test acquiring creates new client for new pool key."""
        with patch.object(
            PooledClient, "acquire", new_callable=AsyncMock
        ) as mock_acquire:
            mock_acquire.return_value = True

            pool_key, client = await pool.acquire(tcp_config)

            assert pool_key == "tcp:192.168.1.100:502"
            assert pool_key in pool._pools
            mock_acquire.assert_called_once()

    @pytest.mark.asyncio
    async def test_acquire_reuses_existing_client(
        self, pool, tcp_config, tcp_config_same
    ):
        """Test acquiring reuses client for same pool key."""
        with patch.object(PooledClient, "acquire", new_callable=AsyncMock) as mock_acquire:
            mock_acquire.return_value = True

            key1, client1 = await pool.acquire(tcp_config)
            key2, client2 = await pool.acquire(tcp_config_same)

            assert key1 == key2
            assert client1 is client2
            assert mock_acquire.call_count == 2

    @pytest.mark.asyncio
    async def test_acquire_different_keys(self, pool, tcp_config, tcp_config_different):
        """Test acquiring creates different clients for different pool keys."""
        with patch.object(PooledClient, "acquire", new_callable=AsyncMock) as mock_acquire:
            mock_acquire.return_value = True

            key1, client1 = await pool.acquire(tcp_config)
            key2, client2 = await pool.acquire(tcp_config_different)

            assert key1 != key2
            assert client1 is not client2

    @pytest.mark.asyncio
    async def test_release_removes_client_when_zero_refs(self, pool, tcp_config):
        """Test releasing removes client when reference count reaches zero."""
        with patch.object(PooledClient, "acquire", new_callable=AsyncMock):
            with patch.object(
                PooledClient, "release", new_callable=AsyncMock
            ) as mock_release:
                mock_release.return_value = None

                pool_key, client = await pool.acquire(tcp_config)
                assert pool_key in pool._pools

                # Mock ref_count to be 0 after release
                client.ref_count = 0
                await pool.release(pool_key)

                assert pool_key not in pool._pools

    @pytest.mark.asyncio
    async def test_release_keeps_client_with_refs(self, pool, tcp_config):
        """Test releasing keeps client when references remain."""
        with patch.object(PooledClient, "acquire", new_callable=AsyncMock):
            with patch.object(
                PooledClient, "release", new_callable=AsyncMock
            ) as mock_release:
                mock_release.return_value = None

                pool_key, client = await pool.acquire(tcp_config)
                assert pool_key in pool._pools

                # Mock ref_count to be > 0 after release
                client.ref_count = 1
                await pool.release(pool_key)

                assert pool_key in pool._pools

    def test_get_existing_client(self, pool, tcp_config):
        """Test getting an existing client by key."""
        with patch.object(PooledClient, "acquire", new_callable=AsyncMock):
            pass  # Skip async setup for this test

        # Manually add a client to the pool
        mock_client = MagicMock()
        pool._pools["tcp:192.168.1.100:502"] = mock_client

        result = pool.get("tcp:192.168.1.100:502")
        assert result is mock_client

    def test_get_nonexistent_client(self, pool):
        """Test getting a nonexistent client returns None."""
        result = pool.get("nonexistent:key")
        assert result is None

    @pytest.mark.asyncio
    async def test_close_all(self, pool, tcp_config, tcp_config_different):
        """Test closing all pooled clients."""
        with patch.object(PooledClient, "acquire", new_callable=AsyncMock):
            with patch.object(
                PooledClient, "release", new_callable=AsyncMock
            ) as mock_release:
                mock_release.return_value = None

                await pool.acquire(tcp_config)
                await pool.acquire(tcp_config_different)

                assert len(pool._pools) == 2

                await pool.close_all()

                assert len(pool._pools) == 0
                assert mock_release.call_count == 2
