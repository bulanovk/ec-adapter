"""Tests for ectoControl adapter config flow."""

# Mock HA modules that the config flow imports but aren't already mocked in conftest
import sys
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest

_MOCK_MODULES = [
    "homeassistant.config_entries",
    "homeassistant.helpers.dispatcher",
    "homeassistant.helpers.selector",
]
for _name in _MOCK_MODULES:
    sys.modules.setdefault(_name, MagicMock())


def _make_config_flow():
    """Create a config flow with mocked parent class methods."""
    from custom_components.ectocontrol_adapter.config_flow import ECAdapterConfigFlow

    flow = ECAdapterConfigFlow()
    flow.hass = MagicMock()
    flow.async_show_form = MagicMock(return_value={"type": "form"})
    flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
    flow.add_suggested_values_to_schema = MagicMock(side_effect=lambda schema, _: schema)
    return flow


def _make_options_flow(config_entry: Any = None):
    """Create an options flow with mocked parent class methods."""
    from custom_components.ectocontrol_adapter.config_flow import ECAdapterOptionsFlow

    if config_entry is None:
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {"name": "Test", "modbus_type": "tcp", "host": "1.2.3.4", "port": 502, "slave": 1}
        config_entry.options = {}
    flow = ECAdapterOptionsFlow(config_entry)
    flow.hass = MagicMock()
    flow.async_show_form = MagicMock(return_value={"type": "form"})
    flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
    flow.add_suggested_values_to_schema = MagicMock(side_effect=lambda schema, _: schema)
    return flow


class TestECAdapterConfigFlowConnectionStep:
    """Regression tests for ECAdapterConfigFlow.async_step_connection.

    Commit 232517d added ``int(user_input[OPT_SLAVE])`` to the connection step
    to fix a float-slave bug. The connection form (host/port for TCP,
    device/baudrate for serial) does NOT include ``OPT_SLAVE`` — it is
    collected in the init step only — so that line raised ``KeyError: 'slave'``
    on every connection-form submission.
    """

    @pytest.mark.asyncio
    async def test_connection_step_tcp_does_not_crash_without_slave(self):
        """TCP connection form (host/port) must not raise KeyError: 'slave'."""
        flow = _make_config_flow()
        flow.config_data = {"name": "Test", "modbus_type": "tcp", "slave": 1}

        # Connection form submission for TCP — no slave key
        connection_input: Dict[str, Any] = {"host": "192.168.1.100", "port": 502}

        # Should NOT raise KeyError: 'slave'
        await flow.async_step_connection(user_input=connection_input)

    @pytest.mark.asyncio
    async def test_connection_step_serial_does_not_crash_without_slave(self):
        """Serial connection form (device/baudrate/...) must not raise KeyError: 'slave'."""
        flow = _make_config_flow()
        flow.config_data = {"name": "Test", "modbus_type": "serial", "slave": 1}

        # Connection form submission for Serial — no slave key
        connection_input: Dict[str, Any] = {
            "device": "/dev/ttyUSB0",
            "baudrate": "19200",
            "bytesize": "8",
            "parity": "N",
            "stopbits": "1",
        }

        # Should NOT raise KeyError: 'slave'
        await flow.async_step_connection(user_input=connection_input)

    @pytest.mark.asyncio
    async def test_connection_step_preserves_existing_int_slave_in_config_data(self):
        """If config_data already has int slave, connection form must not corrupt it."""
        flow = _make_config_flow()
        flow.config_data = {"name": "Test", "modbus_type": "tcp", "slave": 5}

        await flow.async_step_connection(user_input={"host": "1.2.3.4", "port": 502})

        # Slave must remain int 5 in config_data after connection form submission
        assert flow.config_data["slave"] == 5
        assert isinstance(flow.config_data["slave"], int)


class TestECAdapterConfigFlowInitStep:
    """Tests for ECAdapterConfigFlow.async_step_user slave-ID conversion.

    Original concern: NumberSelector with mode=BOX returns a float (e.g. 5.0)
    for the slave field, which caused unique-ID mismatches between platforms
    (one platform used 5, another used 5.0). The init step is where the
    slave value is first collected, so int conversion must happen there.
    """

    @pytest.mark.asyncio
    async def test_init_step_converts_float_slave_to_int(self):
        """Init step must convert float slave (from NumberSelector) to int."""
        flow = _make_config_flow()
        # Avoid recursing into the connection step — we only want to assert
        # the init step's effect on config_data.
        flow.async_step_connection = AsyncMock(return_value={"type": "form"})

        init_input = {
            "name": "Test",
            "response_timeout": 5,
            "modbus_type": "tcp",
            "slave": 5.0,  # float — the original NumberSelector behaviour
        }

        await flow.async_step_user(user_input=init_input)

        assert flow.config_data["slave"] == 5
        assert isinstance(flow.config_data["slave"], int)

    @pytest.mark.asyncio
    async def test_init_step_preserves_int_slave(self):
        """Init step must not corrupt an int slave value."""
        flow = _make_config_flow()
        flow.async_step_connection = AsyncMock(return_value={"type": "form"})

        init_input = {
            "name": "Test",
            "response_timeout": 5,
            "modbus_type": "tcp",
            "slave": 5,  # already int
        }

        await flow.async_step_user(user_input=init_input)

        assert flow.config_data["slave"] == 5
        assert isinstance(flow.config_data["slave"], int)


class TestECAdapterOptionsFlowConnectionStep:
    """Same regression coverage for the options flow."""

    @pytest.mark.asyncio
    async def test_options_connection_step_tcp_does_not_crash_without_slave(self):
        """Options flow connection step must not raise KeyError: 'slave'."""
        flow = _make_options_flow()
        flow.config_data = {"name": "Test", "modbus_type": "tcp", "slave": 1}

        await flow.async_step_connection(user_input={"host": "1.2.3.4", "port": 502})

    @pytest.mark.asyncio
    async def test_options_init_step_converts_float_slave_to_int(self):
        """Options flow init step must convert float slave to int."""
        flow = _make_options_flow()
        flow.async_step_connection = AsyncMock(return_value={"type": "form"})

        init_input = {
            "name": "Test",
            "response_timeout": 5,
            "modbus_type": "tcp",
            "slave": 5.0,
        }

        await flow.async_step_init(user_input=init_input)

        assert flow.config_data["slave"] == 5
        assert isinstance(flow.config_data["slave"], int)
