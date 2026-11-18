from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from staff.attendance import (
    day_card,
    day_row,
    end_day,
    first_name,
    greeting,
    hourly_rate,
    initials,
    overtime_hint,
    parse_week,
    save_day,
    start_day,
    to_minute,
    wage_hint,
    week_days,
    week_label,
    week_start,
)
from staff.models import DayRecord, Employee

IST = ZoneInfo("Asia/Kolkata")
THU = date(2026, 11, 12)


def at(hour, minute=0, second=0, day=THU):
    return datetime(day.year, day.month, day.day, hour, minute, second, tzinfo=IST)


def make_employee(phone="9000011116", name="Ali Khan"):
    return Employee.objects.create(name=name, phone=phone, daily_wage=800)


def test_to_minute_drops_seconds():
    assert to_minute(at(9, 2, 47)) == at(9, 2)


def test_week_start_and_days():
    assert week_start(THU) == date(2026, 11, 9)
    days = week_days(date(2026, 11, 9))
    assert len(days) == 7
    assert days[-1] == date(2026, 11, 15)


def test_parse_week_valid_and_invalid():
    assert parse_week("2026-11-12", THU) == date(2026, 11, 9)
    assert parse_week("nope", THU) == date(2026, 11, 9)
    assert parse_week(None, date(2026, 11, 18)) == date(2026, 11, 16)


def test_parse_week_out_of_range_falls_back():
    assert parse_week("9999-12-31", THU) == date(2026, 11, 9)
    assert parse_week("0001-01-01", THU) == date(2026, 11, 9)


def test_week_label_same_and_cross_month():
    assert week_label(date(2026, 11, 9)) == "Mon 9 – Sun 15 Nov"
    assert week_label(date(2026, 11, 30)) == "Mon 30 Nov – Sun 6 Dec"


def test_greeting_by_hour():
    assert [greeting(h) for h in (11, 12, 16, 17)] == [
        "Good morning",
        "Good afternoon",
        "Good afternoon",
        "Good evening",
    ]


def test_names():
    assert first_name("Ali Khan") == "Ali"
    assert first_name("  ") == ""
    assert initials("Ali Khan") == "AK"
    assert initials("ali") == "A"
    assert initials("a b c") == "AB"


def test_hourly_rate():
    assert hourly_rate(Decimal(800)) == 100


def test_wage_and_overtime_hints():
    assert wage_hint(Decimal(800)) == "Hourly rate: ₹100 (daily wage ÷ 8)."
    assert wage_hint(None) == "Hourly rate is the daily wage ÷ 8."
    assert (
        overtime_hint(Decimal(800), Decimal("1.00"))
        == "Hours past 8 in a day are paid at ₹100 × 1 = ₹100 an hour."
    )
    assert "× 1.5 = ₹150 an hour." in overtime_hint(Decimal(800), Decimal("1.50"))
    assert overtime_hint(None, Decimal(1)).endswith("the hourly rate × this number.")


def test_day_row_states():
    today = THU
    done = DayRecord(start=at(9), end=at(19))
    assert day_row(today, done, today) | {} == {
        "date": today,
        "label": "Thu 12",
        "times": "9:00 am – 7:00 pm",
        "state": "done",
        "can_edit": True,
        "edited": False,
    }
    open_record = DayRecord(start=at(9, 2))
    assert day_row(today, open_record, today)["times"] == "9:02 am – working"
    past = day_row(today - timedelta(days=1), open_record, today)
    assert past["times"] == "9:02 am – not ended"
    assert past["state"] == "open"
    missing = day_row(today - timedelta(days=2), None, today)
    assert (missing["times"], missing["state"]) == ("Not recorded", "missing")
    future = day_row(today + timedelta(days=1), None, today)
    assert not future["can_edit"]
    edited = DayRecord(start=at(9), end=at(10), edited_by_owner=True)
    assert day_row(today, edited, today)["edited"]


def test_start_day_saves_to_minute(db):
    record = start_day(make_employee(), at(9, 2, 47))
    record.refresh_from_db()
    assert record.start == at(9, 2)
    assert record.date == THU
    assert not record.edited_by_owner


def test_start_day_twice_same_date_keeps_one(db):
    e = make_employee()
    first = start_day(e, at(9, 2, 47))
    second = start_day(e, at(11, 30))
    assert second.pk == first.pk
    assert e.days.count() == 1
    assert second.start == at(9, 2)


def test_end_day_sets_end_and_noop_without_open_day(db):
    e = make_employee()
    assert end_day(e, at(19, 0, 30)) is None
    start_day(e, at(9, 2))
    record = end_day(e, at(19, 0, 30))
    assert record.end == at(19, 0)
    assert not record.edited_by_owner
    assert end_day(e, at(20)) is None
    assert e.days.get().end == at(19, 0)


def test_end_day_same_minute_as_start(db):
    e = make_employee()
    start_day(e, at(9, 2, 10))
    assert end_day(e, at(9, 2, 50)).end == at(9, 2)


def test_end_day_by_owner_marks_edited(db):
    e = make_employee()
    start_day(e, at(9, 2))
    assert end_day(e, at(18), by_owner=True).edited_by_owner


def test_save_day_creates_and_updates_marked_edited(db):
    e = make_employee()
    record = save_day(e, THU, time(9, 0), time(17, 30))
    assert (record.start, record.end) == (at(9), at(17, 30))
    assert record.edited_by_owner
    again = save_day(e, THU, time(10, 0), None)
    assert again.pk == record.pk
    assert again.end is None
    assert e.days.count() == 1


def test_day_card_states(db):
    assert day_card(None, at(9)) is None
    e = make_employee()
    card = day_card(e, at(9, 2))
    assert card["state"] == "not_started"
    assert card["greeting"] == "Good morning, Ali"
    start_day(e, at(9, 2))
    card = day_card(e, at(15, 20))
    assert card["state"] == "started"
    assert card["so_far"] == timedelta(hours=6, minutes=18)
    assert card["greeting"] == "Good afternoon, Ali"
    end_day(e, at(19))
    card = day_card(e, at(19, 5))
    assert card["state"] == "ended"
    assert card["end"] == at(19)
