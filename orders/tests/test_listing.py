from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from customers.models import Customer
from orders.listing import (
    ListFilter,
    customer_totals,
    filter_url,
    is_late,
    items_summary,
    order_row,
    ordering,
    parse_filter,
    rows_queryset,
    search_filter,
    show_filter,
)
from orders.models import MaterialLine, Order, Payment
from orders.tests.conftest import make_order


def test_parse_filter_defaults_to_open():
    assert parse_filter({}) == ListFilter("open", "")
    assert parse_filter({"show": "x"}) == ListFilter("open", "")
    assert parse_filter({"show": "late"}).show == "late"


def test_parse_filter_trims_and_caps_q():
    assert parse_filter({"q": "  asha "}).q == "asha"
    assert len(parse_filter({"q": "a" * 200}).q) == 80


def test_filter_url_omits_defaults():
    assert filter_url("/orders/", ListFilter()) == "/orders/"
    assert (
        filter_url("/orders/", ListFilter("late", "asha"))
        == "/orders/?show=late&q=asha"
    )
    assert filter_url("/orders/", ListFilter("open", "x")) == "/orders/?q=x"


def test_items_summary_groups_names():
    assert items_summary(["Kurta", "Kurta", "Blouse"]) == "Kurta ×2, Blouse"
    assert items_summary(["Kurta"]) == "Kurta"


TODAY = date(2026, 11, 20)


@pytest.mark.parametrize(
    ("status", "due", "late"),
    [
        ("open", TODAY - timedelta(days=1), True),
        ("in_progress", TODAY - timedelta(days=1), True),
        ("open", TODAY, False),
        ("open", None, False),
        ("ready", TODAY - timedelta(days=1), False),
        ("delivered", TODAY - timedelta(days=1), False),
    ],
)
def test_is_late(status, due, late):
    order = Order(status=status, due_date=due)
    assert is_late(order, TODAY) is late


def test_ordering_by_show():
    for show in ("open", "ready", "late"):
        assert len(ordering(show)) == 2
    for show in ("delivered", "free", "all"):
        assert ordering(show) == ["-number"]


@pytest.fixture
def asha(db):
    return Customer.objects.create(name="Asha Rao", phone="9845022110")


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("show", "numbers"),
    [
        ("open", {2, 3, 6}),
        ("ready", {4}),
        ("delivered", {5}),
        ("free", {6}),
        ("late", {2}),
        ("all", {2, 3, 4, 5, 6}),
    ],
)
def test_each_show_filter_returns_only_matching(asha, show, numbers):
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    make_order(asha, 1, status="draft")
    make_order(asha, 2, status="open", due=yesterday)
    make_order(asha, 3, status="in_progress", due=today)
    make_order(asha, 4, status="ready", due=yesterday)
    make_order(asha, 5, status="delivered")
    make_order(asha, 6, status="open", free=True)
    qs = Order.objects.exclude(status="draft").filter(show_filter(show, today))
    assert set(qs.values_list("number", flat=True)) == numbers


@pytest.mark.django_db
def test_search_by_name_phone_and_number(asha):
    other = Customer.objects.create(name="Meera Iyer", phone="9900177345")
    make_order(asha, 12)
    make_order(other, 13)

    def found(q):
        return set(
            Order.objects.filter(search_filter(q)).values_list("number", flat=True)
        )

    assert found("asha") == {12}
    assert found("98450 22110") == {12}
    assert found("+91 9900177345") == {13}
    assert found("#12") == {12}
    assert found("ORD-12") == {12}
    assert found("12") == {12}
    assert found("zzz") == set()


@pytest.mark.django_db
def test_order_row_balance_paid_free(asha, lining):
    today = timezone.localdate()
    due = make_order(asha, 1, due=today, price="1200")
    paid = make_order(asha, 2, price="500")
    Payment.objects.create(order=paid, amount=Decimal("500"), date=today, method="cash")
    make_order(asha, 3, free=True)
    billed = make_order(asha, 4, price="1000")
    MaterialLine.objects.create(
        item=billed.items.get(),
        product=lining,
        name="Lining",
        quantity=Decimal("2"),
        unit="m",
        cost_price=Decimal("60"),
        selling_price=Decimal("90"),
        on_bill=True,
    )
    rows = {
        r["order"].number: r
        for r in (order_row(o, today) for o in rows_queryset(Order.objects.all()))
    }
    assert rows[1]["balance"] == Decimal("1200") and rows[1]["due"] == "Due today"
    assert rows[1]["late"] is False and rows[1]["items"] == "Blouse"
    assert rows[2]["balance"] == 0
    assert rows[3]["free"] is True and rows[3]["balance"] is None
    assert rows[4]["balance"] == Decimal("1180")
    assert due.number == 1


def row(total, balance):
    return {"total": total, "balance": balance}


def test_customer_totals_skip_free_and_overpaid():
    rows = [
        row(Decimal(1000), Decimal(400)),
        row(Decimal(500), Decimal(-100)),
        row(None, None),
    ]
    assert customer_totals(rows) == (Decimal(1500), Decimal(400))
    assert customer_totals([]) == (0, 0)
