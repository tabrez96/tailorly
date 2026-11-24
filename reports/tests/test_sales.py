from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from catalog.models import Product
from customers.models import Customer
from orders.models import MaterialLine, Order, Payment
from orders.tests.conftest import make_order
from reports import sales
from reports.sales import Line, Sale

D = Decimal
THU = date(2026, 11, 12)


# --- periods ---------------------------------------------------------------


def test_period_this_month():
    p = sales.parse_period({}, THU)
    assert p == sales.Period("month", date(2026, 11, 1), date(2026, 11, 30))


def test_period_last_month_across_year():
    p = sales.parse_period({"period": "last_month"}, date(2027, 1, 15))
    assert (p.first, p.last) == (date(2026, 12, 1), date(2026, 12, 31))


def test_period_this_week_across_year():
    p = sales.parse_period({"period": "week"}, date(2026, 12, 31))
    assert (p.first, p.last) == (date(2026, 12, 28), date(2027, 1, 3))


def test_period_custom():
    params = {"period": "custom", "from": "2026-11-03", "to": "2026-11-09"}
    p = sales.parse_period(params, THU)
    assert (p.key, p.first, p.last) == ("custom", date(2026, 11, 3), date(2026, 11, 9))
    swapped = sales.parse_period(
        {"period": "custom", "from": "2026-11-09", "to": "2026-11-03"}, THU
    )
    assert (swapped.first, swapped.last) == (date(2026, 11, 3), date(2026, 11, 9))
    bad = sales.parse_period({"period": "custom", "from": "x", "to": ""}, THU)
    assert (bad.first, bad.last) == (date(2026, 11, 1), THU)


@pytest.mark.django_db
def test_period_custom_clamps_extreme_dates():
    params = {"period": "custom", "from": "0001-01-01", "to": "9999-12-31"}
    p = sales.parse_period(params, THU)
    assert (p.first, p.last) == (sales.EARLIEST, THU)
    top = sales.parse_period(
        {"period": "custom", "from": "9999-12-31", "to": "9999-12-31"}, THU
    )
    assert (top.first, top.last) == (THU, THU)
    assert sales.load_sales(p.first, p.last) == []
    assert sales.load_sales(top.first, top.last) == []


def test_period_unknown_defaults_to_month():
    assert sales.parse_period({"period": "day"}, THU).key == "month"


def test_range_text():
    d = date
    assert sales.range_text(d(2026, 11, 1), d(2026, 11, 12)) == "1–12 Nov"
    assert sales.range_text(d(2026, 11, 30), d(2026, 12, 6)) == "30 Nov–6 Dec"
    assert sales.range_text(d(2025, 12, 29), d(2026, 1, 4)) == "29 Dec 2025–4 Jan 2026"
    assert sales.range_text(THU, THU) == "12 Nov"


def test_hero_label_this_month_stops_today():
    this = sales.parse_period({}, THU)
    assert sales.hero_label(this, THU) == "Sales, 1–12 Nov"
    last = sales.parse_period({"period": "last_month"}, THU)
    assert sales.hero_label(last, THU) == "Sales, 1–31 Oct"


def test_empty_text():
    assert sales.empty_text(sales.parse_period({}, THU)) == "No sales in November 2026."
    week = sales.parse_period({"period": "week"}, THU)
    assert sales.empty_text(week) == "No sales in 9–15 Nov."


def test_option_labels_and_urls():
    assert [sales.option_label(k, THU) for k in sales.PERIODS] == [
        "November 2026",
        "October 2026",
        "This week",
        "Custom range",
    ]
    custom = sales.Period("custom", date(2026, 11, 3), date(2026, 11, 9))
    assert sales.period_query(custom) == "period=custom&from=2026-11-03&to=2026-11-09"
    assert sales.page_url(custom, "garment").endswith("&group=garment")
    assert "group" not in sales.page_url(custom, "customer")


# --- totals and grouping -----------------------------------------------------


def sale(customer_id, name, total, balance="0", lines=()):
    return Sale(customer_id, name, D(total), D(balance), tuple(lines))


def test_summary_to_collect_ignores_overpaid():
    s = sales.summary(
        [sale(1, "A", 500, 400), sale(2, "B", 300, -100), sale(1, "A", 50)]
    )
    assert s == {"total": D(850), "orders": 3, "customers": 2, "to_collect": D(400)}


def test_summary_empty():
    assert sales.summary([])["total"] == D(0)


def test_by_customer_sorted_with_percent():
    rows = sales.by_customer(
        [
            sale(1, "Zoya", 1000),
            sale(2, "Asha", 500),
            sale(3, "Bela", 500),
            sale(2, "Asha", 0),
        ]
    )
    assert [r["name"] for r in rows] == ["Zoya", "Asha", "Bela"]
    assert [r["percent"] for r in rows] == [100, 50, 50]
    assert rows[0]["orders_text"] == "1 order"
    assert rows[1]["orders_text"] == "2 orders"


def test_same_name_customers_stay_separate():
    rows = sales.by_customer([sale(1, "Asha", 100), sale(2, "Asha", 100)])
    assert len(rows) == 2


def test_zero_top_gives_zero_bars():
    rows = sales.by_customer([sale(1, "A", 0)])
    assert rows[0]["percent"] == 0


def test_by_garment_counts_and_totals():
    rows = sales.by_garment(
        [
            sale(1, "A", 0, lines=[Line("Kurta", D(800)), Line("Blouse", D(300))]),
            sale(2, "B", 0, lines=[Line("Kurta", D(900))]),
        ]
    )
    assert rows[0] | {} == {
        "name": "Kurta",
        "count": 2,
        "total": D(1700),
        "count_text": "2 pieces",
        "percent": 100,
    }
    assert rows[1]["count_text"] == "1 piece"
    assert rows[1]["percent"] == 18


# --- loader (db) -------------------------------------------------------------


def aware(y, m, d, hour=12, minute=0):
    return timezone.make_aware(datetime(y, m, d, hour, minute))


def placed(customer, number, price="1000", when=None, **kw):
    order = make_order(customer, number, price=price, **kw)
    Order.objects.filter(pk=order.pk).update(created_at=when or aware(2026, 11, 5))
    order.refresh_from_db()
    return order


@pytest.fixture
def asha(db):
    return Customer.objects.create(name="Asha Rao", phone="9000000011")


def nov():
    return sales.load_sales(date(2026, 11, 1), date(2026, 11, 30))


def test_customer_total_equals_invoice_totals(asha):
    a = placed(asha, 1, "1000")
    b = placed(asha, 2, "500")
    MaterialLine.objects.create(
        item=a.items.first(),
        name="Lining",
        unit=Product.METRE if hasattr(Product, "METRE") else Product.UNITS[0][0],
        quantity=D("2"),
        selling_price=D("60"),
        on_bill=True,
    )
    Payment.objects.create(
        order=a, amount=D("300"), date=date(2026, 11, 6), method="cash"
    )
    rows = sales.by_customer(nov())
    assert len(rows) == 1
    assert rows[0]["total"] == a.invoice().total + b.invoice().total == D("1620")
    assert sales.summary(nov())["to_collect"] == D("1320")


def test_free_and_draft_add_nothing(asha):
    placed(asha, 1, "1000")
    before = sales.summary(nov())
    other = Customer.objects.create(name="New One", phone="9000000022")
    placed(asha, 2, "700", free=True)
    placed(other, 3, "700", free=True)
    placed(other, 4, "700", status="draft")
    assert sales.summary(nov()) == before
    assert before["orders"] == 1


def test_local_date_boundary(asha):
    placed(asha, 1, when=datetime(2026, 10, 31, 18, 30, tzinfo=UTC))
    placed(asha, 2, when=aware(2026, 11, 30, 23, 59))
    assert len(nov()) == 2
    assert sales.load_sales(date(2026, 10, 1), date(2026, 10, 31)) == []
    assert sales.load_sales(date(2026, 12, 1), date(2026, 12, 31)) == []


def test_garment_line_includes_on_bill_material(asha):
    order = placed(asha, 1, "1000")
    item = order.items.first()
    for on_bill, price in ((True, "50"), (False, "999")):
        MaterialLine.objects.create(
            item=item,
            name="Thread",
            unit=Product.UNITS[0][0],
            quantity=D("1"),
            selling_price=D(price),
            on_bill=on_bill,
        )
    rows = sales.by_garment(nov())
    assert rows[0]["name"] == "Blouse"
    assert rows[0]["total"] == D("1050")
