"""Tests for ectocontrol_adapter.mixins helper functions."""

from unittest.mock import MagicMock

from custom_components.ectocontrol_adapter.mixins import get_device_info_for_register
from custom_components.ectocontrol_adapter.registers import REG_BOILER_DEPENDENT, REG_BOILER_WRITES


def _make_entry(entry_id: str):
    """Create a MagicMock with only ``entry_id`` attribute (mimics ConfigEntry)."""
    entry = MagicMock(spec=["entry_id"])
    entry.entry_id = entry_id
    return entry


def test_returns_main_device_when_no_entry_data():
    """No entry data registered -> fall back to main device identifier."""
    entry = _make_entry("e1")
    hass = MagicMock()
    hass.data = {}

    info = get_device_info_for_register(entry, hass, register_addr=0x0010)

    assert info["identifiers"] == {("ectocontrol_adapter", "e1")}


def test_returns_main_device_when_no_boiler_sub_device():
    """Entry exists but boiler sub-device not registered -> main device."""
    entry = _make_entry("e2")
    hass = MagicMock()
    hass.data = {"ectocontrol_adapter": {"e2": {"boiler_device_id": None}}}

    info = get_device_info_for_register(entry, hass, register_addr=0x0010)

    assert info["identifiers"] == {("ectocontrol_adapter", "e2")}


def test_routes_boiler_read_to_boiler_sub_device():
    """Boiler-side read register + boiler sub-device present -> routed to sub-device."""
    entry = _make_entry("e3")
    hass = MagicMock()
    hass.data = {"ectocontrol_adapter": {"e3": {"boiler_device_id": "boiler-id"}}}

    boiler_reg = next(iter(REG_BOILER_DEPENDENT))
    info = get_device_info_for_register(entry, hass, register_addr=boiler_reg, is_write=False)

    assert info["identifiers"] == {("ectocontrol_adapter", "e3_boiler")}
    assert info["via_device"] == ("ectocontrol_adapter", "e3")


def test_routes_boiler_write_to_boiler_sub_device():
    """Boiler-side write register + boiler sub-device present -> routed to sub-device."""
    entry = _make_entry("e4")
    hass = MagicMock()
    hass.data = {"ectocontrol_adapter": {"e4": {"boiler_device_id": "boiler-id"}}}

    boiler_reg = next(iter(REG_BOILER_WRITES))
    info = get_device_info_for_register(entry, hass, register_addr=boiler_reg, is_write=True)

    assert info["identifiers"] == {("ectocontrol_adapter", "e4_boiler")}


def test_non_boiler_register_stays_on_main_device():
    """Non-boiler register even with boiler sub-device -> main device."""
    entry = _make_entry("e5")
    hass = MagicMock()
    hass.data = {"ectocontrol_adapter": {"e5": {"boiler_device_id": "boiler-id"}}}

    info = get_device_info_for_register(entry, hass, register_addr=0x9999, is_write=True)

    assert info["identifiers"] == {("ectocontrol_adapter", "e5")}
