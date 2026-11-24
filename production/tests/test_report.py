import re
from datetime import date, datetime, timedelta

import pytest
from django.contrib.auth.models import Group, User
from django.test import Client
from django.utils import timezone

from core.formats import format_day
from orders.models import Order, OrderItem
from production import report
from production.models import TimeSession
from production.tests.conftest import PARTIAL
from staff.models import DayRecord, Employee

THU = date(2026, 11, 12)


def aware(day, hour=10, minute=0):
    return timezone.make_aware(datetime(day.year, day.month, day.day, hour, minute))


# --- pure helpers ---------------------------------------------------------


def test_parse_period_defaults_and_future():
    assert report.parse_period({}, THU) == ("week", THU)
    assert report.parse_period({"period": "bogus", "date": "nope"}, THU) == (
        "week",
        THU,
    )
    assert report.parse_period({"period": "day", "date": "2026-11-03"}, THU) == (
        "day",
        date(2026, 11, 3),
    )
    assert report.parse_period({"date": "2027-01-01"}, THU) == ("week", THU)


def test_period_range_and_step():
    assert report.period_range("day", THU) == (THU, THU)
    assert report.period_range("week", THU) == (date(2026, 11, 9), date(2026, 11, 15))
    assert report.period_range("month", THU) == (date(2026, 11, 1), date(2026, 11, 30))
    assert report.step("day", THU, -1) == date(2026, 11, 11)
    assert report.step("week", THU, -1) == date(2026, 11, 2)
    assert report.step("week", THU, 1) == date(2026, 11, 16)
    assert report.step("month", THU, -1) == date(2026, 10, 1)
    assert report.step("month", date(2026, 12, 5), 1) == date(2027, 1, 1)
    assert report.step("month", date(2026, 1, 5), -1) == date(2025, 12, 1)


def test_period_label():
    en = "\N{EN DASH}"
    assert report.period_label("day", THU, THU, THU) == "Thu 12 Nov"
    first, last = report.period_range("week", THU)
    assert report.period_label("week", first, last, THU) == f"This week · 9{en}15 Nov"
    first, last = report.period_range("week", date(2026, 11, 30))
    assert report.period_label("week", first, last, THU) == f"30 Nov{en}6 Dec"
    first, last = report.period_range("month", THU)
    assert report.period_label("month", first, last, THU) == "This month · Nov 2026"
    assert report.period_label("month", first, last, date(2026, 12, 1)) == "Nov 2026"


def test_bars_week_and_month():
    first, last = report.period_range("week", THU)
    days = [date(2026, 11, 9)] * 2 + [date(2026, 11, 10)]
    week = report.bars("week", first, last, days, THU)
    assert [b["label"] for b in week][:3] == ["Mon", "Tue", "Wed"]
    assert [b["count"] for b in week] == [2, 1, 0, 0, 0, 0, 0]
    assert [b["percent"] for b in week][:2] == [100, 50]
    assert [b["future"] for b in week] == [False] * 4 + [True] * 3
    first, last = report.period_range("month", THU)
    month = report.bars("month", first, last, [date(2026, 11, 1)], THU)
    en = "\N{EN DASH}"
    assert [b["label"] for b in month] == [
        "1",
        f"2{en}8",
        f"9{en}15",
        f"16{en}22",
        f"23{en}29",
        "30",
    ]
    assert month[0]["count"] == 1 and month[0]["percent"] == 100
    assert month[-1]["future"] is True
    assert (
        report.bars("week", *report.period_range("week", THU), [], THU)[0]["percent"]
        == 0
    )


def test_week_caption():
    monday = date(2026, 11, 9)
    assert (
        report.week_caption(monday, THU)
        == "Mon to Thu so far. Fri to Sun still to come."
    )
    assert (
        report.week_caption(monday, monday) == "Mon so far. Tue to Sun still to come."
    )
    assert report.week_caption(monday, date(2026, 11, 14)) == (
        "Mon to Sat so far. Sun still to come."
    )
    assert report.week_caption(date(2026, 11, 2), THU) == ""
    assert report.week_caption(monday, date(2026, 11, 15)) == ""


def test_on_time_rule():
    due = date(2026, 11, 10)
    assert report.on_time([(due, due)]) == (1, 1)
    assert report.on_time([(due + timedelta(days=1), due)]) == (0, 1)
    assert report.on_time([(due, due), (date(2026, 11, 11), due)]) == (1, 2)
    assert report.on_time([]) == (0, 0)


def row(name, took, estimate):
    return {"name": name, "took": took, "estimate": estimate, "url": "/x/"}


def test_estimate_summary():
    rows = [row("Kurta", 185, 165), row("Blouse", 120, 150), row("Salwar", 30, None)]
    summary = report.estimate_summary(rows)
    assert summary["estimated_text"] == "5h 15m"
    assert summary["took_text"] == "5h 5m"
    assert summary["longer"] == 1 and summary["with_estimate"] == 2
    assert [r["name"] for r in summary["furthest"]] == ["Blouse", "Kurta"]
    assert summary["furthest"][0]["diff_text"] == "\N{MINUS SIGN}30m"
    assert summary["furthest"][1]["diff_text"] == "+20m"
    assert summary["furthest"][1]["diff_tone"] == "warn"
    assert summary["has_more"] is False
    assert report.estimate_summary([row("Salwar", 30, None)]) is None
    longer = report.estimate_summary([row("A", 1760 + 50, 1760), row("B", 0, 0)])
    assert longer["line"].startswith("50m over (+3%) · 1 of 2 took longer")
    even = report.estimate_summary([row("A", 60, 60)])
    assert even["furthest"][0]["diff_text"] == "on time"
    many = report.estimate_summary([row(str(n), 10 + n, 10) for n in range(5)])
    assert many["has_more"] is True


def test_by_garment_averages():
    rows = [row("Kurta", 180, 165), row("Kurta", 120, None), row("Blouse", 60, 45)]
    garments = report.by_garment(rows)
    assert [g["name"] for g in garments] == ["Kurta", "Blouse"]
    assert garments[0] == {
        "name": "Kurta",
        "count": 2,
        "avg_took_text": "2h 30m",
        "avg_estimate_text": "2h 45m",
    }
    assert report.by_garment([row("Salwar", 5, None)])[0]["avg_estimate_text"] == "—"


def test_day_line():
    start, end = aware(THU, 9, 2), aware(THU, 18, 10)
    assert report.day_line("Ali", start, end, 495, 68) == (
        "Ali: 9:02 am to 6:10 pm · 8h 15m on garments · 1h 8m overtime"
    )
    assert report.day_line("Ali", start, end, 495, 0) == (
        "Ali: 9:02 am to 6:10 pm · 8h 15m on garments"
    )
    assert report.day_line("Ali", start, None, 495, 0) == (
        "Ali: 9:02 am, still in · 8h 15m on garments"
    )


# --- database -------------------------------------------------------------

db = pytest.mark.django_db


@pytest.fixture
def owner():
    user = User.objects.create_user("owner", password="x")
    user.groups.add(Group.objects.get_or_create(name="owner")[0])
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def finish(make_item):
    def _finish(ali, minutes=60, estimate=45, at=None, **kwargs):
        item = make_item(ali, estimate=estimate, status="open", **kwargs)
        at = at or timezone.now()
        OrderItem.objects.filter(pk=item.pk).update(status="finished", finished_at=at)
        TimeSession.objects.create(
            employee=ali,
            item=item,
            started_at=at - timedelta(minutes=minutes),
            ended_at=at,
        )
        item.refresh_from_db()
        return item

    return _finish


def context(**params):
    return report.report_context(params, timezone.now())


@db
def test_counts_on_finish_day(ali, finish):
    now = timezone.now()
    item = finish(ali, 60, at=now)
    TimeSession.objects.filter(item=item).update(
        started_at=now - timedelta(days=9), ended_at=now - timedelta(days=9, hours=-1)
    )
    assert context(period="day")["count"] == 1
    yesterday = (timezone.localdate() - timedelta(days=9)).isoformat()
    assert context(period="day", date=yesterday)["count"] == 0
    assert context()["count"] == 1


@db
def test_ready_made_and_rework_left_out(ali, finish, make_item, make_rework):
    ready = finish(ali, 30)
    OrderItem.objects.filter(pk=ready.pk).update(type="ready_made")
    garment = make_item(ali, status="open")
    OrderItem.objects.filter(pk=garment.pk).update(
        status="finished", finished_at=timezone.now()
    )
    rework = make_rework(garment, ali)
    TimeSession.objects.create(
        employee=ali,
        rework=rework,
        started_at=timezone.now() - timedelta(hours=2),
        ended_at=timezone.now() - timedelta(hours=1),
    )
    ctx = context()
    assert ctx["count"] == 1  # only the custom garment
    assert ctx["logged_text"] == "0m"  # no garment sessions counted


@db
def test_late_now_excludes_ready(customer, ali, make_item):
    past = timezone.localdate() - timedelta(days=2)
    make_item(ali, due=past, status="open")
    make_item(ali, due=past, status="ready")
    assert report.late_now(timezone.localdate()) == 1


@db
def test_on_time_from_delivered_at(ali, make_item):
    today = timezone.localdate()
    for due in (today, today - timedelta(days=3)):
        item = make_item(ali, due=due, status="delivered")
        Order.objects.filter(pk=item.order_id).update(delivered_at=timezone.now())
    # delivered a week ago; updated_at stays at now, so only delivered_at puts it there
    earlier = timezone.now() - timedelta(days=8)
    old = make_item(ali, due=today - timedelta(days=9), status="delivered")
    Order.objects.filter(pk=old.order_id).update(delivered_at=earlier)
    ctx = context()
    assert (ctx["on_time"], ctx["of"], ctx["delivered"]) == (1, 2, 2)
    past = context(date=timezone.localtime(earlier).date().isoformat())
    assert (past["on_time"], past["of"], past["delivered"]) == (0, 1, 1)


@db
def test_ready_made_only_sale_is_not_delivered_here(ali, make_item):
    item = make_item(ali, due=None, status="delivered", kind="ready_made")
    Order.objects.filter(pk=item.order_id).update(delivered_at=timezone.now())
    assert context()["of"] == 0


@db
def test_report_view_week(owner, ali, finish):
    finish(ali, 60, due=timezone.localdate() + timedelta(days=2))
    html = owner.get("/production/report/").content.decode()
    assert "Garments finished" in html
    assert "Estimate vs time taken" in html
    assert "By garment" in html and "By employee" in html and "Coming up" in html
    assert 'id="report-production_report"' in html
    assert (
        owner.get("/production/report/?period=month", headers=PARTIAL).status_code
        == 200
    )
    assert "Nothing due in the next 7 days." not in html


@db
def test_report_view_day(owner, ali, finish, started_day):
    started_day(ali, end=aware(timezone.localdate(), 18, 10))
    finish(ali, 60)
    html = owner.get("/production/report/?period=day").content.decode()
    assert "Finished today" in html
    assert "Ali: 9:00 am to 6:10 pm" in html
    past = timezone.localdate() - timedelta(days=1)
    other = owner.get(f"/production/report/?period=day&date={past}").content.decode()
    assert f"Nothing finished on {format_day(past)}" in other


@db
def test_report_view_empty(owner):
    html = owner.get("/production/report/").content.decode()
    assert "Nothing finished this week" in html
    assert "Go to this week" in html
    month = owner.get("/production/report/?period=month").content.decode()
    assert "Nothing finished in " in month


@db
def test_report_links(owner, ali, finish, make_item):
    item = finish(ali, 60, estimate=30)
    make_item(ali, due=timezone.localdate(), name="Petticoat")
    html = owner.get("/production/report/").content.decode()
    assert f"/production/items/{item.pk}/record/" in html
    assert 'href="/orders/?show=soon"' in html
    assert "Petticoat" in html and "Not started" in html


@db
def test_see_all(owner, ali, finish):
    for n in range(5):
        finish(ali, 60 + n, estimate=30)
    html = owner.get("/production/report/").content.decode()
    assert 'id="see-all"' in html and html.count("list__chev") == 3
    full = owner.get("/production/report/?estimates=all").content.decode()
    assert 'id="see-all"' not in full and full.count("list__chev") == 5


@db
def test_back_target(owner):
    html = owner.get("/production/report/").content.decode()
    assert re.search(r'<a class="header__back"\s+href="/production/"', html)
    today = owner.get("/production/report/?from=today").content.decode()
    assert re.search(r'<a class="header__back"\s+href="/"', today)
    assert "from=today" in today  # kept across the report row and the periods


@db
def test_production_tab_week_row(owner, ali, finish):
    finish(ali, 60)
    html = owner.get("/production/").content.decode()
    assert "This week so far" in html
    assert "1 garment finished" in html
    assert "No orders delivered yet · 0 late now" in " ".join(html.split())
    assert 'href="/production/report/"' in html


@db
def test_today_card(owner, ali, finish, make_item):
    finish(ali, 60, estimate=30)
    make_item(ali, due=timezone.localdate() - timedelta(days=1), status="open")
    html = owner.get("/").content.decode()
    assert 'href="/production/report/?from=today"' in html
    assert "1 garment finished · 1 took longer" in " ".join(html.split())
    assert "1 late" in html


@db
def test_report_owner_only(ali):
    assert (
        ali.client.get("/production/report/").status_code
        == ali.client.get("/production/").status_code
        != 200
    )


@db
def test_by_employee_present_time(ali, finish, started_day):
    started_day(ali, end=aware(timezone.localdate(), 18, 0))
    finish(ali, 90, at=aware(timezone.localdate(), 12, 0))
    people = context()["employees"]
    assert people == [
        {"name": "Ali Khan", "line": "1 garment · 1h 30m logged of 9h present"}
    ]


@db
def test_open_day_before_today_counts_no_present_time(ali, started_day):
    started_day(ali, day=timezone.localdate() - timedelta(days=1))
    sessions = []
    records = list(DayRecord.objects.select_related("employee"))
    people = report.by_employee([], sessions, records, timezone.now())
    assert people[0]["line"] == "0 garments · 0m logged"
    assert Employee.objects.count() == 1


@db
def test_still_in_progress(owner, ali, finish, make_item):
    item = finish(ali, 60)
    OrderItem.objects.create(
        order=item.order,
        product=item.product,
        name="Petticoat",
        type="custom",
        price=100,
        usual_price=100,
    )
    html = owner.get("/production/report/?period=day").content.decode()
    assert "Still in progress" in html and "Petticoat" in html


@db
def test_report_ignores_rework_time(ali, finish, make_rework):
    item = finish(ali, 60, estimate=45)
    now = timezone.now()
    before = report._row(OrderItem.objects.get(pk=item.pk), now)
    summary_before = report.estimate_summary([before])
    rework = make_rework(item, ali)
    TimeSession.objects.create(
        employee=ali,
        rework=rework,
        started_at=now - timedelta(hours=3),
        ended_at=now - timedelta(hours=2),
    )
    Rework = type(rework)
    Rework.objects.filter(pk=rework.pk).update(finished_at=now)
    after = report._row(OrderItem.objects.get(pk=item.pk), now)
    assert after["took"] == before["took"] == 60
    assert report.estimate_summary([after]) == summary_before
