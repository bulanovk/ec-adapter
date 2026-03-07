"""Tests for helpers module."""

from custom_components.ectocontrol_adapter.const import (
    MODBUS_TYPE_RTU_OVER_TCP,
    MODBUS_TYPE_SERIAL,
    MODBUS_TYPE_TCP,
    MODBUS_TYPE_UDP,
    OPT_BAUDRATE,
    OPT_BYTESIZE,
    OPT_DEVICE,
    OPT_HOST,
    OPT_MODBUS_TYPE,
    OPT_PARITY,
    OPT_PORT,
    OPT_RESPONSE_TIMEOUT,
    OPT_STOPBITS,
)
from custom_components.ectocontrol_adapter.helpers import create_modbus_client


class TestCreateModbusClient:
    """Tests for create_modbus_client function."""

    def test_create_tcp_client(self):
        """Test creating a TCP Modbus client."""
        config = {
            OPT_MODBUS_TYPE: MODBUS_TYPE_TCP,
            OPT_HOST: "192.168.1.100",
            OPT_PORT: "502",
            OPT_RESPONSE_TIMEOUT: "5",
        }

        client = create_modbus_client(config)

        assert client is not None
        assert client.comm_params.host == "192.168.1.100"
        assert client.comm_params.port == 502

    def test_create_udp_client(self):
        """Test creating a UDP Modbus client."""
        config = {
            OPT_MODBUS_TYPE: MODBUS_TYPE_UDP,
            OPT_HOST: "192.168.1.100",
            OPT_PORT: "502",
            OPT_RESPONSE_TIMEOUT: "5",
        }

        client = create_modbus_client(config)

        assert client is not None
        assert client.comm_params.host == "192.168.1.100"
        assert client.comm_params.port == 502

    def test_create_rtu_over_tcp_client(self):
        """Test creating an RTU-over-TCP Modbus client."""
        config = {
            OPT_MODBUS_TYPE: MODBUS_TYPE_RTU_OVER_TCP,
            OPT_HOST: "192.168.1.100",
            OPT_PORT: "502",
            OPT_RESPONSE_TIMEOUT: "5",
        }

        client = create_modbus_client(config)

        assert client is not None
        assert client.comm_params.host == "192.168.1.100"
        assert client.comm_params.port == 502

    def test_create_serial_client(self):
        """Test creating a serial Modbus client."""
        config = {
            OPT_MODBUS_TYPE: MODBUS_TYPE_SERIAL,
            OPT_DEVICE: "/dev/ttyUSB0",
            OPT_BAUDRATE: "19200",
            OPT_PARITY: "N",
            OPT_STOPBITS: "1",
            OPT_BYTESIZE: "8",
            OPT_RESPONSE_TIMEOUT: "5",
        }

        client = create_modbus_client(config)

        assert client is not None
        assert client.comm_params.port == "/dev/ttyUSB0"

    def test_create_tcp_client_with_int_port(self):
        """Test creating a TCP client with integer port."""
        config = {
            OPT_MODBUS_TYPE: MODBUS_TYPE_TCP,
            OPT_HOST: "192.168.1.100",
            OPT_PORT: 502,  # Integer instead of string
            OPT_RESPONSE_TIMEOUT: 5,  # Integer instead of string
        }

        client = create_modbus_client(config)

        assert client is not None
        assert client.comm_params.port == 502
