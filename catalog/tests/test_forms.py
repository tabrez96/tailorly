from decimal import Decimal

import pytest

from catalog.forms import (
    AMOUNT_ERROR,
    MaterialForm,
    ProductForm,
    amount_input,
    parse_amount,
)
from catalog.models import Product


def test_parse_amount_accepts_rupee_and_commas():
    assert parse_amount("₹1,800") == 1800
    assert parse_amount("1800.50") == Decimal("1800.50")
    assert parse_amount(" 120 ") == 120


@pytest.mark.parametrize("text", ["", "-5", "abc", "1.234", "12345678901", "NaN"])
def test_parse_amount_rejects_bad_values(text):
    assert parse_amount(text) is None


def test_amount_input():
    assert amount_input(Decimal("1800.00")) == "1,800"
    assert amount_input(Decimal("1800.00"), rupee=True) == "₹1,800"
    assert amount_input(Decimal("1800.50")) == "1800.50"


def product_data(**extra):
    return {
        "name": "Sherwani",
        "kind": "primary",
        "type": "custom",
        "usual_price": "₹1,800",
    } | extra


def material_data(**extra):
    return {
        "name": "Saree fall",
        "kind": "secondary",
        "unit": "pcs",
        "cost_price": "60",
        "selling_price": "80",
    } | extra


@pytest.mark.django_db
def test_product_form_creates_primary():
    form = ProductForm(product_data())
    assert form.is_valid(), form.errors
    product = form.save()
    assert (product.kind, product.type, product.unit) == ("primary", "custom", "")
    assert product.usual_price == 1800


def test_product_form_missing_name_and_price():
    form = ProductForm(product_data(name="", usual_price=""))
    assert not form.is_valid()
    assert form.errors["name"] == ["Enter a name."]
    assert form.errors["usual_price"] == ["Enter a price."]


def test_product_form_negative_price():
    form = ProductForm(product_data(usual_price="-5"))
    assert not form.is_valid()
    assert form.errors["usual_price"] == [AMOUNT_ERROR]


@pytest.mark.django_db
def test_material_form_saves_all_fields():
    form = MaterialForm(material_data())
    assert form.is_valid(), form.errors
    product = form.save()
    assert (product.kind, product.type, product.unit) == ("secondary", "", "pcs")
    assert (product.cost_price, product.selling_price) == (60, 80)
    assert product.billed_by_default is False


def test_material_form_label_follows_unit():
    form = MaterialForm(material_data(unit="pair"))
    assert ">pair</span>" in str(form["cost_price"].label)
    assert ">m</span>" in str(MaterialForm()["cost_price"].label)


@pytest.mark.django_db
def test_product_with_options_cannot_become_material(demo_catalog):
    blouse = Product.objects.get(name="Blouse")
    form = MaterialForm(material_data(name="Blouse"), instance=blouse)
    assert not form.is_valid()
    assert form.errors["kind"] == ["Remove its options before you make it a material."]


@pytest.mark.django_db
def test_used_material_cannot_become_product(demo_catalog):
    lining = Product.objects.get(name="Lining, cotton cream")
    form = ProductForm(product_data(name=lining.name), instance=lining)
    assert not form.is_valid()
    assert "Options on other products use this material" in form.errors["kind"][0]


@pytest.mark.django_db
def test_wrong_kind_is_rejected():
    assert ProductForm(product_data(kind="secondary")).errors["kind"] == [
        "Choose a kind."
    ]


@pytest.mark.django_db
def test_ready_made_clears_measurement_fields():
    blouse = Product.objects.create(
        name="Blouse", kind="primary", type="custom", measurement_fields=["Bust"]
    )
    form = ProductForm(product_data(name="Blouse", type="ready_made"), instance=blouse)
    assert form.is_valid(), form.errors
    blouse = form.save()
    assert blouse.measurement_fields == []
