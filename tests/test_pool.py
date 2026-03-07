"""Tests for Modbus client connection pool."""

from custom_components.ectocontrol_adapter.pool import ModbusClientPool, PooledClient, _get_pool_key


class TestGetPoolKey:
    """Tests for _get_pool_key function."""

    def test_tcp_config(self):
        """Test pool key for TCP connection."""
        config = {
            "modbus_type": "tcp",
            "host": "192.168.1.100",
            "port": 502,
        }
        key = _get_pool_key(config)
        assert key == "tcp:192.168.1.100:502"

    def test_udp_config(self):
        """Test pool key for UDP connection."""
        config = {
            "modbus_type": "udp",
            "host": "192.168.1.101",
            "port": 5020,
        }
        key = _get_pool_key(config)
        assert key == "udp:192.168.1.101:5020"

    def test_rtuovertcp_config(self):
        """Test pool key for RTU-over-TCP connection."""
        config = {
            "modbus_type": "rtuovertcp",
            "host": "192.168.1.102",
            "port": 502,
        }
        key = _get_pool_key(config)
        assert key == "rtuovertcp:192.168.1.102:502"

    def test_serial_config(self):
        """Test pool key for serial connection."""
        config = {
            "modbus_type": "serial",
            "device": "/dev/ttyUSB0",
            "baudrate": "19200",
            "parity": "N",
            "stopbits": "1",
            "bytesize": "8",
        }
        key = _get_pool_key(config)
        assert key == "serial:/dev/ttyUSB0:19200:N:1:8"

    def test_serial_config_different_settings(self):
        """Test that different serial settings produce different keys."""
        config1 = {
            "modbus_type": "serial",
            "device": "/dev/ttyUSB0",
            "baudrate": "9600",
            "parity": "N",
            "stopbits": "1",
            "bytesize": "8",
        }
        config2 = {
            "modbus_type": "serial",
            "device": "/dev/ttyUSB0",
            "baudrate": "19200",
            "parity": "N",
            "stopbits": "1",
            "bytesize": "8",
        }
        key1 = _get_pool_key(config1)
        key2 = _get_pool_key(config2)
        assert key1 != key2

    def test_unknown_config(self):
        """Test pool key for unknown connection type."""
        config = {
            "modbus_type": "unknown",
        }
        key = _get_pool_key(config)
        assert key.startswith("unknown:")

    def test_tcp_config_with_int_port(self):
        """Test pool key for TCP with integer port."""
        config = {
            "modbus_type": "tcp",
            "host": "192.168.1.100",
            "port": 502,
        }
        key = _get_pool_key(config)
        assert key == "tcp:192.168.1.100:502"

    def test_tcp_config_with_string_port(self):
        """Test pool key for TCP with string port."""
        config = {
            "modbus_type": "tcp",
            "host": "192.168.1.100",
            "port": "502",
        }
        key = _get_pool_key(config)
        assert key == "tcp:192.168.1.100:502"

    def test_missing_optional_fields(self):
        """Test pool key with missing optional fields."""
        config = {
            "modbus_type": "tcp",
        }
        key = _get_pool_key(config)
        # Should still generate a key, host and port will be None
        assert "tcp:" in key


class TestPoolKeyUniqueness:
    """Tests for pool key uniqueness."""

    def test_different_hosts_different_keys(self):
        """Test that different hosts produce different keys."""
        config1 = {"modbus_type": "tcp", "host": "192.168.1.100", "port": 502}
        config2 = {"modbus_type": "tcp", "host": "192.168.1.101", "port": 502}
        key1 = _get_pool_key(config1)
        key2 = _get_pool_key(config2)
        assert key1 != key2

    def test_different_ports_different_keys(self):
        """Test that different ports produce different keys."""
        config1 = {"modbus_type": "tcp", "host": "192.168.1.100", "port": 502}
        config2 = {"modbus_type": "tcp", "host": "192.168.1.100", "port": 5020}
        key1 = _get_pool_key(config1)
        key2 = _get_pool_key(config2)
        assert key1 != key2

    def test_different_devices_different_keys(self):
        """Test that different serial devices produce different keys."""
        config1 = {
            "modbus_type": "serial",
            "device": "/dev/ttyUSB0",
            "baudrate": "19200",
            "parity": "N",
            "stopbits": "1",
            "bytesize": "8",
        }
        config2 = {
            "modbus_type": "serial",
            "device": "/dev/ttyUSB1",
            "baudrate": "19200",
            "parity": "N",
            "stopbits": "1",
            "bytesize": "8",
        }
        key1 = _get_pool_key(config1)
        key2 = _get_pool_key(config2)
        assert key1 != key2

    def test_different_baudrates_different_keys(self):
        """Test that different baud rates produce different keys."""
        config1 = {
            "modbus_type": "serial",
            "device": "/dev/ttyUSB0",
            "baudrate": "9600",
            "parity": "N",
            "stopbits": "1",
            "bytesize": "8",
        }
        config2 = {
            "modbus_type": "serial",
            "device": "/dev/ttyUSB0",
            "baudrate": "19200",
            "parity": "N",
            "stopbits": "1",
            "bytesize": "8",
        }
        key1 = _get_pool_key(config1)
        key2 = _get_pool_key(config2)
        assert key1 != key2

    def test_different_parities_different_keys(self):
        """Test that different parities produce different keys."""
        config1 = {
            "modbus_type": "serial",
            "device": "/dev/ttyUSB0",
            "baudrate": "19200",
            "parity": "N",
            "stopbits": "1",
            "bytesize": "8",
        }
        config2 = {
            "modbus_type": "serial",
            "device": "/dev/ttyUSB0",
            "baudrate": "19200",
            "parity": "E",
            "stopbits": "1",
            "bytesize": "8",
        }
        key1 = _get_pool_key(config1)
        key2 = _get_pool_key(config2)
        assert key1 != key2

    def test_different_types_different_keys(self):
        """Test that different modbus types produce different keys."""
        config1 = {"modbus_type": "tcp", "host": "192.168.1.100", "port": 502}
        config2 = {"modbus_type": "udp", "host": "192.168.1.100", "port": 502}
        key1 = _get_pool_key(config1)
        key2 = _get_pool_key(config2)
        assert key1 != key2


class TestPooledClient:
    """Tests for PooledClient class."""

    def test_pooled_client_initialization(self):
        """Test PooledClient initialization."""
        config = {
            "modbus_type": "tcp",
            "host": "192.168.1.100",
            "port": 502,
            "response_timeout": 5,
        }
        client = PooledClient(config)
        assert client.ref_count == 0
        assert client.is_connected is False

    def test_pooled_client_ref_count_property(self):
        """Test PooledClient ref_count property."""
        config = {"modbus_type": "tcp", "host": "192.168.1.100", "port": 502}
        client = PooledClient(config)
        assert client.ref_count == 0
        # Manually increment to test property
        client._ref_count = 5
        assert client.ref_count == 5


class TestModbusClientPool:
    """Tests for ModbusClientPool class."""

    def test_pool_initialization(self):
        """Test ModbusClientPool initialization."""
        pool = ModbusClientPool()
        assert pool._pools == {}

    def test_pool_get_nonexistent(self):
        """Test getting a non-existent pool key."""
        pool = ModbusClientPool()
        result = pool.get("nonexistent:key")
        assert result is None

    def test_pool_get_pool_key(self):
        """Test getting the pool key for a config."""
        config = {
            "modbus_type": "tcp",
            "host": "192.168.1.100",
            "port": 502,
        }
        # The pool key is generated internally by _get_pool_key
        expected_key = "tcp:192.168.1.100:502"
        actual_key = _get_pool_key(config)
        assert actual_key == expected_key
