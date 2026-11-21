from decimal import Decimal

import pytest
from django.http import QueryDict

from catalog.models import Product, ProductOption
from orders import finishing
from orders.models import MaterialLine, Order, OrderItem, Payment
from orders.tests.conftest import make_order

D = Decimal


@pytest.fixture
def option(blouse):
    ProductOption.objects.filter(product=blouse).update(
        asked_when=ProductOption.WHEN_DONE
    )
    return blouse.options.get()


def blouse_order(customer, blouse, count=1, **kwargs):
    order = make_order(customer, 1, **kwargs)
    item = order.items.get()
    item.product = blouse
    item.options = [{"name": "Lining", "answer": "Yes"}]
    item.save()
    for _ in range(count - 1):
        OrderItem.objects.create(
            order=order,
            product=blouse,
            name="Blouse",
            type=Product.CUSTOM,
            price=D(1000),
            usual_price=D(1000),
            options=[{"name": "Lining", "answer": "Yes"}],
        )
    return order


def test_needs_answer_yes_option_without_line(option):
    assert finishing.needs_answer(option, [{"name": "Lining", "answer": "Yes"}], set())


def test_needs_answer_no_answer_or_at_order_or_no_material(option):
    yes = [{"name": "Lining", "answer": "Yes"}]
    assert not finishing.needs_answer(
        option, [{"name": "Lining", "answer": "No"}], set()
    )
    assert not finishing.needs_answer(option, [], set())
    option.asked_when = ProductOption.AT_ORDER
    assert not finishing.needs_answer(option, yes, set())
    option.asked_when = ProductOption.WHEN_DONE
    option.material = None
    assert not finishing.needs_answer(option, yes, set())


def test_needs_answer_choice_with_answer(option):
    option.answer = ProductOption.CHOICE
    assert finishing.needs_answer(
        option, [{"name": "Lining", "answer": "Elbow"}], set()
    )
    assert not finishing.needs_answer(option, [{"name": "Lining", "answer": ""}], set())


def test_needs_answer_false_when_line_exists(option):
    yes = [{"name": "Lining", "answer": "Yes"}]
    assert not finishing.needs_answer(option, yes, {option.material_id})


def test_pending_questions_numbers_items(customer, blouse, kurta, option):
    order = blouse_order(customer, blouse, count=2)
    OrderItem.objects.create(
        order=order,
        product=kurta,
        name="Kurta",
        type=Product.READY_MADE,
        price=D(799),
        usual_price=D(799),
        options=[{"name": "Lining", "answer": "Yes"}],
    )
    questions = finishing.pending_questions(order)
    assert [q.number for q in questions] == [1, 2]


def test_pending_questions_skips_deleted_product_and_answered(
    customer, blouse, lining, option
):
    order = blouse_order(customer, blouse)
    MaterialLine.from_product(lining, D(1), item=order.items.get())
    assert finishing.pending_questions(order) == []
    OrderItem.objects.filter(order=order).update(product=None)
    assert finishing.pending_questions(order) == []


def test_clean_answer_valid_strips_rupee_and_commas():
    assert finishing.clean_answer("0.8", "₹96", "1,20") == (
        (D("0.8"), D(96), D(120)),
        {},
    )


def test_clean_answer_errors():
    for bad in ("0", "abc", "-1", "1.234", "1000000"):
        _, errors = finishing.clean_answer(bad, "1", "1")
        assert errors == {"qty": finishing.QTY_INVALID}
    for bad in ("abc", "-1", "1.234", "10000000000"):
        _, errors = finishing.clean_answer("1", bad, bad)
        assert errors == {
            "cost": finishing.PRICE_INVALID,
            "sell": finishing.PRICE_INVALID,
        }


def test_clean_answer_rejects_per_unit_price_too_big():
    answer, errors = finishing.clean_answer("0.01", "100000000", "1")
    assert errors == {"cost": finishing.PRICE_INVALID}
    assert answer is None
    answer, errors = finishing.clean_answer("0.01", "99999999.99", "1")
    assert errors == {}


def test_per_unit_and_total_round_half_up():
    assert finishing.per_unit(D(96), D("0.8")) == D(120)
    assert finishing.per_unit(D(100), D(3)) == D("33.33")
    assert finishing.total_for(D(150), D("0.8")) == D(120)


def question(customer, blouse):
    order = blouse_order(customer, blouse)
    return finishing.pending_questions(order)[0]


def test_question_row_defaults_and_posted_errors(customer, blouse, option):
    q = question(customer, blouse)
    row = finishing.question_row(q)
    assert (row["qty"], row["cost"], row["sell"]) == ("1", "60", "90")
    assert row["qty_label"] == "Length (m)"
    assert row["note"].endswith("and to the bill.")
    assert row["title"] == "Item 1 · Blouse · Lining"
    data = QueryDict(f"qty_{q.key}=0&cost_{q.key}=5&sell_{q.key}=6")
    assert finishing.question_row(q, data)["qty_error"] == finishing.QTY_INVALID
    q.option.material.billed_by_default = False
    assert "Counted in its gain" in finishing.question_row(q)["note"]
    assert finishing.unit_label("pc") == "Quantity (pc)"


def test_save_answers_creates_material_lines(customer, blouse, lining, option):
    q = question(customer, blouse)
    data = QueryDict(f"qty_{q.key}=0.8&cost_{q.key}=96&sell_{q.key}=120")
    rows, errors = finishing.save_answers([q], data)
    assert errors == 0
    line = MaterialLine.objects.get()
    assert (line.item, line.product, line.quantity) == (q.item, lining, D("0.8"))
    assert (line.cost_price, line.selling_price) == (D(120), D(150))
    assert line.on_bill == lining.billed_by_default


def test_save_answers_with_errors_writes_nothing(customer, blouse, option):
    q = question(customer, blouse)
    rows, errors = finishing.save_answers([q], QueryDict(f"qty_{q.key}=0"))
    assert errors == 3
    assert MaterialLine.objects.count() == 0


def test_bar_by_status(customer):
    order = make_order(customer, 1)
    assert finishing.bar(order, False) == {"action": "ready"}
    order.status = Order.IN_PROGRESS
    assert finishing.bar(order, False) == {"action": "ready"}
    order.status = Order.READY
    result = finishing.bar(order, True)
    assert result["action"] == "deliver" and result["sheet"] is True
    order.status = Order.DELIVERED
    assert finishing.bar(order, False) == {"action": None}


def test_deliver_confirm(customer):
    order = make_order(customer, 1, status="ready", price="1200")
    assert (
        finishing.deliver_confirm(order)
        == "Asha still owes ₹1,200. Mark delivered anyway?"
    )
    Payment.objects.create(
        order=order, amount=D(1200), date="2026-11-01", method=Payment.CASH
    )
    assert finishing.deliver_confirm(order) == ""
    free = make_order(customer, 2, status="ready", free=True)
    assert finishing.deliver_confirm(free) == ""


def test_things():
    assert finishing.things(1) == "one thing"
    assert finishing.things(2) == "two things"
    assert finishing.things(12) == "12 things"
