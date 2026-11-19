from datetime import date
from decimal import Decimal as D

import pytest
from django.db import IntegrityError, transaction

from customers.models import MeasurementSet
from orders.models import MaterialLine, Order, OrderError, OrderItem, Payment, Rework

TODAY = date(2026, 11, 19)


def make_order(customer, *products, due=TODAY, **kwargs):
    order = Order.objects.create(customer=customer, due_date=due, **kwargs)
    for product in products:
        OrderItem.from_product(order, product)
    return order


def test_item_keeps_snapshot_when_product_edited_or_deactivated(customer, blouse):
    saved = MeasurementSet.objects.create(
        customer=customer,
        product=blouse,
        values=[{"name": "Bust", "value": "34"}, {"name": "Waist", "value": "28"}],
    )
    order = Order.objects.create(customer=customer, due_date=TODAY)
    answers = [{"name": "Lining", "answer": "Yes"}]
    item = OrderItem.from_product(order, blouse, answers)
    before = (item.name, item.type, item.price, item.usual_price)

    blouse.name = "Silk blouse"
    blouse.usual_price = D("1500")
    blouse.active = False
    blouse.measurement_fields = ["Hip"]
    blouse.save()
    blouse.options.all().delete()
    saved.values = [{"name": "Bust", "value": "40"}]
    saved.save()

    item.refresh_from_db()
    assert (item.name, item.type, item.price, item.usual_price) == before
    assert item.options == answers
    assert item.measurements == [
        {"name": "Bust", "value": "34"},
        {"name": "Waist", "value": "28"},
    ]


def test_item_copies_saved_measurements_in_product_order(customer, blouse):
    MeasurementSet.objects.create(
        customer=customer,
        product=blouse,
        values=[{"name": "Waist", "value": "28"}, {"name": "Bust", "value": "34"}],
    )
    item = OrderItem.from_product(Order.objects.create(customer=customer), blouse)
    assert [m["name"] for m in item.measurements] == ["Bust", "Waist"]


def test_item_without_saved_set_gets_empty_fields(customer, blouse):
    item = OrderItem.from_product(Order.objects.create(customer=customer), blouse)
    assert item.measurements == [
        {"name": "Bust", "value": ""},
        {"name": "Waist", "value": ""},
    ]


def test_ready_made_item_has_no_measurements(customer, kurta):
    item = OrderItem.from_product(Order.objects.create(customer=customer), kurta)
    assert item.measurements == []
    item.measurements = [{"name": "Bust", "value": "1"}]
    with pytest.raises(IntegrityError), transaction.atomic():
        item.save()


def test_material_line_needs_exactly_one_owner(customer, blouse, lining):
    item = OrderItem.from_product(Order.objects.create(customer=customer), blouse)
    rework = Rework.objects.create(item=item, reason=Rework.FIT)
    with pytest.raises(IntegrityError), transaction.atomic():
        MaterialLine.from_product(lining, 1, item=item, rework=rework)
    with pytest.raises(IntegrityError), transaction.atomic():
        MaterialLine.from_product(lining, 1)


def test_rework_material_never_billed(customer, blouse, lining):
    item = OrderItem.from_product(Order.objects.create(customer=customer), blouse)
    rework = Rework.objects.create(item=item, reason=Rework.FIT)
    with pytest.raises(IntegrityError), transaction.atomic():
        MaterialLine.objects.create(
            rework=rework,
            name="x",
            unit="m",
            quantity=1,
            selling_price=1,
            on_bill=True,
        )
    assert MaterialLine.from_product(lining, 1, rework=rework).on_bill is False


def test_material_line_copies_prices_and_billed_default(customer, blouse, lining):
    item = OrderItem.from_product(Order.objects.create(customer=customer), blouse)
    line = MaterialLine.from_product(lining, D("1.5"), item=item)
    assert (
        line.name,
        line.unit,
        line.cost_price,
        line.selling_price,
        line.on_bill,
    ) == (
        "Lining, cotton",
        "m",
        D("60"),
        D("90"),
        True,
    )
    lining.selling_price = D("500")
    lining.save()
    line.refresh_from_db()
    assert line.selling_price == D("90")


def test_order_invoice_counts_billed_materials_and_payments(customer, blouse, lining):
    order = make_order(customer, blouse)
    item = order.items.get()
    MaterialLine.from_product(lining, D("1.5"), item=item)
    rework = Rework.objects.create(item=item, reason=Rework.FIT)
    MaterialLine.from_product(lining, 2, rework=rework)
    order.place()
    order.record_payment(D("500"), TODAY, Payment.UPI)
    result = order.invoice()
    assert (result.total, result.received, result.balance) == (
        D("1335.00"),
        D("500"),
        D("835.00"),
    )


def test_free_order_invoice_is_none(customer, blouse):
    assert make_order(customer, blouse, paid_by=Order.FREE).invoice() is None


def test_place_numbers_orders_in_sequence(customer, blouse):
    draft = make_order(customer, blouse)
    assert draft.number is None
    first, second = make_order(customer, blouse), make_order(customer, blouse)
    first.place()
    second.place()
    assert (first.number, second.number) == (1, 2)


def test_place_custom_order_opens(customer, blouse):
    order = make_order(customer, blouse)
    order.place()
    assert order.status == Order.OPEN


def test_place_ready_made_sale_is_delivered(customer, kurta):
    order = make_order(customer, kurta, due=None)
    order.place()
    order.refresh_from_db()
    assert order.status == Order.DELIVERED


def test_place_needs_items(customer):
    order = make_order(customer)
    with pytest.raises(OrderError):
        order.place()
    order.refresh_from_db()
    assert (order.status, order.number) == (Order.DRAFT, None)


def test_place_custom_needs_due_date(customer, blouse):
    order = make_order(customer, blouse, due=None)
    with pytest.raises(OrderError, match="due date"):
        order.place()
    order.refresh_from_db()
    assert order.status == Order.DRAFT


def test_place_twice_raises(customer, blouse):
    order = make_order(customer, blouse)
    order.place()
    with pytest.raises(OrderError):
        order.place()


def test_full_status_path(customer, blouse):
    order = make_order(customer, blouse)
    order.place()
    order.start_work()
    order.start_work()
    assert order.status == Order.IN_PROGRESS
    order.mark_ready()
    order.mark_delivered()
    order.refresh_from_db()
    assert order.status == Order.DELIVERED


@pytest.mark.parametrize(
    "status, action",
    [
        (Order.OPEN, "mark_delivered"),
        (Order.DRAFT, "mark_delivered"),
        (Order.DRAFT, "mark_ready"),
        (Order.DELIVERED, "start_work"),
        (Order.READY, "start_work"),
    ],
)
def test_invalid_transitions_raise(customer, blouse, status, action):
    order = make_order(customer, blouse, number=1, status=status)
    with pytest.raises(OrderError):
        getattr(order, action)()
    order.refresh_from_db()
    assert order.status == status


def test_record_payment_refused_on_free_and_draft_orders_and_non_positive_amount(
    customer, blouse
):
    free = make_order(customer, blouse, paid_by=Order.FREE)
    free.place()
    draft = make_order(customer, blouse)
    open_order = make_order(customer, blouse)
    open_order.place()
    for order, amount in [(free, 10), (draft, 10), (open_order, 0), (open_order, -5)]:
        with pytest.raises(OrderError):
            order.record_payment(D(amount), TODAY, Payment.CASH)
    assert Payment.objects.count() == 0


def test_order_str(customer, blouse):
    order = make_order(customer, blouse)
    assert str(order) == "Draft order"
    order.place()
    assert str(order) == "#1"


def test_place_stores_unsaved_due_date(customer, blouse):
    order = make_order(customer, blouse, due=None)
    due = date(2030, 1, 5)
    order.due_date = due
    order.place()
    order.refresh_from_db()
    assert order.due_date == due
