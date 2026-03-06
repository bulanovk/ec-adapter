"""Tests for Modbus client connection pool.

Tests the connection pool logic without importing from the custom component.
"""

import asyncio
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest


def _get_pool_key(config: Dict[str, Any]) -> str:
    """Generate a unique key for connection pooling based on connection config.

    This is a copy of the function from pool.py for isolated testing.
    """
    modbus_type = config.get("modbus_type", "")

    if modbus_type == "serial":
        return f"serial:{config.get('device')}:{config.get('baudrate')}:{config.get('parity')}:{config.get('stopbits')}:{config.get('bytesize')}"
    elif modbus_type in ("tcp", "udp", "rtuovertcp"):
        return f"{modbus_type}:{config.get('host')}:{config.get('port')}"
    else:
        return f"unknown:{id(config)}"


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
