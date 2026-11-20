from datetime import date

import pytest

from orders.making import ordinal, parse_duration, queue_place


def test_parse_duration_formats():
    assert parse_duration("2h 30m") == 150
    assert parse_duration("2h") == 120
    assert parse_duration("45m") == 45
    assert parse_duration("2:30") == 150
    assert parse_duration("2") == 120
    assert parse_duration(" 1H5M ") == 65
    assert parse_duration("") is None


@pytest.mark.parametrize("text", ["abc", "2h 75m", "0", "100h", "2:7", "2:75"])
def test_parse_duration_rejects(text):
    with pytest.raises(ValueError, match="Enter a time like 2h 30m."):
        parse_duration(text)


def test_queue_place():
    d1, d2, d3 = date(2026, 12, 1), date(2026, 12, 2), date(2026, 12, 3)
    assert queue_place([], d2) == 1
    assert queue_place([d1, d3], d2) == 2
    assert queue_place([d2], d2) == 2
    assert queue_place([d1, None], None) == 3
    assert queue_place([None, None], d3) == 1


def test_ordinal():
    got = [ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22, 23, 101)]
    assert got == [
        "1st", "2nd", "3rd", "4th", "11th", "12th", "13th",
        "21st", "22nd", "23rd", "101st",
    ]  # fmt: skip
