from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from customers.models import Customer
from orders.models import Order, Payment
from orders.tests.conftest import make_order
from reports import payments

IST = ZoneInfo("Asia/Kolkata")
TODAY = date(2026, 11, 24)


def pay(order, amount, day=TODAY, method="upi"):
    Payment.objects.create(order=order, amount=Decimal(amount), date=day, method=method)


def delivered(order, day):
    order.status = Order.DELIVERED
    order.delivered_at = datetime(day.year, day.month, day.day, 12, tzinfo=IST)
    order.save()


@pytest.fixture
def customer(db):
    return Customer.objects.create(name="Asha Rao", phone="9000000011")


def test_by_method_sorted_with_percent():
    rows = payments.by_method([("cash", Decimal(100))] + [("upi", Decimal(100))] * 3)
    assert [r["label"] for r in rows] == ["UPI", "Cash"]
    assert [r["percent"] for r in rows] == [100, 33]
    assert rows[0]["count_text"] == "3 payments"
    assert rows[1]["count_text"] == "1 payment"


def test_to_collect_equals_sum_of_open_in_progress_ready_delivered_balances(customer):
    orders = [
        make_order(customer, 1, status="open"),
        make_order(customer, 2, status="in_progress"),
        make_order(customer, 3, status="ready"),
        make_order(customer, 4, status="delivered"),
    ]
    for o in orders:
        pay(o, "300")
    make_order(customer, 5, status="draft")
    make_order(customer, 6, status="open", free=True)
    over = make_order(customer, 7, status="delivered")
    pay(over, "1500")
    ctx = payments.payments_context({}, TODAY)["collect"]
    expected = sum(o.invoice().balance for o in orders)
    assert ctx["total"] == expected == Decimal(2800)
    assert ctx["orders"] == 4
    assert ctx["not_delivered"] == Decimal(2100)
    assert ctx["delivered"] == Decimal(700)


def test_received_by_payment_date(customer):
    order = make_order(customer, 1, status="delivered")
    pay(order, "400", date(2026, 10, 20))
    this = payments.payments_context({}, TODAY)
    last = payments.payments_context({"date": "2026-10-15"}, TODAY)
    assert this["received"] == 0 and this["count"] == 0
    assert last["received"] == Decimal(400)


def test_owing_longest_oldest_first_with_days(customer):
    newer = make_order(customer, 1, status="open")
    delivered(newer, TODAY - timedelta(days=2))
    older = make_order(customer, 2, status="open")
    delivered(older, TODAY - timedelta(days=12))
    rows = payments.payments_context({}, TODAY)["owing"]
    assert [r["number_text"] for r in rows] == ["#2", "#1"]
    assert rows[0]["days_text"] == "12 days since delivery"
    assert rows[0]["url"] == f"/orders/{older.pk}/"


def test_owing_days_text_variants():
    assert payments._days_text(None) == "Delivered"
    assert payments._days_text(0) == "Delivered today"
    assert payments._days_text(1) == "1 day since delivery"


def test_empty_states_text(db):
    ctx = payments.payments_context({}, TODAY)
    assert ctx["methods"] == []
    assert ctx["collect"]["orders"] == 0
    assert ctx["owing"] == []


def test_payments_view_owner_only_and_renders(owner_client, customer):
    order = make_order(customer, 1, status="delivered")
    delivered(order, timezone.localdate() - timedelta(days=3))
    pay(order, "100", timezone.localdate())
    html = owner_client.get("/reports/payments/").content.decode()
    assert 'id="report-payments_report"' in html
    assert "Owing longest" in html
    assert "3 days since delivery" in html


def test_payments_view_empty(owner_client):
    html = owner_client.get("/reports/payments/").content.decode()
    assert "No payments received in this period." in html
    assert "Everyone has paid." in html
    assert "Owing longest" not in html


def test_payments_requires_sign_in(client, db):
    assert client.get("/reports/payments/").status_code == 302


def test_payments_requires_owner(client, db):
    client.force_login(User.objects.create_user("emp", password="x"))
    assert client.get("/reports/payments/").status_code == 302
