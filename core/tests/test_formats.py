from datetime import UTC, date, datetime, time, timedelta

import pytest

from core.formats import format_clock, format_day, format_duration


def test_day_examples():
    assert format_day(date(2026, 11, 12)) == "Thu 12 Nov"
    assert format_day(date(2026, 11, 2)) == "Mon 2 Nov"
    assert format_day(datetime(2026, 11, 12, 20, 0, tzinfo=UTC)) == "Fri 13 Nov"


def test_clock_examples():
    assert format_clock(time(9, 2)) == "9:02 am"
    assert format_clock(time(0, 5)) == "12:05 am"
    assert format_clock(time(12, 0)) == "12:00 pm"
    assert format_clock(time(18, 30)) == "6:30 pm"
    assert format_clock(datetime(2026, 11, 12, 3, 32, tzinfo=UTC)) == "9:02 am"


def test_duration_examples():
    assert format_duration(160) == "2h 40m"
    assert format_duration(180) == "3h"
    assert format_duration(40) == "40m"
    assert format_duration(0) == "0m"
    assert format_duration(timedelta(hours=2, minutes=40, seconds=59)) == "2h 40m"


def test_blank_and_invalid():
    assert format_day(None) == ""
    assert format_clock(None) == ""
    assert format_duration(None) == ""
    with pytest.raises(ValueError):
        format_duration(-1)
