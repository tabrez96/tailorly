"""Display formats for days, clock times and durations, independent of the locale."""

from datetime import date, datetime, time, timedelta

from django.utils import timezone


def _local(value):
    if isinstance(value, datetime) and timezone.is_aware(value):
        return timezone.localtime(value)
    return value


def format_day(value: date | datetime | None) -> str:
    if value is None:
        return ""
    value = _local(value)
    return f"{value:%a} {value.day} {value:%b}"


def format_phone(digits: str) -> str:
    if len(digits) == 10:
        return f"{digits[:5]} {digits[5:]}"
    return digits


def format_month(value: date | datetime | None) -> str:
    if value is None:
        return ""
    value = _local(value)
    return f"{value:%b} {value.year}"


def format_clock(value: datetime | time | None) -> str:
    if value is None:
        return ""
    value = _local(value)
    suffix = "am" if value.hour < 12 else "pm"
    return f"{value.hour % 12 or 12}:{value.minute:02d} {suffix}"


def format_duration(value: int | timedelta | None) -> str:
    if value is None:
        return ""
    minutes = (
        int(value.total_seconds() // 60) if isinstance(value, timedelta) else value
    )
    if minutes < 0:
        raise ValueError("duration cannot be negative")
    hours, minutes = divmod(minutes, 60)
    if hours and minutes:
        return f"{hours}h {minutes}m"
    return f"{hours}h" if hours else f"{minutes}m"
