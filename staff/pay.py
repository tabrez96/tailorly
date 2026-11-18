"""Pay: pure helpers for day pay, overtime and weekly totals (no database)."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from core.formats import format_duration
from staff.attendance import HOURS_PER_DAY, hourly_rate, week_days

DAY_MINUTES = HOURS_PER_DAY * 60
CENTS = Decimal("0.01")
ZERO = Decimal(0)


@dataclass(frozen=True)
class DayPay:
    date: date
    paid: bool  # counted as a worked day
    running: bool  # today, started, not ended
    worked_minutes: int
    overtime_minutes: int
    base: Decimal
    overtime: Decimal

    @property
    def total(self) -> Decimal:
        return self.base + self.overtime


@dataclass(frozen=True)
class WeekPay:
    monday: date
    days: list[DayPay]
    daily_wage: Decimal
    multiplier: Decimal

    @property
    def days_paid(self) -> int:
        return sum(d.paid for d in self.days)

    @property
    def base_total(self) -> Decimal:
        return sum((d.base for d in self.days), ZERO)

    @property
    def overtime_minutes(self) -> int:
        return sum(d.overtime_minutes for d in self.days)

    @property
    def overtime_total(self) -> Decimal:
        return sum((d.overtime for d in self.days), ZERO)

    @property
    def total(self) -> Decimal:
        return self.base_total + self.overtime_total


def worked_minutes(start: datetime, end: datetime) -> int:
    return int((end - start).total_seconds() // 60)


def overtime_minutes(start: datetime, end: datetime) -> int:
    return max(worked_minutes(start, end) - DAY_MINUTES, 0)


def overtime_pay(minutes: int, daily_wage: Decimal, multiplier: Decimal) -> Decimal:
    pay = Decimal(minutes) / 60 * hourly_rate(daily_wage) * multiplier
    return pay.quantize(CENTS, ROUND_HALF_UP)


def day_pay(
    day: date,
    start: datetime | None,
    end: datetime | None,
    daily_wage: Decimal,
    multiplier: Decimal,
    today: date,
) -> DayPay:
    if start is None or (end is None and day != today):
        return DayPay(day, False, False, 0, 0, ZERO, ZERO)
    if end is None:
        return DayPay(day, True, True, 0, 0, daily_wage, ZERO)
    minutes = overtime_minutes(start, end)
    return DayPay(
        day,
        True,
        False,
        worked_minutes(start, end),
        minutes,
        daily_wage,
        overtime_pay(minutes, daily_wage, multiplier),
    )


def week_pay(
    monday: date,
    records: dict[date, tuple[datetime, datetime | None]],
    daily_wage: Decimal,
    multiplier: Decimal,
    today: date,
) -> WeekPay:
    days = [
        day_pay(d, *records.get(d, (None, None)), daily_wage, multiplier, today)
        for d in week_days(monday)
    ]
    return WeekPay(monday, days, daily_wage, multiplier)


def pay_day(monday: date) -> date:
    return monday + timedelta(days=5)


def short_period(monday: date) -> str:
    sunday = monday + timedelta(days=6)
    if monday.month == sunday.month:
        return f"{monday.day}–{sunday.day} {sunday:%b}"
    return f"{monday.day} {monday:%b}–{sunday.day} {sunday:%b}"


def payout_summary(days: int, overtime_minutes: int) -> str:
    text = f"{days} day{'' if days == 1 else 's'}"
    if overtime_minutes:
        text += f", {format_duration(overtime_minutes)} overtime"
    return text
