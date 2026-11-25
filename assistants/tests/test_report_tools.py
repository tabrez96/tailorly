import json
from datetime import date, datetime, timedelta
from decimal import Decimal as D
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from assistants import report_tools, tools
from assistants.tools import ToolFailure
from customers.models import Customer
from orders.models import MaterialLine, Payment
from orders.tests.conftest import make_employee, make_order
from production.models import TimeSession
from reports import payments
from reports.models import ShopSettings
from reports.order_costs import cost_card
from staff import pay
from staff.models import DayRecord, Employee, Payout

IST = ZoneInfo("Asia/Kolkata")
TODAY = date(2026, 11, 24)


def switches(**kw):
    ShopSettings.objects.update_or_create(pk=1, defaults=kw)


def paid(order, amount, day=TODAY, method="upi"):
    Payment.objects.create(order=order, amount=D(amount), date=day, method=method)


@pytest.fixture
def customer(db):
    return Customer.objects.create(name="Asha Rao", phone="9000000011")


def keys_of(value):
    if isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from keys_of(v)
    elif isinstance(value, list):
        for v in value:
            yield from keys_of(v)


@pytest.fixture
def owing(customer):
    open_ = make_order(customer, 1, status="open", price="1000")
    paid(open_, "400")
    sent = make_order(customer, 2, status="delivered", price="700")
    sent.delivered_at = datetime(2026, 11, 10, 12, tzinfo=IST)
    sent.save()
    make_order(customer, 3, status="open", free=True)
    return open_, sent


def test_money_to_collect_matches_payments_report(owing):
    got = report_tools.money_to_collect()
    shown = payments.payments_context({}, TODAY)["collect"]
    assert {k: got[k] for k in ("total", "not_delivered", "delivered")} == {
        k: str(shown[k]) for k in ("total", "not_delivered", "delivered")
    }
    assert got["orders"] == shown["orders"] == 2
    assert got["total"] == "1300.00"
    assert [o["number"] for o in got["owing"]] == [2, 1]
    assert got["owing"][0]["delivered"] == "2026-11-10"


def test_money_to_collect_without_orders_scope_has_no_owing_list(owing):
    switches(mcp_orders=False)
    got = report_tools.money_to_collect()
    assert "owing" not in got and got["total"] == "1300.00"


def test_money_to_collect_nothing_owing(db):
    assert report_tools.money_to_collect() == {
        "total": "0.00",
        "not_delivered": "0.00",
        "delivered": "0.00",
        "orders": 0,
        "owing": [],
    }


@pytest.fixture
def received(owing):
    order = owing[0]
    paid(order, "100", date(2026, 11, 2), "cash")
    paid(order, "250", date(2026, 11, 15), "upi")
    paid(order, "50", date(2026, 11, 30), "cash")
    paid(order, "999", date(2026, 12, 1), "cash")  # outside the month
    return order


def test_list_payments_matches_payments_report(received):
    shown = payments.payments_context({"date": "2026-11-10"}, TODAY)
    got = report_tools.list_payments("2026-11-01", "2026-11-30")
    assert got["received"] == str(shown["received"])
    assert got["count"] == shown["count"]
    assert [(m["method"], m["count"], m["total"]) for m in got["by_method"]] == [
        (m["label"], m["count"], str(m["total"])) for m in shown["methods"]
    ]
    assert [p["date"] for p in got["payments"]][0] == "2026-11-30"
    assert got["payments"][0]["order"] == 1 and got["more"] is False


def test_list_payments_bad_ranges_fail(db):
    for args in [
        ("nope", "2026-11-01"),
        ("2026-11-01", None),
        ("2026-11-05", "2026-11-01"),
        ("2025-01-01", "2026-01-02"),
    ]:
        with pytest.raises(ToolFailure):
            report_tools.list_payments(*args)


def test_list_payments_without_orders_scope_has_no_order_fields(received):
    switches(mcp_orders=False)
    rows = report_tools.list_payments("2026-11-01", "2026-11-30")["payments"]
    assert rows and not {"order", "customer"} & set(rows[0])


def test_list_payments_caps_rows(owing, monkeypatch):
    monkeypatch.setattr(report_tools, "MAX_PAYMENT_ROWS", 1)
    paid(owing[0], "10")
    paid(owing[0], "20")
    got = report_tools.list_payments("2026-11-24", "2026-11-24")
    assert (got["count"], len(got["payments"]), got["more"]) == (3, 1, True)


@pytest.fixture
def costed(customer, db):
    ShopSettings.objects.create(
        pk=1, running_costs=[{"name": "Rent", "amount": "9500"}]
    )
    _, ali = make_employee("9000000002", "ali")
    ali.daily_wage = D(800)
    ali.save()
    order = make_order(customer, 1, status="in_progress", price="1500")
    order.assignee = ali
    order.save()
    item = order.items.get()
    item.estimate_minutes = 240
    item.save()
    now = timezone.now()
    TimeSession.objects.create(
        employee=ali,
        item=item,
        started_at=now - timedelta(hours=3),
        ended_at=now - timedelta(hours=1),
    )
    MaterialLine.objects.create(
        item=item,
        name="Lining",
        unit="m",
        quantity=D("2"),
        cost_price=D("60"),
        selling_price=D("90"),
        on_bill=True,
    )
    return order


def test_order_cost_and_gain_matches_cost_card(costed, monkeypatch):
    switches(mcp_staff=True)
    now = timezone.now()
    monkeypatch.setattr(timezone, "now", lambda: now)
    card = cost_card(costed, now)
    oc = card["total"]
    got = report_tools.order_cost_and_gain(1)
    for field in ("price", "sale", "cost", "gain", "staff", "materials", "running"):
        assert got[field] == str(getattr(oc, field))
    assert got["gain_pct"] == oc.gain_pct
    assert got["staff_time_minutes"] == oc.minutes
    assert got["staff_detail"] == card["staff_detail"] != ""
    (item,) = got["items"]
    assert (item["cost"], item["gain"], item["staff"]) == (
        str(card["items"][0]["cost"]),
        str(card["items"][0]["gain"]),
        str(oc.items[0].staff),
    )
    assert got["reworks"] is None and got["rate_missing"] is False


def test_order_cost_and_gain_without_staff_has_no_staff_lines(costed):
    switches(mcp_staff=True)
    full = report_tools.order_cost_and_gain(1)
    assert "staff" in full
    switches(mcp_staff=False)
    got = report_tools.order_cost_and_gain(1)
    assert not {"staff", "staff_time_minutes", "staff_detail"} & set(got)
    assert "staff" not in got["items"][0]
    assert (got["cost"], got["gain"]) == (full["cost"], full["gain"])


def test_order_cost_and_gain_reworks(costed):
    from orders.models import Rework

    Rework.objects.create(item=costed.items.get(), reason="fit")
    switches(mcp_staff=True)
    got = report_tools.order_cost_and_gain(1)
    assert got["reworks"]["count"] == 1 and "staff" in got["reworks"]
    switches(mcp_staff=False)
    assert "staff" not in report_tools.order_cost_and_gain(1)["reworks"]


def test_order_cost_and_gain_unknown_or_draft_fails(customer):
    make_order(customer, 0, status="draft")
    for number in (9, 0):
        with pytest.raises(ToolFailure, match="No order"):
            report_tools.order_cost_and_gain(number)


@pytest.fixture
def week(db):
    ali = Employee.objects.create(
        name="Ali", phone="9000000004", daily_wage=D(800), overtime_multiplier=D("1.5")
    )

    def day(d, hours):
        start = datetime(d.year, d.month, d.day, 9, tzinfo=IST)
        DayRecord.objects.create(
            employee=ali, date=d, start=start, end=start + timedelta(hours=hours)
        )

    day(date(2026, 11, 16), 8)
    day(date(2026, 11, 17), 10)
    Payout.objects.create(
        employee=ali,
        week_start=date(2026, 11, 16),
        paid_on=date(2026, 11, 21),
        method="cash",
        amount=D(1700),
        days=2,
        daily_wage=D(800),
        base_total=D(1600),
        overtime_minutes=120,
        overtime_multiplier=D("1.5"),
        overtime_total=D(150),
        calculated_total=D(1750),
    )
    Employee.objects.create(name="Gone", phone="9000000003", active=False)
    return ali


def test_staff_week_matches_pay(week):
    got = report_tools.staff_week("2026-11-18")  # a Wednesday
    assert got["week_start"] == "2026-11-16" and got["week_end"] == "2026-11-22"
    assert got["pay_day"] == "2026-11-21"
    (row,) = got["employees"]  # the inactive employee with no records is left out
    w = pay.week_pay(
        date(2026, 11, 16),
        {r.date: (r.start, r.end) for r in DayRecord.objects.filter(employee=week)},
        D(800),
        D("1.5"),
        timezone.localdate(),
    )
    assert row["earned"] == got["earned"] == str(w.total)
    assert row["days_worked"] == 2 and row["overtime_minutes"] == w.overtime_minutes > 0
    assert [d["date"] for d in row["days"]] == ["2026-11-16", "2026-11-17"]
    assert row["payout"] == {
        "paid_on": "2026-11-21",
        "method": "Cash",
        "amount": "1700.00",
    }
    assert got["paid_out"] == "1700.00"


def test_staff_week_default_is_this_week_and_empty_week_is_zero(week):
    got = report_tools.staff_week()
    assert (
        got["week_start"]
        == (
            timezone.localdate() - timedelta(days=timezone.localdate().weekday())
        ).isoformat()
    )
    assert got["earned"] == "0.00" and got["employees"][0]["days_worked"] == 0
    with pytest.raises(ToolFailure):
        report_tools.staff_week("soon")


def test_no_result_carries_wages_or_payouts_with_staff_off(costed, week):
    paid(costed, "100")
    switches(mcp_staff=False)  # also the default
    results = [
        tools.get_order(1),
        tools.list_orders(),
        report_tools.money_to_collect(),
        report_tools.list_payments("2026-11-01", "2026-12-31"),
        report_tools.order_cost_and_gain(1),
    ]
    for result in results:
        found = {k for k in keys_of(json.loads(json.dumps(result)))}
        assert not [
            k
            for k in found
            if any(w in k for w in ("wage", "payout", "paid_out", "staff"))
        ]
