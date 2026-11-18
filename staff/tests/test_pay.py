from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from staff.pay import (
    day_pay,
    pay_day,
    payout_summary,
    short_period,
    week_pay,
)

IST = ZoneInfo("Asia/Kolkata")
MONDAY = date(2026, 11, 9)
WAGE = Decimal(800)
ONE = Decimal(1)


def at(day, hour, minute=0):
    return datetime(2026, 11, day, hour, minute, tzinfo=IST)


def test_six_days_at_800_is_4800():
    records = {date(2026, 11, d): (at(d, 9), at(d, 17)) for d in range(9, 15)}
    week = week_pay(MONDAY, records, WAGE, ONE, date(2026, 11, 16))
    assert week.total == 4800
    assert week.days_paid == 6


def test_ten_hour_day_1x_overtime_200():
    pay = day_pay(MONDAY, at(9, 9), at(9, 19), WAGE, ONE, date(2026, 11, 16))
    assert pay.overtime == 200
    assert pay.total == 1000


def test_ten_hour_day_2x_overtime_400():
    pay = day_pay(MONDAY, at(9, 9), at(9, 19), WAGE, Decimal(2), date(2026, 11, 16))
    assert pay.overtime == 400


def test_9h37m_is_97_overtime_minutes():
    pay = day_pay(MONDAY, at(9, 9), at(9, 18, 37), WAGE, ONE, date(2026, 11, 16))
    assert pay.overtime_minutes == 97


def test_day_with_only_start_is_unpaid():
    pay = day_pay(MONDAY, at(9, 9), None, WAGE, ONE, date(2026, 11, 12))
    assert pay.paid is False
    assert pay.total == 0


def test_running_today_counts_base_only():
    pay = day_pay(MONDAY, at(9, 9), None, WAGE, ONE, MONDAY)
    assert pay.running
    assert pay.base == 800
    assert pay.overtime == 0


def test_no_record_is_unpaid():
    pay = day_pay(MONDAY, None, None, WAGE, ONE, MONDAY)
    assert not pay.paid
    assert pay.total == 0


def test_exactly_eight_hours_no_overtime():
    pay = day_pay(MONDAY, at(9, 9), at(9, 17), WAGE, ONE, MONDAY)
    assert pay.overtime_minutes == 0
    assert pay.overtime == 0


def test_one_minute_over_is_rounded_to_paise():
    pay = day_pay(MONDAY, at(9, 9), at(9, 17, 1), WAGE, ONE, MONDAY)
    assert pay.overtime_minutes == 1
    assert pay.overtime == Decimal("1.67")


def test_week_has_seven_days_from_monday():
    week = week_pay(MONDAY, {}, WAGE, ONE, MONDAY)
    assert [d.date.weekday() for d in week.days] == list(range(7))
    assert week.total == 0
    assert week.overtime_minutes == 0


def test_short_period_same_and_cross_month():
    assert short_period(date(2026, 11, 9)) == "9–15 Nov"
    assert short_period(date(2026, 10, 26)) == "26 Oct–1 Nov"


def test_payout_summary():
    assert payout_summary(1, 0) == "1 day"
    assert payout_summary(6, 0) == "6 days"
    assert payout_summary(6, 60) == "6 days, 1h overtime"
    assert payout_summary(6, 97) == "6 days, 1h 37m overtime"


def test_pay_day_is_saturday():
    assert pay_day(MONDAY) == date(2026, 11, 14)
