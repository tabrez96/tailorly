from datetime import date
from decimal import Decimal as D

import pytest
from django.db import IntegrityError, transaction

from catalog.models import Product
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


def test_change_same_product_keeps_measurements(customer, blouse):
    saved = MeasurementSet.objects.create(
        customer=customer, product=blouse, values=[{"name": "Bust", "value": "34"}]
    )
    order = Order.objects.create(customer=customer)
    item = OrderItem.from_product(order, blouse)
    item.measurements = [
        {"name": "Bust", "value": "40"},
        {"name": "Waist", "value": ""},
    ]
    item.save()
    saved.values = [{"name": "Bust", "value": "36"}]
    saved.save()
    item.change(
        blouse, [{"name": "Lining", "answer": "Yes"}], price=D("1500"), notes="Hooks"
    )
    item.refresh_from_db()
    assert item.price == D("1500") and item.notes == "Hooks"
    assert item.options == [{"name": "Lining", "answer": "Yes"}]
    assert item.measurements[0] == {"name": "Bust", "value": "40"}


def test_change_product_recopies(customer, blouse):
    other = Product.objects.create(
        name="Salwar",
        kind=Product.PRIMARY,
        type=Product.CUSTOM,
        usual_price=D("900"),
        measurement_fields=["Hip"],
    )
    MeasurementSet.objects.create(
        customer=customer, product=other, values=[{"name": "Hip", "value": "38"}]
    )
    item = OrderItem.from_product(Order.objects.create(customer=customer), blouse)
    item.change(other, price=D("950"))
    item.refresh_from_db()
    assert (item.product, item.name, item.type) == (other, "Salwar", "custom")
    assert item.usual_price == D("900") and item.price == D("950")
    assert item.measurements == [{"name": "Hip", "value": "38"}]


def test_change_to_ready_made_clears_measurements(customer, blouse, kurta):
    item = OrderItem.from_product(Order.objects.create(customer=customer), blouse)
    assert item.measurements
    item.change(kurta, price=D("799"))
    item.refresh_from_db()
    assert item.type == "ready_made" and item.measurements == []


def test_change_same_product_does_not_overwrite_newer_measurements(customer, blouse):
    item = OrderItem.from_product(Order.objects.create(customer=customer), blouse)
    stale = OrderItem.objects.get(pk=item.pk)
    item.measurements = [{"name": "Bust", "value": "41"}]
    item.save(update_fields=["measurements"])
    stale.change(blouse, price=D("1500"))
    item.refresh_from_db()
    assert item.price == D("1500")
    assert item.measurements == [{"name": "Bust", "value": "41"}]


def test_new_item_goes_after_the_last_one_when_positions_have_gaps(customer, blouse):
    order = make_order(customer, blouse, blouse, blouse, blouse)
    first, second, *_ = order.items.all()
    first.delete()
    second.delete()
    added = OrderItem.from_product(order, blouse)
    assert list(order.items.all())[-1] == added


def test_draft_can_have_no_customer(db):
    assert Order.objects.create().customer is None


def test_placed_order_needs_customer_constraint(db):
    order = Order.objects.create()
    with pytest.raises(IntegrityError), transaction.atomic():
        Order.objects.filter(pk=order.pk).update(status="open", number=1)


def test_place_without_customer_raises(blouse):
    order = Order.objects.create(due_date=TODAY)
    OrderItem.from_product(order, blouse)
    with pytest.raises(OrderError, match="Choose a customer."):
        order.place()


def test_choose_customer_recopies_custom_items(customer, blouse, kurta):
    MeasurementSet.objects.create(
        customer=customer,
        product=blouse,
        values=[{"name": "Bust", "value": "34"}, {"name": "Waist", "value": "28"}],
    )
    order = Order.objects.create()
    custom = OrderItem.from_product(order, blouse)
    ready = OrderItem.from_product(order, kurta)
    assert custom.measurements[0]["value"] == ""
    order.choose_customer(customer)
    custom.refresh_from_db()
    ready.refresh_from_db()
    order.refresh_from_db()
    assert order.customer == customer
    assert custom.measurements == [
        {"name": "Bust", "value": "34"},
        {"name": "Waist", "value": "28"},
    ]
    assert ready.measurements == []


def test_choose_customer_overwrites_item_edits_and_clears_for_new_customer(
    customer, blouse
):
    from customers.models import Customer

    order = Order.objects.create(customer=customer)
    item = OrderItem.from_product(order, blouse)
    item.measurements = [{"name": "Bust", "value": "40"}]
    item.save()
    order.choose_customer(Customer.objects.create(name="Meera Iyer"))
    item.refresh_from_db()
    assert [m["value"] for m in item.measurements] == ["", ""]


def test_choose_customer_on_placed_order_raises(customer, blouse):
    order = make_order(customer, blouse)
    order.place()
    with pytest.raises(OrderError):
        order.choose_customer(customer)
