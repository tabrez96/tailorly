from datetime import date

from reports import periods
from reports.periods import Nav

TODAY = date(2026, 11, 12)
ALL = ("day", "week", "month")


def test_parse_defaults_to_month_and_clamps_future():
    nav = periods.parse({}, TODAY, ALL)
    assert (nav.key, nav.first, nav.last) == (
        "month",
        date(2026, 11, 1),
        date(2026, 11, 30),
    )
    assert periods.parse({"date": "2030-01-01"}, TODAY, ALL).day == TODAY
    assert periods.parse({"date": "nope"}, TODAY, ALL).day == TODAY
    assert periods.parse({"period": "day"}, TODAY, ("week", "month")).key == "month"


def test_label_month_week_day():
    assert periods.label(periods.parse({}, TODAY, ALL)) == "November 2026"
    week = periods.parse({"period": "week"}, TODAY, ALL)
    assert periods.label(week) == "9–15 Nov"
    assert periods.label(periods.parse({"period": "day"}, TODAY, ALL)) == "Thu 12 Nov"


def test_prev_next_urls(db):
    nav = periods.parse({}, TODAY, ALL)
    ctx = periods.nav_context("payments_report", nav, TODAY, ALL)
    assert ctx["prev_url"] == "/reports/payments/?date=2026-10-01"
    assert ctx["next_url"] == ""
    assert ctx["report_query"] == ""
    past = periods.parse({"period": "week", "date": "2026-11-02"}, TODAY, ALL)
    ctx = periods.nav_context("payments_report", past, TODAY, ALL)
    assert ctx["next_url"] == "/reports/payments/?period=week"
    assert ctx["report_query"] == "period=week&date=2026-11-02"
    assert isinstance(past, Nav)
