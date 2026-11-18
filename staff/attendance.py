"""Attendance: pure helpers for weeks, labels and hints, plus the day-record writes."""

from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from core.formats import format_clock
from core.money import format_inr
from staff.models import DayRecord

HOURS_PER_DAY = 8


def to_minute(dt: datetime) -> datetime:
    return dt.replace(second=0, microsecond=0)


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def week_days(monday: date) -> list[date]:
    return [monday + timedelta(days=i) for i in range(7)]


def parse_week(raw: str | None, today: date) -> date:
    try:
        monday = week_start(date.fromisoformat(raw or ""))
        # The page links to the previous and next weeks, so both must exist.
        monday - timedelta(days=7), monday + timedelta(days=7)
        return monday
    except ValueError, OverflowError:
        return week_start(today)


def week_label(monday: date) -> str:
    sunday = monday + timedelta(days=6)
    if monday.month == sunday.month:
        return f"Mon {monday.day} – Sun {sunday.day} {sunday:%b}"
    return f"Mon {monday.day} {monday:%b} – Sun {sunday.day} {sunday:%b}"


def greeting(hour: int) -> str:
    if hour < 12:
        return "Good morning"
    return "Good afternoon" if hour < 17 else "Good evening"


def first_name(name: str) -> str:
    return name.split()[0] if name.strip() else ""


def initials(name: str) -> str:
    return "".join(part[0] for part in name.split()[:2]).upper()


def hourly_rate(daily_wage: Decimal) -> Decimal:
    return daily_wage / HOURS_PER_DAY


def wage_hint(daily_wage: Decimal | None) -> str:
    if daily_wage is None:
        return "Hourly rate is the daily wage ÷ 8."
    return f"Hourly rate: {format_inr(hourly_rate(daily_wage))} (daily wage ÷ 8)."


def overtime_hint(daily_wage: Decimal | None, multiplier: Decimal | None) -> str:
    if daily_wage is None or multiplier is None:
        return "Hours past 8 in a day are paid at the hourly rate × this number."
    hourly = hourly_rate(daily_wage)
    return (
        f"Hours past 8 in a day are paid at {format_inr(hourly)} × "
        f"{multiplier.normalize():f} = {format_inr(hourly * multiplier)} an hour."
    )


def parse_decimal(raw) -> Decimal | None:
    try:
        value = Decimal(str(raw).strip())
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


def day_row(d: date, record: DayRecord | None, today: date) -> dict:
    if record is None:
        times, state = "Not recorded", "missing"
    elif record.end:
        times = f"{format_clock(record.start)} – {format_clock(record.end)}"
        state = "done"
    else:
        tail = "working" if d == today else "not ended"
        times, state = f"{format_clock(record.start)} – {tail}", "open"
    return {
        "date": d,
        "label": f"{d:%a} {d.day}",
        "times": times,
        "state": state,
        "can_edit": d <= today,
        "edited": bool(record and record.edited_by_owner),
    }


def start_day(employee, now: datetime) -> DayRecord:
    record, _ = DayRecord.objects.get_or_create(
        employee=employee,
        date=timezone.localdate(now),
        defaults={"start": to_minute(now)},
    )
    return record


def end_day(employee, now: datetime, *, by_owner: bool = False) -> DayRecord | None:
    record = DayRecord.objects.filter(
        employee=employee, date=timezone.localdate(now), end__isnull=True
    ).first()
    if record is None:
        return None
    record.end = max(to_minute(now), record.start)
    record.edited_by_owner = record.edited_by_owner or by_owner
    record.save()
    return record


def save_day(employee, day: date, start: time, end: time | None) -> DayRecord:
    record, _ = DayRecord.objects.update_or_create(
        employee=employee,
        date=day,
        defaults={
            "start": timezone.make_aware(datetime.combine(day, start)),
            "end": timezone.make_aware(datetime.combine(day, end)) if end else None,
            "edited_by_owner": True,
        },
    )
    return record


def day_card(employee, now: datetime) -> dict | None:
    if employee is None:
        return None
    record = DayRecord.objects.filter(
        employee=employee, date=timezone.localdate(now)
    ).first()
    hello = greeting(timezone.localtime(now).hour)
    card = {
        "greeting": f"{hello}, {first_name(employee.name)}",
        "now": now,
        "start": record.start if record else None,
        "end": record.end if record else None,
    }
    if record is None:
        return card | {"state": "not_started"}
    if record.end:
        return card | {"state": "ended"}
    return card | {"state": "started", "so_far": max(now - record.start, timedelta(0))}
