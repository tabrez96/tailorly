from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth.models import User

from customers.models import Customer
from orders.models import Rework
from orders.tests.conftest import make_order
from production.models import TimeSession
from reports import staff_report
from staff import pay
from staff.models import DayRecord, Employee, Payout

IST = ZoneInfo("Asia/Kolkata")
MONDAY = date(2026, 11, 9)
WAGE = Decimal(800)
ONE = Decimal(1)
NOW = datetime(2026, 11, 16, 12, tzinfo=IST)


def at(day, hour, minute=0):
    return datetime(2026, 11, day, hour, minute, tzinfo=IST)


@pytest.fixture
def ali(db):
    return Employee.objects.create(
        name="Ali Khan", phone="9000000001", daily_wage=WAGE, overtime_multiplier=ONE
    )


def seed_week(employee):
    records = {}
    for d in range(9, 15):
        end = at(d, 19) if d == 12 else at(d, 17)
        DayRecord.objects.create(
            employee=employee, date=date(2026, 11, d), start=at(d, 9), end=end
        )
        records[date(2026, 11, d)] = (at(d, 9), end)
    return records


def test_pay_earned_matches_s10_week_pay(owner_client, ali):
    records = seed_week(ali)
    ctx = staff_report.staff_context({"period": "week", "date": "2026-11-09"}, NOW)
    expected = pay.week_pay(MONDAY, records, WAGE, ONE, date(2026, 11, 16)).total
    assert expected == Decimal(5000)
    assert ctx["cards"][0]["earned"] == expected
    s10 = owner_client.get("/settings/staff/?week=2026-11-09").context["week"].total
    assert ctx["cards"][0]["earned"] == s10


def days_off_fixture():
    records = {}
    for i in (2, 3, 4, 5, 6, 7, 9, 10, 11, 12):
        d = date(2026, 11, i)
        records[d] = (at(i, 9), at(i, 19))
    days = staff_report.employee_days(
        date(2026, 11, 1), date(2026, 11, 12), records, WAGE, ONE, date(2026, 11, 12)
    )
    return days, records


def test_card_days_off_present_overtime():
    days, records = days_off_fixture()
    c = staff_report.card(
        "Ali Khan", days, records, WAGE, ONE, 120, date(2026, 11, 12), 5
    )
    assert c["off_text"] == "2 · Sun 1, Sun 8"
    assert c["worked"] == 10
    assert c["present_text"] == "100h"
    assert c["overtime_text"] == "20h"
    assert c["ot_label"] == "Overtime pay 20h × ₹100 × 1"
    assert c["logged_line"] == "2h · 2%"
    assert c["earned"] == 10 * 800 + 2000
    assert len(c["overtime_rows"]) == 5 and c["overtime_more"]
    assert c["overtime_rows"][0]["times"] == "9:00 am to 7:00 pm"
    full = staff_report.card(
        "Ali Khan", days, records, WAGE, ONE, 0, date(2026, 11, 12), None
    )
    assert len(full["overtime_rows"]) == 10 and not full["overtime_more"]


def test_no_share_without_present_time():
    days = staff_report.employee_days(MONDAY, MONDAY, {}, WAGE, ONE, MONDAY)
    c = staff_report.card("Ali Khan", days, {}, WAGE, ONE, 30, MONDAY)
    assert c["logged_line"] == "30m" and c["bar"] == 0
    assert c["off_text"] == "0"


def test_logged_includes_rework_sessions(ali):
    seed_week(ali)
    order = make_order(Customer.objects.create(name="Asha Rao", phone="9000000011"), 1)
    item = order.items.first()
    rework = Rework.objects.create(item=item, reason=Rework.FIT, estimate_minutes=30)
    TimeSession.objects.create(
        employee=ali, item=item, started_at=at(10, 10), ended_at=at(10, 11)
    )
    TimeSession.objects.create(
        employee=ali, rework=rework, started_at=at(11, 10), ended_at=at(11, 10, 30)
    )
    ctx = staff_report.staff_context({"period": "week", "date": "2026-11-09"}, NOW)
    c = ctx["cards"][0]
    assert c["logged_text"] == "1h 30m"
    assert c["logged_line"] == "1h 30m · 3%"


def test_month_spans_weeks_with_one_payout(ali):
    seed_week(ali)
    today = date(2026, 11, 16)
    DayRecord.objects.create(employee=ali, date=today, start=at(16, 9), end=at(16, 17))
    Payout.objects.create(
        employee=ali,
        week_start=MONDAY,
        paid_on=date(2026, 11, 14),
        method="cash",
        amount=Decimal(4975),
        days=6,
        daily_wage=WAGE,
        base_total=Decimal(4800),
        overtime_minutes=120,
        overtime_multiplier=ONE,
        overtime_total=Decimal(200),
        calculated_total=Decimal(5000),
    )
    ctx = staff_report.staff_context({}, NOW)
    assert ctx["headline"]["earned"] == Decimal(5800)
    assert ctx["headline"]["line"] == "Paid ₹4,975 on Sat 14 Nov · ₹800 due Sat 21 Nov"
    Payout.objects.create(
        employee=ali,
        week_start=date(2026, 11, 16),
        paid_on=today,
        method="cash",
        amount=Decimal(800),
        days=1,
        daily_wage=WAGE,
        base_total=Decimal(800),
        overtime_minutes=0,
        overtime_multiplier=ONE,
        overtime_total=Decimal(0),
        calculated_total=Decimal(800),
    )
    line = staff_report.staff_context({}, NOW)["headline"]["line"]
    assert "due" not in line


def test_inactive_employee_with_activity_in_period_is_included(ali):
    ali.active = False
    ali.save()
    seed_week(ali)
    Payout.objects.create(
        employee=ali,
        week_start=MONDAY,
        paid_on=date(2026, 11, 14),
        method="cash",
        amount=Decimal(5000),
        days=6,
        daily_wage=WAGE,
        base_total=Decimal(4800),
        overtime_minutes=120,
        overtime_multiplier=ONE,
        overtime_total=Decimal(200),
        calculated_total=Decimal(5000),
    )
    ctx = staff_report.staff_context({"period": "week", "date": "2026-11-09"}, NOW)
    assert [c["name"] for c in ctx["cards"]] == ["Ali Khan"]
    assert ctx["headline"]["earned"] == Decimal(5000)
    assert ctx["headline"]["line"].startswith("Paid ₹5,000")
    later = staff_report.staff_context({"period": "week", "date": "2026-11-23"}, NOW)
    assert later["cards"] == []


def test_headline_line_empty_when_nothing_paid_or_due():
    assert staff_report.headline([], [], Decimal(0), date(2026, 11, 21))["line"] == ""


def test_no_days_text(ali):
    ctx = staff_report.staff_context({}, NOW)
    assert ctx["cards"][0]["empty_text"] == "No days recorded for Ali in this period."
    assert not ctx["cards"][0]["has_days"]


def test_staff_view_owner_only_and_renders(owner_client, ali):
    seed_week(ali)
    html = owner_client.get(
        "/reports/staff/?period=week&date=2026-11-09"
    ).content.decode()
    assert 'id="report-staff_report"' in html
    assert 'id="period-day"' not in html
    assert "Ali Khan" in html
    assert "Overtime by day" in html


def test_staff_requires_sign_in(client, db):
    assert client.get("/reports/staff/").status_code == 302


def test_staff_requires_owner(client, db):
    client.force_login(User.objects.create_user("emp", password="x"))
    assert client.get("/reports/staff/").status_code == 302


def test_staff_all_days_link(owner_client, ali):
    for d in range(1, 8):
        DayRecord.objects.create(
            employee=ali, date=date(2026, 11, d), start=at(d, 9), end=at(d, 19)
        )
    html = owner_client.get("/reports/staff/?date=2026-11-09").content.decode()
    assert 'id="overtime-all"' in html
    full = owner_client.get("/reports/staff/?days=all").content.decode()
    assert 'id="overtime-all"' not in full


def test_staff_empty_without_employees(owner_client, db):
    html = owner_client.get("/reports/staff/").content.decode()
    assert "No employees yet. Add one in Staff." in html


def test_headline_labels_last_payout_date_when_dates_differ():
    payouts = [
        Payout(amount=Decimal(5000), paid_on=date(2026, 11, 14)),
        Payout(amount=Decimal(5000), paid_on=date(2026, 11, 21)),
    ]
    line = staff_report.headline([], payouts, Decimal(0), date(2026, 11, 28))["line"]
    assert line == "Paid ₹10,000, last on Sat 21 Nov"
    same = staff_report.headline([], payouts[:1], Decimal(0), date(2026, 11, 28))
    assert same["line"] == "Paid ₹5,000 on Sat 14 Nov"
