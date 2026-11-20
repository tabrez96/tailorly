from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from accounts.roles import EMPLOYEE, add_to_role
from catalog.models import Product
from customers.models import MeasurementSet
from orders.models import Order, OrderItem, Payment
from orders.tests.conftest import make_employee, make_order

PARTIAL = {"HTTP_HX_REQUEST": "true", "HTTP_HX_REQUEST_TYPE": "partial"}


def url(order):
    return f"/orders/{order.pk}/"


def pay_url(order):
    return f"/orders/{order.pk}/payments/new/"


def pay(client, order, **data):
    data = {
        "amount": "300",
        "date": timezone.localdate().isoformat(),
        "method": "cash",
        **data,
    }
    return client.post(pay_url(order), data)


def test_detail_full_page_on_direct_load(owner_client, customer):
    order = make_order(customer, 1)
    body = owner_client.get(url(order)).content.decode()
    assert "<html" in body
    assert f'href="/customers/{customer.pk}/"' in body


def test_detail_partial_for_htmx(owner_client, customer):
    order = make_order(customer, 1)
    body = owner_client.get(url(order), **PARTIAL).content.decode()
    assert "<html" not in body
    assert "Asha Rao" in body


def test_detail_shows_queue_place(owner_client, customer):
    _, ali = make_employee("9000000002", "ali")
    today = timezone.localdate()
    first = make_order(customer, 1, due=today + timedelta(days=1))
    second = make_order(customer, 2, due=today + timedelta(days=3))
    Order.objects.update(assignee=ali, status=Order.IN_PROGRESS)
    assert "1st in ali" in owner_client.get(url(first)).content.decode()
    body = owner_client.get(url(second)).content.decode()
    assert "2nd in ali" in body
    assert "Change" in body


def test_same_due_date_gets_distinct_places(owner_client, customer):
    _, ali = make_employee("9000000002", "ali")
    day = timezone.localdate() + timedelta(days=2)
    first = make_order(customer, 1, due=day)
    second = make_order(customer, 2, due=day)
    Order.objects.update(assignee=ali, status=Order.OPEN)
    assert "1st in ali" in owner_client.get(url(first)).content.decode()
    assert "2nd in ali" in owner_client.get(url(second)).content.decode()


def test_set_saved_after_item_is_not_claimed_as_source(owner_client, customer, blouse):
    order = make_order(customer, 1)
    OrderItem.objects.filter(order=order).update(
        product=blouse, measurements=[{"name": "Bust", "value": "36"}]
    )
    MeasurementSet.objects.create(
        customer=customer, product=blouse, values=[{"name": "Bust", "value": "40"}]
    )
    body = owner_client.get(url(order)).content.decode()
    assert "Copied from" not in body
    assert "Measurements for this item only." in body


def test_ready_order_has_no_queue_place(owner_client, customer):
    _, ali = make_employee("9000000002", "ali")
    order = make_order(customer, 1, status="ready")
    Order.objects.update(assignee=ali)
    body = owner_client.get(url(order)).content.decode()
    assert "in ali" not in body


def test_no_assignee(owner_client, customer):
    order = make_order(customer, 1)
    assert "Not assigned" in owner_client.get(url(order)).content.decode()


def test_ready_made_item_has_no_measurements(owner_client, customer, kurta):
    order = make_order(customer, 1)
    OrderItem.objects.all().delete()
    OrderItem.objects.create(
        order=order,
        name="Cotton kurta",
        type=Product.READY_MADE,
        price=799,
        usual_price=799,
        product=kurta,
    )
    body = owner_client.get(url(order)).content.decode()
    assert "Cotton kurta" in body
    assert "Measurements" not in body
    assert "No measurements yet" not in body


def test_custom_item_without_values_shows_empty_text(owner_client, customer):
    order = make_order(customer, 1)
    body = owner_client.get(url(order)).content.decode()
    assert "No measurements yet for this blouse." in body


def test_custom_item_tiles_and_copied_text(owner_client, customer, blouse):
    MeasurementSet.objects.create(
        customer=customer, product=blouse, values=[{"name": "Bust", "value": "36"}]
    )
    order = make_order(customer, 1)
    OrderItem.objects.filter(order=order).update(
        product=blouse,
        notes="Hooks at the back",
        measurements=[
            {"name": "Bust", "value": "36"},
            {"name": "Waist", "value": "30"},
        ],
    )
    body = owner_client.get(url(order)).content.decode()
    assert "Bust" in body and "36" in body
    assert "Copied from Asha" in body
    assert "Notes" in body and "Hooks at the back" in body


def test_item_without_saved_set_says_item_only(owner_client, customer, blouse):
    order = make_order(customer, 1)
    OrderItem.objects.filter(order=order).update(
        product=blouse, measurements=[{"name": "Bust", "value": "36"}]
    )
    body = owner_client.get(url(order)).content.decode()
    assert "Measurements for this item only." in body


def test_free_order_no_invoice(owner_client, customer):
    order = make_order(customer, 1, free=True)
    body = owner_client.get(url(order)).content.decode()
    assert "Free" in body
    assert "<s " in body
    assert 'id="order-invoice"' not in body
    assert "Record payment" not in body


def test_paid_order_hides_record_payment(owner_client, customer):
    order = make_order(customer, 1)
    order.record_payment(Decimal(1000), date.today(), "cash")
    body = owner_client.get(url(order)).content.decode()
    assert "Paid" in body
    assert 'id="record-payment"' not in body


def test_unpaid_order_shows_record_payment_and_payments(owner_client, customer):
    order = make_order(customer, 1)
    order.record_payment(Decimal(400), date.today(), "upi")
    body = owner_client.get(url(order)).content.decode()
    assert 'id="record-payment"' in body
    assert "UPI" in body
    assert "₹600" in body


def test_no_payments_yet(owner_client, customer):
    order = make_order(customer, 1)
    assert "No payments yet." in owner_client.get(url(order)).content.decode()


def test_employee_sees_no_owner_controls(client, customer):
    user, ali = make_employee("9000000002", "ali")
    add_to_role(user, EMPLOYEE)
    order = make_order(customer, 1)
    Order.objects.update(assignee=ali)
    client.force_login(user)
    body = client.get(url(order)).content.decode()
    assert "Asha Rao" in body
    assert f"/customers/{customer.pk}/" not in body
    assert "Record payment" not in body
    assert ">Change<" not in body
    assert "₹" not in body
    assert 'id="order-invoice"' not in body


def test_payment_sheet_defaults(owner_client, customer):
    order = make_order(customer, 1)
    order.record_payment(Decimal(400), date.today(), "cash")
    body = owner_client.get(pay_url(order)).content.decode()
    assert 'value="600"' in body
    assert f'value="{timezone.localdate().isoformat()}"' in body
    assert "balance ₹600" in body
    assert 'value="cash"' in body and "checked" in body


def test_record_payment_swaps_invoice(owner_client, customer):
    order = make_order(customer, 1)
    response = pay(owner_client, order, amount="300")
    assert response.status_code == 200
    assert response["HX-Retarget"] == "#order-invoice"
    body = response.content.decode()
    assert "₹300" in body and "₹700" in body
    assert order.payments.count() == 1
    response = pay(owner_client, order, amount="700")
    assert "Paid" in response.content.decode()
    assert "record-payment" not in response.content.decode()


def test_record_payment_zero_amount(owner_client, customer):
    order = make_order(customer, 1)
    for amount in ("0", "-5"):
        response = pay(owner_client, order, amount=amount)
        assert response.status_code == 422
        assert "Enter an amount above zero." in response.content.decode()
    assert not Payment.objects.exists()


def test_record_payment_on_free_order(owner_client, customer):
    order = make_order(customer, 1, free=True)
    response = pay(owner_client, order)
    assert response.status_code == 422
    assert "Free orders have no payments." in response.content.decode()
    assert not Payment.objects.exists()
    assert "balance" not in owner_client.get(pay_url(order)).content.decode()


def test_payment_sheet_owner_only(client, customer):
    user = User.objects.create_user("staff", password="x")
    add_to_role(user, EMPLOYEE)
    order = make_order(customer, 1)
    client.force_login(user)
    assert client.get(pay_url(order)).status_code in (302, 403, 404)
    assert pay(client, order).status_code in (302, 403, 404)
    assert not Payment.objects.exists()


def test_payment_sheet_draft_is_404(owner_client, customer):
    draft = make_order(customer, 1, status="draft")
    assert owner_client.get(pay_url(draft)).status_code == 404


@pytest.mark.parametrize("amount", ["", "abc"])
def test_record_payment_bad_amount(owner_client, customer, amount):
    order = make_order(customer, 1)
    assert pay(owner_client, order, amount=amount).status_code == 422
