from datetime import timedelta
from decimal import Decimal as D

import pytest
from django.utils import timezone

from core.money import format_inr
from orders.models import MaterialLine, Order, OrderItem
from orders.tests.conftest import make_employee, make_order
from production.models import TimeSession
from reports.models import ShopSettings
from reports.order_costs import order_costs

HX = {"HTTP_HX_REQUEST": "true"}


@pytest.fixture
def rate(db):
    ShopSettings.objects.create(
        pk=1, running_costs=[{"name": "Rent", "amount": "9500"}]
    )


@pytest.fixture
def order(customer):
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


def url(order):
    return f"/orders/{order.pk}/"


def test_owner_sees_cost_and_gain_matching_module(owner_client, order, rate):
    oc, rate_ = order_costs(order, timezone.now())
    body = owner_client.get(url(order)).content.decode()
    assert rate_ == D(46)
    assert "Cost and gain" in body and "Free order" not in body
    item = oc.items[0]
    assert item.staff == D(400)  # 240 min at 100 an hour
    assert item.running == D(184)
    assert item.cost == D(400) + D(120) + D(184)
    for figure in (item.cost, item.gain, oc.sale, oc.gain, oc.staff, oc.running):
        assert format_inr(figure) in body
    assert f"Gain {format_inr(item.gain)} ({item.gain_pct}%)" in body
    assert "Gain on this order" in body
    assert "Staff ₹400 · Materials ₹120 · Running costs ₹184" in body


def test_estimated_note_until_finished(owner_client, order, rate):
    note = "Estimated: items not finished"
    assert note in owner_client.get(url(order)).content.decode()
    OrderItem.objects.update(status=OrderItem.FINISHED)
    assert note not in owner_client.get(url(order)).content.decode()


def test_free_order_shows_cost_to_shop(owner_client, order, rate):
    Order.objects.update(paid_by=Order.FREE)
    oc, _ = order_costs(Order.objects.get(), timezone.now())
    body = owner_client.get(url(order)).content.decode()
    for text in ("Free order", "Usual price, not charged", "Cost to the shop"):
        assert text in body
    assert format_inr(oc.cost) in body
    assert "Cost and gain" not in body


def test_rate_missing_note(owner_client, order):
    body = owner_client.get(url(order)).content.decode()
    assert "Running costs aren't set, so they count as ₹0." in body
    assert "Set running costs" in body


def test_rate_set_has_no_missing_note(owner_client, order, rate):
    body = owner_client.get(url(order)).content.decode()
    assert "aren't set" not in body


def test_missing_cost_price_note(owner_client, order, rate):
    MaterialLine.objects.update(cost_price=None)
    body = owner_client.get(url(order)).content.decode()
    assert "have no cost price yet" in body


def test_zero_price_item_shows_dash(owner_client, order, rate):
    OrderItem.objects.update(price=0)
    Order.objects.update(paid_by=Order.CUSTOMER)
    assert "(—)" in owner_client.get(url(order)).content.decode()


def test_card_updates_after_material_added(owner_client, order, rate, lining):
    item = order.items.get()
    before, _ = order_costs(order, timezone.now())
    response = owner_client.post(
        f"/orders/{order.pk}/items/{item.pk}/materials/new/?on=order",
        {
            "item": item.pk,
            "material": lining.pk,
            "qty": "1",
            "cost": "300",
            "sell": "350",
            "bought_on": "2026-11-12",
        },
        **HX,
    )
    after, _ = order_costs(order, timezone.now())
    assert after.materials == before.materials + D(300)
    body = response.content.decode()
    assert format_inr(after.materials) in body
    assert format_inr(after.cost) in body


def test_employee_sees_no_prices_costs_or_gain(client, order, rate):
    ali = order.assignee
    client.force_login(ali.user)
    response = client.get(url(order))
    assert response.status_code == 200
    body = response.content.decode()
    for text in (
        "Cost and gain",
        "Free order",
        "Cost to the shop",
        "Gain",
        "1,500",
        "Running costs",
    ):
        assert text not in body
