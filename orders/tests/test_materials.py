from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from catalog.models import Product, ProductOption
from orders import finishing
from orders.materials import (
    bill_lines,
    cost_total,
    format_qty,
    line_row,
    material_choices,
    options_to_add,
    qty_label,
)
from orders.models import MaterialLine, OrderItem, Rework
from orders.tests.conftest import make_order

D = Decimal


def line(**kwargs):
    base = {
        "pk": 1,
        "name": "Lining",
        "unit": "m",
        "quantity": D("1.50"),
        "cost_price": D("80"),
        "selling_price": D("100"),
        "on_bill": True,
        "bought_on": None,
    }
    return SimpleNamespace(**{**base, **kwargs})


def test_format_qty_drops_trailing_zeros():
    assert format_qty(D("1.50")) == "1.5"
    assert format_qty(D("2.00")) == "2"
    assert format_qty(D("0.25")) == "0.25"
    assert format_qty(D("10")) == "10"


def test_qty_label():
    assert qty_label("m") == "Quantity (m)"
    assert qty_label("pcs") == "Quantity (pcs)"
    assert qty_label("") == "Quantity"


def test_line_row_billed_and_cost_blank():
    row = line_row(line(cost_price=None))
    assert row["bill_label"] == "On bill" and row["on_bill"]
    assert row["cost"] == "No cost yet"
    assert row["sell"] == "₹150"
    assert row["qty"] == "1.5 m"
    assert row["bought"] == "Not bought yet"


def test_line_row_unbilled_with_cost_and_date():
    row = line_row(line(on_bill=False, bought_on=date(2026, 11, 12)))
    assert row["bill_label"] == "In price"
    assert row["cost"] == "₹120"
    assert row["bought"] == "Bought Thu 12 Nov"


def test_cost_total_none_when_unknown():
    assert cost_total(line(cost_price=None)) is None
    assert cost_total(line()) == D("120.00")


def test_material_choices_sub_line():
    product = SimpleNamespace(
        pk=3,
        name="Canvas",
        unit="m",
        cost_price=D("80"),
        selling_price=D("100"),
        billed_by_default=False,
    )
    [choice] = material_choices([product])
    assert choice["sub"] == "Cost ₹80 · sells ₹100 a m"
    assert choice["unitCost"] == "80" and choice["billed"] is False


@pytest.mark.django_db
def test_bill_lines_only_billed_under_their_item(customer, lining):
    order = make_order(customer, 1)
    second = OrderItem.objects.create(
        order=order, name="Skirt", type=Product.CUSTOM, price=D(500), usual_price=D(500)
    )
    first = order.items.first()
    MaterialLine.from_product(lining, D("2"), item=first)
    MaterialLine.from_product(lining, D("1"), item=first, on_bill=False)
    rows = bill_lines(order.items.prefetch_related("materials"))
    assert [r["name"] for r in rows] == ["Blouse", "Skirt"]
    assert rows[0]["number"] == 1 and rows[0]["price"] == D(1000)
    [m] = rows[0]["materials"]
    assert m["label"] == "Lining, cotton · 2 m" and m["amount"] == D("180.00")
    assert rows[1]["materials"] == [] and second.pk


def opt(pk, material_id, when, answer=ProductOption.YES_NO, name="Lining"):
    return SimpleNamespace(
        pk=pk, material_id=material_id, asked_when=when, answer=answer, name=name
    )


def test_options_to_add_at_order_yes_only():
    at = ProductOption.AT_ORDER
    options = [
        opt(1, 10, at, name="A"),
        opt(2, 11, at, name="B"),
        opt(3, 12, ProductOption.WHEN_DONE, name="C"),
        opt(4, 13, at, name="D"),
        opt(5, 10, at, name="E"),
    ]
    answers = [
        {"name": "A", "answer": "Yes"},
        {"name": "B", "answer": "No"},
        {"name": "C", "answer": "Yes"},
        {"name": "D", "answer": "Yes"},
        {"name": "E", "answer": "Yes"},
    ]
    found = options_to_add(options, answers, {13})
    assert [o.pk for o in found] == [1]


def test_clean_answer_cost_optional():
    answer, errors = finishing.clean_answer("1.5", "", "150", cost_optional=True)
    assert errors == {} and answer == (D("1.5"), None, D("150"))
    _, errors = finishing.clean_answer("1.5", "", "150")
    assert "cost" in errors
    _, errors = finishing.clean_answer("1.5", "", "", cost_optional=True)
    assert set(errors) == {"sell"}


@pytest.mark.django_db
def test_from_product_cost_unknown_and_on_bill_override(customer, lining):
    item = make_order(customer, 1).items.first()
    unknown = MaterialLine.from_product(lining, D(1), item=item, cost_unknown=True)
    assert unknown.cost_price is None and unknown.on_bill is True
    off = MaterialLine.from_product(lining, D(1), item=item, on_bill=False)
    assert off.on_bill is False and off.cost_price == D("60")
    rework = Rework.objects.create(item=item, reason=Rework.FIT)
    line_ = MaterialLine.from_product(lining, D(1), rework=rework, on_bill=True)
    assert line_.on_bill is False
