"""Tests for sensor data converters.

This test file tests the converter logic in isolation without importing from
the actual integration module (which has Home Assistant dependencies).
"""

import datetime


def calculate_boottime_from_uptime(uptime: int, current_time: datetime.datetime) -> datetime.datetime:
    """Calculate boot time from uptime.

    This is the pure logic extracted from converters.py for isolated testing.

    Args:
        uptime: Uptime in seconds
        current_time: Current datetime

    Returns:
        Boot time datetime with seconds and microseconds zeroed
    """
    boottime = current_time - datetime.timedelta(seconds=uptime)
    return boottime.replace(second=0, microsecond=0)


class TestUptimeToBoottime:
    """Tests for uptime_to_boottime converter logic."""

    def test_uptime_zero(self):
        """Test with zero uptime."""
        current = datetime.datetime(2024, 1, 15, 12, 30, 45, 123456)
        result = calculate_boottime_from_uptime(0, current)

        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 12
        assert result.minute == 30
        assert result.second == 0
        assert result.microsecond == 0

    def test_uptime_one_hour(self):
        """Test with 1 hour uptime."""
        current = datetime.datetime(2024, 1, 15, 12, 30, 45, 123456)
        result = calculate_boottime_from_uptime(3600, current)

        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 11
        assert result.minute == 30
        assert result.second == 0
        assert result.microsecond == 0

    def test_uptime_large(self):
        """Test with large uptime (30 days)."""
        current = datetime.datetime(2024, 2, 15, 12, 30, 45, 123456)
        result = calculate_boottime_from_uptime(30 * 86400, current)

        assert result.year == 2024
        assert result.month == 1
        assert result.day == 16
        assert result.hour == 12
        assert result.minute == 30
        assert result.second == 0
        assert result.microsecond == 0

    def test_uptime_crosses_month_boundary(self):
        """Test uptime that crosses month boundary."""
        current = datetime.datetime(2024, 2, 5, 12, 30, 45, 123456)
        result = calculate_boottime_from_uptime(10 * 86400, current)

        assert result.year == 2024
        assert result.month == 1
        assert result.day == 26
        assert result.hour == 12
        assert result.minute == 30
        assert result.second == 0
        assert result.microsecond == 0

    def test_uptime_crosses_year_boundary(self):
        """Test uptime that crosses year boundary."""
        current = datetime.datetime(2024, 1, 5, 12, 30, 45, 123456)
        result = calculate_boottime_from_uptime(10 * 86400, current)

        assert result.year == 2023
        assert result.month == 12
        assert result.day == 26
        assert result.hour == 12
        assert result.minute == 30
        assert result.second == 0
        assert result.microsecond == 0

    def test_uptime_fractional_seconds_handled(self):
        """Test that fractional seconds in uptime are handled correctly."""
        current = datetime.datetime(2024, 1, 15, 12, 30, 45, 123456)
        result = calculate_boottime_from_uptime(90, current)  # 1.5 minutes

        assert result.minute == 29
        assert result.second == 0
        assert result.microsecond == 0

    def test_uptime_type_preservation(self):
        """Test that the function returns a datetime object."""
        current = datetime.datetime(2024, 1, 15, 12, 30, 45, 123456)
        result = calculate_boottime_from_uptime(3600, current)

        assert isinstance(result, datetime.datetime)

    def test_seconds_microseconds_zeroed(self):
        """Test that seconds and microseconds are always zeroed."""
        # Start with non-zero seconds and microseconds
        current = datetime.datetime(2024, 1, 15, 12, 30, 45, 999999)
        result = calculate_boottime_from_uptime(0, current)

        assert result.second == 0
        assert result.microsecond == 0

    def test_leap_year_february(self):
        """Test uptime calculation during leap year February."""
        # 2024 is a leap year
        current = datetime.datetime(2024, 3, 1, 12, 0, 0, 0)
        result = calculate_boottime_from_uptime(86400, current)  # 1 day back

        # Should be Feb 29 in leap year
        assert result.year == 2024
        assert result.month == 2
        assert result.day == 29

    def test_uptime_exactly_midnight(self):
        """Test uptime that results in exactly midnight."""
        current = datetime.datetime(2024, 1, 15, 0, 0, 30, 500000)
        result = calculate_boottime_from_uptime(30, current)

        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0

    def test_uptime_multiple_days(self):
        """Test uptime of multiple days."""
        current = datetime.datetime(2024, 1, 15, 12, 30, 45, 123456)
        result = calculate_boottime_from_uptime(7 * 86400, current)  # 7 days

        assert result.year == 2024
        assert result.month == 1
        assert result.day == 8
        assert result.hour == 12
        assert result.minute == 30
