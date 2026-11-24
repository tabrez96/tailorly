from datetime import date
from decimal import Decimal

from reports import profit
from reports.costing import ReworkTotal
from reports.sales import LAST_MONTH, MONTH, Period

D = Decimal


def fig(
    n,
    customer="Asha",
    cid=1,
    *,
    free=False,
    sale=1000,
    mat=0,
    staff=0,
    run=0,
    logged=None,
):
    return profit.OrderFigures(
        order_id=n,
        number=n,
        customer_id=cid,
        customer=customer,
        created=date(2026, 11, 3),
        free=free,
        sale=D(sale),
        materials=D(mat),
        staff=D(staff),
        logged_staff=D(staff if logged is None else logged),
        running=D(run),
        shop_cost=D(mat) + D(staff) + D(run),
        estimated=False,
    )


def rework_total(count=5, minutes=370, staff=617, materials=119):
    return ReworkTotal(
        count=count,
        logged=minutes,
        minutes=minutes,
        staff=D(staff),
        materials=D(materials),
        cost=D(staff) + D(materials),
        estimated=False,
        cost_missing=False,
    )


def test_shop_profit_subtracts_everything():
    shop = profit.shop_profit(D(42600), D(2640), D(8300), D(9500), D(7200))
    assert shop.profit == D(22160)
    assert shop.unlogged == D(1100)
    assert "₹1,100 of pay wasn't logged" in profit.note(shop)


def test_unlogged_floors_at_zero():
    shop = profit.shop_profit(D(0), D(0), D(500), D(0), D(900))
    assert shop.unlogged == 0
    assert profit.note(shop) == "Staff pay is split by time logged on each order."


def test_free_work_sums_free_orders_only():
    orders = [
        fig(1, free=True, sale=1500, mat=100, staff=200, run=50),
        fig(2, free=True, sale=2600, mat=260, staff=700, run=364),
        fig(3, sale=9000, mat=999),
    ]
    free = profit.free_work(orders)
    assert free["count"] == 2
    assert free["not_charged"] == D(4100)
    assert free["cost"] == D(1674)
    assert free["text"] == "2 orders · usual price ₹4,100 not charged"
    assert profit.free_work([fig(1)]) is None


def test_free_work_none_when_no_free_orders():
    assert profit.free_work([]) is None


def test_reworks_line_text_and_none():
    line = profit.reworks_line(rework_total())
    assert line["text"] == "5 reworks · 370 min"
    assert line["cost"] == D(736)
    assert profit.reworks_line(rework_total(count=0)) is None
    assert profit.reworks_line(rework_total(count=1))["text"].startswith("1 rework ·")


def test_none_text_month_and_custom():
    nov = Period(MONTH, date(2026, 11, 1), date(2026, 11, 30))
    assert profit.none_text(nov) == "None in November 2026"
    last = Period(LAST_MONTH, date(2026, 10, 1), date(2026, 10, 31))
    assert profit.none_text(last) == "None in October 2026"
    custom = Period("custom", date(2026, 11, 1), date(2026, 11, 7))
    assert profit.none_text(custom) == "None in 1–7 Nov"


def test_caption_parts():
    free = {
        "materials": D(360),
        "staff": D(900),
        "running": D(414),
        "estimated": True,
    }
    reworks = profit.reworks_line(rework_total())
    both = profit.caption(free, reworks)
    assert both == (
        "Free work: materials ₹360, staff ₹900, running costs ₹414 (estimated)."
        " Reworks: staff ₹617, materials ₹119, never invoiced."
        " Materials are already inside the totals above;"
        " staff pay counts what was actually paid."
    )
    only = profit.caption(free | {"running": D(0), "estimated": False}, None)
    assert only == (
        "Free work: materials ₹360, staff ₹900."
        " Materials are already inside the totals above;"
        " staff pay counts what was actually paid."
    )
    assert profit.caption(None, None) == ""


def test_order_profit_ignores_running():
    assert fig(1, sale=1000, mat=100, staff=250, run=400).profit == D(650)


def test_by_customer_skips_free_and_sorts():
    orders = [
        fig(1, "Asha", 1, sale=1600, mat=100),
        fig(2, "Asha", 1, sale=1600, staff=200),
        fig(3, "Bina", 2, sale=1000, mat=1500),
        fig(4, "Chitra", 3, sale=700),
        fig(5, "Free", 4, free=True, sale=9000),
    ]
    rows = profit.by_customer(orders)
    assert [r["name"] for r in rows] == ["Asha", "Chitra", "Bina"]
    assert rows[0]["profit"] == D(2900)
    assert rows[0]["orders"] == 2
    assert rows[0]["sub"] == "2 orders · sales ₹3,200"
    assert rows[1]["sub"] == "1 order · sales ₹700"
    assert [r["percent"] for r in rows] == [100, 24, 0]


def test_by_sale_rows():
    orders = [
        fig(1, "Asha", sale=1000, mat=100),
        fig(2, "Bina", 2, sale=900),
        fig(3, "Free", 3, free=True),
    ]
    rows = profit.by_sale(orders)
    assert [r["name"] for r in rows] == ["#2 Bina", "#1 Asha"]
    assert rows[0]["sub"] == "sales ₹900 · 3 Nov"
    assert rows[0]["order_id"] == 2
    assert profit.by_sale([]) == []


def test_order_profit_uses_logged_staff_not_estimate():
    # Unfinished, nothing logged: the estimate is in staff, not in profit.
    assert fig(1, sale=1000, staff=100, logged=0).profit == D(1000)
