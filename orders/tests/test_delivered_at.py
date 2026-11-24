from datetime import timedelta

import pytest
from django.utils import timezone

from catalog.models import Product
from orders.listing import SOON, show_filter
from orders.models import Order, OrderItem, Payment

pytestmark = pytest.mark.django_db


def order(customer, number, status, due=None):
    return Order.objects.create(
        customer=customer, number=number, status=status, due_date=due
    )


def test_mark_delivered_sets_delivered_at(customer):
    o = order(customer, 1, Order.READY, timezone.localdate())
    before = timezone.now()
    o.mark_delivered()
    o.refresh_from_db()
    assert o.delivered_at is not None and o.delivered_at >= before


def test_ready_made_sale_sets_delivered_at(customer):
    product = Product.objects.create(
        name="Scarf", kind=Product.PRIMARY, type=Product.READY_MADE, usual_price=300
    )
    draft = Order.objects.create(customer=customer, status=Order.DRAFT)
    OrderItem.objects.create(
        order=draft,
        product=product,
        name="Scarf",
        type=Product.READY_MADE,
        price=300,
        usual_price=300,
    )
    draft.place()
    draft.refresh_from_db()
    assert draft.status == Order.DELIVERED
    assert draft.delivered_at is not None


def test_other_moves_leave_it_empty(customer):
    o = order(customer, 1, Order.OPEN, timezone.localdate())
    o.mark_ready()
    o.refresh_from_db()
    assert o.delivered_at is None


def test_soon_filter(customer):
    today = timezone.localdate()
    keep = [
        order(customer, 1, Order.OPEN, today),
        order(customer, 2, Order.IN_PROGRESS, today + timedelta(days=6)),
    ]
    order(customer, 3, Order.OPEN, today + timedelta(days=7))
    order(customer, 4, Order.OPEN, today - timedelta(days=1))
    order(customer, 5, Order.READY, today)
    found = Order.objects.filter(show_filter(SOON, today))
    assert set(found) == set(keep)


def test_orders_page_soon_chip(owner_client, customer):
    today = timezone.localdate()
    order(customer, 1, Order.OPEN, today + timedelta(days=2))
    order(customer, 2, Order.OPEN, today + timedelta(days=20))
    html = owner_client.get("/orders/?show=soon").content.decode()
    assert "#1" in html and "#2" not in html
    assert 'id="chip-soon"' in html and "Due in 7 days" in html
    plain = owner_client.get("/orders/").content.decode()
    assert "chip-soon" not in plain


def test_owing_filter_matches_load_owing(owner_client, customer):
    from orders.tests.conftest import make_order

    paid = make_order(customer, 1)
    part = make_order(customer, 2)
    free = make_order(customer, 3, free=True)
    delivered = make_order(customer, 4, status="delivered")
    Payment.objects.create(
        order=paid, amount=1000, date=timezone.localdate(), method="cash"
    )
    Payment.objects.create(
        order=part, amount=400, date=timezone.localdate(), method="cash"
    )
    html = owner_client.get("/orders/?show=owing").content.decode()
    assert f'id="order-{part.pk}"' in html
    assert f'id="order-{delivered.pk}"' in html
    assert f'id="order-{paid.pk}"' not in html
    assert f'id="order-{free.pk}"' not in html


def test_owing_chip_shown(owner_client, customer):
    from orders.tests.conftest import make_order

    make_order(customer, 1)
    html = owner_client.get("/orders/?show=owing").content.decode()
    assert 'id="chip-owing"' in html and "Owing" in html
    assert "chip-owing" not in owner_client.get("/orders/").content.decode()
