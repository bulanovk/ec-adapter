"""Sensor data converters for ectoControl adapter."""

import datetime

from homeassistant.util import dt as ha_dt


def uptime_to_boottime(uptime: int):
    """Convert device uptime to boot time.

    Args:
        uptime: Device uptime in seconds.

    Returns:
        Boot time as datetime with seconds and microseconds set to zero.
    """
    boottime = ha_dt.now() - datetime.timedelta(seconds=uptime)
    return boottime.replace(second=0, microsecond=0)
