from decimal import Decimal

import pytest

from catalog.models import Product, ProductOption
from orders.forms import RupeeField
from orders.items import (
    item_summary,
    material_hint,
    price_input,
    price_message,
    product_summary,
    products_for,
    resolve_type,
)
from orders.models import Order, OrderItem

pytestmark = pytest.mark.django_db


def test_price_message_with_and_without_product(blouse):
    assert (
        price_message(blouse)
        == "Enter a price. The usual price for a Blouse is ₹1,200."
    )
    assert price_message(None) == "Enter a price."


def test_price_input_drops_zero_paise():
    assert price_input(Decimal("1800.00")) == "1800"
    assert price_input(Decimal("1800.50")) == "1800.5"


def test_resolve_type_defaults_to_custom():
    assert resolve_type("ready_made") == Product.READY_MADE
    assert resolve_type("nope") == Product.CUSTOM
    assert resolve_type(None) == Product.CUSTOM


def test_material_hint(lining):
    plain = ProductOption(name="Piping")
    assert material_hint(plain) == ""
    option = ProductOption(
        name="Lining", material=lining, asks_quantity=True, asked_when="when_done"
    )
    assert material_hint(option) == "Uses Lining, cotton. Quantity is asked when done."
    option.asked_when = "at_order"
    assert material_hint(option).endswith("Quantity is asked at order.")
    option.asks_quantity = False
    assert material_hint(option) == "Uses Lining, cotton."


def test_product_summary_custom_and_ready_made(blouse, kurta):
    assert product_summary(blouse) == "Custom · 1 option · 2 measurements"
    assert product_summary(kurta) == "Ready-made · usual ₹799"
    bare = Product.objects.create(
        name="Plain", kind=Product.PRIMARY, type=Product.CUSTOM, usual_price=1
    )
    assert product_summary(bare) == "Custom"


def test_item_summary(customer, blouse, kurta):
    order = Order.objects.create(customer=customer)
    item = OrderItem(
        order=order,
        type=Product.CUSTOM,
        options=[
            {"name": "Lining", "answer": "Yes"},
            {"name": "Padding", "answer": "No"},
            {"name": "Sleeve", "answer": "Elbow"},
        ],
        measurements=[
            {"name": "Bust", "value": "34"},
            {"name": "Waist", "value": ""},
        ],
        notes=" Hooks ",
    )
    assert item_summary(item) == "Lining · Elbow · 1 measurement · 1 note"
    item.options, item.measurements, item.notes = (
        [],
        [{"name": "Bust", "value": ""}],
        "",
    )
    assert item_summary(item) == "no measurements"
    item.measurements = [{"name": "A", "value": "1"}, {"name": "B", "value": "2"}]
    assert item_summary(item) == "2 measurements"
    assert item_summary(OrderItem(type=Product.READY_MADE)) == "no measurements"


def test_products_for_filters_active_primary_of_type(blouse, kurta, lining):
    Product.objects.create(
        name="Apron", kind=Product.PRIMARY, type=Product.CUSTOM, usual_price=1
    )
    Product.objects.create(
        name="Old",
        kind=Product.PRIMARY,
        type=Product.CUSTOM,
        usual_price=1,
        active=False,
    )
    names = [p.name for p in products_for(Product.CUSTOM)]
    assert names == ["Apron", "Blouse"]
    assert [p.name for p in products_for(Product.READY_MADE)] == ["Cotton kurta"]


def test_rupee_field_accepts_commas_and_symbol():
    field = RupeeField(max_digits=12, decimal_places=2)
    assert field.clean("1,800") == Decimal("1800")
    assert field.clean("₹1800 ") == Decimal("1800")
