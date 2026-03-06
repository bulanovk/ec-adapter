"""Config flow for ectoControl adapter."""

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import *  # noqa F403
from .helpers import create_modbus_client
from .pool import POOL_KEY, ModbusClientPool, _get_pool_key

# Generic register for connectivity validation (exists on all device types)
REG_DEVICE_DESCRIPTOR = 0x0003  # MSB: device type, LSB: channel count

_LOGGER = logging.getLogger(__name__)


async def create_schema(hass, config_entry=None, user_input=None, type="init"):
    """Create common schema for ConfigFlow and OptionsFlow."""
    if type == "serial":
        return vol.Schema(
            {
                # Serial settings
                vol.Required(OPT_DEVICE, default=DEFAULT_DEVICE): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Required(OPT_BAUDRATE, default=str(DEFAULT_SERIAL_BAUDRATE)): SelectSelector(
                    SelectSelectorConfig(options=SERIAL_BAUDRATES, mode=SelectSelectorMode.DROPDOWN)
                ),
                vol.Required(OPT_BYTESIZE, default=str(DEFAULT_SERIAL_BYTESIZE)): SelectSelector(
                    SelectSelectorConfig(options=SERIAL_BYTESIZES, mode=SelectSelectorMode.DROPDOWN)
                ),
                vol.Required(OPT_PARITY, default=DEFAULT_PARITY): SelectSelector(
                    SelectSelectorConfig(options=SERIAL_PARITIES, mode=SelectSelectorMode.DROPDOWN)
                ),
                vol.Required(OPT_STOPBITS, default=str(DEFAULT_STOPBITS)): SelectSelector(
                    SelectSelectorConfig(options=SERIAL_STOPBITS, mode=SelectSelectorMode.DROPDOWN)
                ),
            }
        )
    elif type in ("tcp", "udp", "rtuovertcp"):
        return vol.Schema(
            {
                # Host + Port settings
                vol.Required(OPT_HOST): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                vol.Required(OPT_PORT, default=DEFAULT_PORT): NumberSelector(
                    NumberSelectorConfig(min=1, max=65535, mode=NumberSelectorMode.BOX)
                ),
            }
        )
    else:
        return vol.Schema(
            {
                vol.Required(OPT_NAME): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                # Settings
                vol.Required(OPT_RESPONSE_TIMEOUT, default=DEFAULT_RESPONSE_TIMEOUT): NumberSelector(
                    NumberSelectorConfig(min=1, max=10, mode=NumberSelectorMode.BOX)
                ),
                vol.Required(OPT_MODBUS_TYPE, default=DEFAULT_MODBUS_TYPE): SelectSelector(
                    SelectSelectorConfig(options=MODBUS_TYPES, mode=SelectSelectorMode.DROPDOWN)
                ),
                vol.Required(OPT_SLAVE, default=DEFAULT_SLAVE_ID): NumberSelector(
                    NumberSelectorConfig(min=0, max=248, mode=NumberSelectorMode.BOX)
                ),
            }
        )


async def check_user_input(user_input, pool: ModbusClientPool = None):
    """
    Validate connection to Modbus device.

    Uses existing pooled connection if available, otherwise creates a temporary client.
    """
    errors = {}
    pool_key = _get_pool_key(user_input)
    slave_id = int(user_input[OPT_SLAVE])

    # Check if we can reuse an existing pooled connection
    pooled_client = pool.get(pool_key) if pool else None

    if pooled_client:
        # Use existing pooled connection (port already locked by pool)
        _LOGGER.debug("Using pooled connection for validation: %s", pool_key)
        try:
            if not pooled_client.is_connected:
                errors["base"] = "ec_modbus_connect_error"
                _LOGGER.error("Pooled client is not connected")
            else:
                # Read device descriptor to validate connectivity
                device_info = await pooled_client.submit_operation(
                    "read_holding_registers", {"address": REG_DEVICE_DESCRIPTOR, "count": 1, "device_id": slave_id}
                )

                if device_info is None or device_info.isError():
                    errors["base"] = "ec_modbus_connect_error"
                    _LOGGER.error("Modbus error reading device descriptor: %s", device_info)
                else:
                    device_type = (device_info.registers[0] >> 8) & 0xFF
                    channel_count = device_info.registers[0] & 0xFF
                    _LOGGER.info(
                        "Device detected: type=0x%02X (%s), channels=%d",
                        device_type,
                        DEVICE_TYPE_NAMES.get(device_type, "Unknown"),
                        channel_count,
                    )
        except Exception as e:
            errors["base"] = "ec_modbus_connect_error"
            _LOGGER.error("Failed to validate using pooled connection: %s", e)
    else:
        # No pooled connection - create temporary client
        _LOGGER.debug("Creating temporary client for validation: %s", pool_key)
        client = create_modbus_client(user_input)
        try:
            result = await client.connect()
            if not result:
                errors["base"] = "ec_modbus_connect_error"
                _LOGGER.error("Failed to connect to Modbus device")
            else:
                _LOGGER.info("Successfully connected to Modbus device")

                # Read generic device descriptor register to validate connectivity
                device_info = await client.read_holding_registers(
                    address=REG_DEVICE_DESCRIPTOR, count=1, device_id=slave_id
                )

                if device_info is None or device_info.isError():
                    errors["base"] = "ec_modbus_connect_error"
                    _LOGGER.error("Modbus error reading device descriptor: %s", device_info)
                else:
                    device_type = (device_info.registers[0] >> 8) & 0xFF
                    channel_count = device_info.registers[0] & 0xFF
                    _LOGGER.info(
                        "Device detected: type=0x%02X (%s), channels=%d",
                        device_type,
                        DEVICE_TYPE_NAMES.get(device_type, "Unknown"),
                        channel_count,
                    )

        except Exception as e:
            errors["base"] = "ec_modbus_connect_error"
            _LOGGER.error("Failed to connect to Modbus device: %s", e)
        finally:
            client.close()

    return errors


def _get_pool(hass) -> ModbusClientPool:
    """Get the ModbusClientPool from hass.data."""
    from .const import DOMAIN

    return hass.data.get(DOMAIN, {}).get(POOL_KEY)


class ECAdapterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ectoControl Adapter."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.config_data = {}
        self.next_step = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if self.next_step:
            return await self.next_step(user_input)

        _LOGGER.debug("Request to create config (init step): %s", user_input)

        if user_input is not None:
            self.config_data.update(user_input)
            self.next_step = self.async_step_connection
            return await self.async_step_connection()

        schema = await create_schema(hass=self.hass, user_input=user_input)
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_connection(self, user_input=None):
        """Handle the connection step."""
        _LOGGER.debug("Request to create config (connection step): %s", user_input)

        errors = {}
        if user_input is not None:
            self.config_data.update(user_input)
            pool = _get_pool(self.hass)
            errors = await check_user_input(self.config_data, pool)
            if not errors:
                return self.async_create_entry(title=self.config_data[OPT_NAME], data=self.config_data)

        schema = await create_schema(hass=self.hass, user_input=user_input, type=self.config_data[OPT_MODBUS_TYPE])
        return self.async_show_form(
            step_id="user", data_schema=self.add_suggested_values_to_schema(schema, user_input or {}), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return ECAdapterOptionsFlow(config_entry)


class ECAdapterOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for ectoControl Adapter."""

    def __init__(self, config_entry):
        """Initialize the options flow.

        Args:
            config_entry: The config entry being configured.
        """
        if HA_VERSION < "2024.12":
            self.config_entry = config_entry
        self.config_data = {}
        self.next_step = None

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if self.next_step:
            return await self.next_step(user_input)

        _LOGGER.debug("Request to update options (init step): %s", user_input)

        errors = {}
        if user_input is not None:
            self.config_data.update(user_input)
            self.next_step = self.async_step_connection
            return await self.async_step_connection()

        schema = await create_schema(hass=self.hass, config_entry=self.config_entry, user_input=user_input)

        options = self.config_entry.options or self.config_entry.data
        return self.async_show_form(
            step_id="init", data_schema=self.add_suggested_values_to_schema(schema, options), errors=errors
        )

    async def async_step_connection(self, user_input=None):
        """Handle the connection step."""
        _LOGGER.debug("Request to update options (connection step): %s", user_input)

        errors = {}
        if user_input is not None:
            self.config_data.update(user_input)
            pool = _get_pool(self.hass)
            errors = await check_user_input(self.config_data, pool)
            if not errors:
                # Update configuration
                self.hass.config_entries.async_update_entry(
                    self.config_entry, title=self.config_data[OPT_NAME], options=self.config_data
                )

                # Send signal to subscribers
                async_dispatcher_send(self.hass, f"{SENSOR_UPDATE_SIGNAL}_{self.config_entry.entry_id}")

                return self.async_create_entry(title="", data=self.config_data)

        schema = await create_schema(
            hass=self.hass,
            config_entry=self.config_entry,
            user_input=user_input,
            type=self.config_data[OPT_MODBUS_TYPE],
        )

        options = user_input or self.config_entry.options or self.config_entry.data or {}
        return self.async_show_form(
            step_id="init", data_schema=self.add_suggested_values_to_schema(schema, options), errors=errors
        )
