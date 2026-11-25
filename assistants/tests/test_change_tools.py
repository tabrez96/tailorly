from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from assistants import change_tools
from assistants.tools import ToolFailure
from catalog.models import Product
from customers.models import Customer, MeasurementSet
from orders.models import Order, OrderItem, Payment


def make(name, type_="custom", **kw):
    return Product.objects.create(
        name=name,
        kind="primary",
        type=type_,
        usual_price=1000,
        measurement_fields=["Chest", "Waist"] if type_ == "custom" else [],
        **kw,
    )


@pytest.fixture
def shop(db):
    customer = Customer.objects.create(name="Asha Rao", phone="9000000011")
    shirt = make("Shirt")
    make("Scarf", "ready_made")
    MeasurementSet.objects.create(
        customer=customer, product=shirt, values=[{"name": "Chest", "value": "38"}]
    )
    return customer


@pytest.fixture
def placed(shop):
    return change_tools.create_order(shop.pk, ["Shirt", "shirt"], "2099-01-01")


def fail(match, fn, *args):
    with pytest.raises(ToolFailure, match=match):
        fn(*args)


def test_create_order_places_numbered_order(shop):
    out = change_tools.create_order(shop.pk, [" Shirt ", "Shirt"], "2099-01-01")
    order = Order.objects.get(number=out["number"])
    assert (order.status, str(order.due_date)) == ("open", "2099-01-01")
    items = list(order.items.all())
    assert len(items) == 2
    assert all(i.measurements[0] == {"name": "Chest", "value": "38"} for i in items)
    assert out["items"][0]["id"] == items[0].id


def test_create_order_ready_made_only_is_delivered(shop):
    out = change_tools.create_order(shop.pk, ["Scarf"], "2099-01-01")
    assert out["status"] == "delivered"


def test_create_order_rejects_unknown_ambiguous_and_inactive_products(shop):
    make("Twin")
    make("twin")
    make("Old", active=False)
    Product.objects.create(
        name="Thread", kind="secondary", type="", unit="m", usual_price=5
    )
    for names, match in [
        (["Coat"], "No product named Coat"),
        (["Twin"], "More than one product is named Twin"),
        (["Old"], "No product named Old"),
        (["Thread"], "No product named Thread"),
        (["Shirt", "Coat"], "No product named Coat"),
        (["", " "], "at least one product"),
        (["Scarf"] * 21, "Up to 20"),
    ]:
        fail(match, change_tools.create_order, shop.pk, names, "2099-01-01")
    assert not Order.objects.exists()


def test_create_order_rejects_bad_or_past_due_date_and_unknown_customer(shop):
    yesterday = str(timezone.localdate() - timedelta(days=1))
    fail("due_date is a date", change_tools.create_order, shop.pk, ["Shirt"], "soon")
    fail("later due date", change_tools.create_order, shop.pk, ["Shirt"], yesterday)
    fail("No customer 999", change_tools.create_order, 999, ["Shirt"], "2099-01-01")
    assert not Order.objects.exists()


def test_record_payment_updates_balance(placed):
    out = change_tools.record_payment(placed["number"], "1,500.50", "upi")
    assert out["total"] == "2000.00"
    assert out["balance"] == "499.50"
    payment = Payment.objects.get()
    assert (payment.method, payment.date) == ("upi", timezone.localdate())
    assert payment.amount == Decimal("1500.50")


def test_record_payment_validates_amount_method_date(placed, shop):
    n = placed["number"]
    for bad in ["0", "-5", "1.234", "abc", "nan", "99999999999"]:
        fail("above zero", change_tools.record_payment, n, bad)
    fail("method is one of", change_tools.record_payment, n, "5", "cheque")
    future = str(timezone.localdate() + timedelta(days=1))
    fail("earlier date", change_tools.record_payment, n, "5", "cash", future)
    fail("date is a date", change_tools.record_payment, n, "5", "cash", "x")
    fail("No order #99", change_tools.record_payment, 99, "5")
    free = Order.objects.create(
        customer=shop, status="open", number=50, paid_by=Order.FREE
    )
    OrderItem.from_product(free, Product.objects.get(name="Scarf"), price=0)
    fail("Free orders", change_tools.record_payment, 50, "5")
    assert not Payment.objects.exists()


def test_update_item_measurements_changes_only_that_item(placed, shop):
    first, second = Order.objects.get(number=placed["number"]).items.order_by("id")
    before = list(MeasurementSet.objects.values_list("values", flat=True))
    out = change_tools.update_item_measurements(
        placed["number"], first.id, {"chest": "38.5", "WAIST": "30"}
    )
    assert out["item"]["measurements"] == [
        {"name": "Chest", "value": "38.5"},
        {"name": "Waist", "value": "30"},
    ]
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.measurements[0]["value"] == "38.5"
    assert second.measurements == [
        {"name": "Chest", "value": "38"},
        {"name": "Waist", "value": ""},
    ]
    assert list(MeasurementSet.objects.values_list("values", flat=True)) == before
    change_tools.update_item_measurements(placed["number"], first.id, {"Chest": ""})
    first.refresh_from_db()
    assert first.measurements[0]["value"] == ""
    assert first.measurements[1]["value"] == "30"


def test_update_item_measurements_rejects_bad_values_and_names(placed, shop):
    n = placed["number"]
    item = Order.objects.get(number=n).items.first()
    other = Order.objects.create(customer=shop, status="open", number=60)
    foreign = OrderItem.from_product(other, Product.objects.get(name="Shirt"))
    scarf = OrderItem.from_product(
        Order.objects.get(number=n), Product.objects.get(name="Scarf")
    )
    update = change_tools.update_item_measurements
    for raw in ["0", "abc", "121", "-3"]:
        fail("Chest:", update, n, item.id, {"Chest": raw})
    fail("no measurement named Hip", update, n, item.id, {"Hip": "30"})
    fail("Chest:", update, n, item.id, {"Waist": "30", "Chest": "abc"})
    fail("Only custom", update, n, scarf.id, {"Chest": "30"})
    fail("No item", update, n, foreign.id, {"Chest": "30"})
    fail("at least one", update, n, item.id, {})
    fail("No order #99", update, 99, item.id, {"Chest": "30"})
    item.refresh_from_db()
    assert item.measurements == [
        {"name": "Chest", "value": "38"},
        {"name": "Waist", "value": ""},
    ]
