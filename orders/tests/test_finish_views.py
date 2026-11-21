from decimal import Decimal

import pytest
from django.test import Client

from accounts.roles import EMPLOYEE, add_to_role
from catalog.models import ProductOption
from orders.models import MaterialLine, Order, Payment
from orders.tests.conftest import make_order
from orders.tests.test_finishing import blouse_order

HX = {"HTTP_HX_REQUEST": "true"}


@pytest.fixture
def option(blouse):
    ProductOption.objects.filter(product=blouse).update(
        asked_when=ProductOption.WHEN_DONE
    )
    return blouse.options.get()


def ready_url(order):
    return f"/orders/{order.pk}/ready/"


def deliver_url(order):
    return f"/orders/{order.pk}/deliver/"


def answers(order, qty="0.8", cost="96", sell="120", **extra):
    item = order.items.first()
    key = f"{item.pk}_{item.product.options.get().pk}"
    return {f"qty_{key}": qty, f"cost_{key}": cost, f"sell_{key}": sell, **extra}


def refreshed(order):
    order.refresh_from_db()
    return order.status


def test_ready_sheet_lists_when_done_questions(owner_client, customer, blouse, option):
    order = blouse_order(customer, blouse)
    response = owner_client.get(ready_url(order), **HX)
    body = response.content.decode()
    assert "Item 1 · Blouse · Lining" in body
    assert "Length (m)" in body and "Skip for now" in body
    assert "has one thing to fill in first." in body
    assert "Send invoice on WhatsApp" in body  # the row shows with questions too


def test_ready_sheet_without_questions_just_confirms(owner_client, customer):
    order = make_order(customer, 1)
    body = owner_client.get(ready_url(order), **HX).content.decode()
    assert "ready for Asha to collect?" in body
    assert ">Mark ready</button>" in body.replace("\n", "").replace("  ", "")


def test_ready_sheet_on_ready_order_refreshes_with_toast(owner_client, customer):
    order = make_order(customer, 1, status="ready")
    response = owner_client.get(ready_url(order), **HX)
    assert "already ready" in response["HX-Trigger"]


def test_ready_save_creates_lines_and_moves(owner_client, customer, blouse, option):
    order = blouse_order(customer, blouse)
    response = owner_client.post(
        ready_url(order), {"action": "save", **answers(order)}, **HX
    )
    assert refreshed(order) == Order.READY
    line = MaterialLine.objects.get()
    assert (line.quantity, line.cost_price, line.selling_price) == (
        Decimal("0.8"),
        Decimal(120),
        Decimal(150),
    )
    assert response["HX-Retarget"] == "#page"
    assert "is ready" in response["HX-Trigger"]


def test_ready_save_invalid_is_422_and_changes_nothing(
    owner_client, customer, blouse, option
):
    order = blouse_order(customer, blouse)
    response = owner_client.post(
        ready_url(order), {"action": "save", **answers(order, qty="0")}, **HX
    )
    assert response.status_code == 422
    assert "Enter a quantity above zero" in response.content.decode()
    assert refreshed(order) == Order.OPEN
    assert MaterialLine.objects.count() == 0


def test_ready_skip_moves_without_lines_and_asks_again_at_deliver(
    owner_client, customer, blouse, option
):
    order = blouse_order(customer, blouse)
    owner_client.post(ready_url(order), {"action": "skip"}, **HX)
    assert refreshed(order) == Order.READY
    assert MaterialLine.objects.count() == 0
    body = owner_client.get(deliver_url(order), **HX).content.decode()
    assert "Item 1 · Blouse · Lining" in body
    assert "Save and mark delivered" in body


def test_ready_twice_shows_order_error(owner_client, customer):
    order = make_order(customer, 1, status="ready")
    response = owner_client.post(ready_url(order), **HX)
    assert (
        "Can" in response["HX-Trigger"]
        and "ready order to ready" in response["HX-Trigger"]
    )
    assert refreshed(order) == Order.READY


def test_ready_order_error_wins_over_invalid_answers(
    owner_client, customer, blouse, option
):
    order = blouse_order(customer, blouse)
    Order.objects.filter(pk=order.pk).update(status=Order.READY)
    response = owner_client.post(
        ready_url(order), {"action": "save", **answers(order, qty="0")}, **HX
    )
    assert response.status_code == 200
    assert "ready order to ready" in response["HX-Trigger"]
    assert refreshed(order) == Order.READY
    assert MaterialLine.objects.count() == 0


def test_ready_without_htmx_redirects(owner_client, customer):
    order = make_order(customer, 1)
    response = owner_client.post(ready_url(order))
    assert response.status_code == 303
    assert refreshed(order) == Order.READY


def test_deliver_with_balance_needs_confirm(owner_client, customer):
    order = make_order(customer, 1, status="ready", price="1000")
    response = owner_client.post(deliver_url(order), **HX)
    assert "Asha still owes ₹1,000. Mark delivered anyway?" in response.content.decode()
    assert refreshed(order) == Order.READY
    response = owner_client.post(deliver_url(order), {"confirmed": "1"}, **HX)
    assert refreshed(order) == Order.DELIVERED
    assert "delivered" in response["HX-Trigger"]


def test_deliver_zero_balance_delivers_directly(owner_client, customer):
    order = make_order(customer, 1, status="ready", price="1000")
    Payment.objects.create(
        order=order, amount=Decimal(1000), date="2026-11-01", method=Payment.CASH
    )
    owner_client.post(deliver_url(order), **HX)
    assert refreshed(order) == Order.DELIVERED


def test_deliver_free_order_delivers_directly(owner_client, customer):
    order = make_order(customer, 1, status="ready", free=True)
    owner_client.post(deliver_url(order), **HX)
    assert refreshed(order) == Order.DELIVERED


def test_deliver_save_then_confirm_rolls_back_answers(
    owner_client, customer, blouse, option
):
    order = blouse_order(customer, blouse, status="ready", price="1000")
    Payment.objects.create(
        order=order, amount=Decimal(1000), date="2026-11-01", method=Payment.CASH
    )
    data = {"action": "save", **answers(order, qty="2", cost="120", sell="180")}
    response = owner_client.post(deliver_url(order), data, **HX)
    assert "Asha still owes ₹180." in response.content.decode()
    assert MaterialLine.objects.count() == 0
    assert refreshed(order) == Order.READY
    owner_client.post(deliver_url(order), {**data, "confirmed": "1"}, **HX)
    assert MaterialLine.objects.count() == 1
    assert refreshed(order) == Order.DELIVERED


def test_deliver_save_invalid_is_422(owner_client, customer, blouse, option):
    order = blouse_order(customer, blouse, status="ready")
    data = {"action": "save", **answers(order, qty="x")}
    assert owner_client.post(deliver_url(order), data, **HX).status_code == 422
    assert refreshed(order) == Order.READY


def test_deliver_get_by_status(owner_client, customer):
    open_order = make_order(customer, 1)
    assert (
        "ready first" in owner_client.get(deliver_url(open_order), **HX)["HX-Trigger"]
    )
    done = make_order(customer, 2, status="delivered")
    assert (
        "already delivered" in owner_client.get(deliver_url(done), **HX)["HX-Trigger"]
    )
    ready = make_order(customer, 3, status="ready")
    assert (
        "Mark #3 delivered?"
        in owner_client.get(deliver_url(ready), **HX).content.decode()
    )


def test_deliver_on_delivered_order_shows_order_error(owner_client, customer):
    order = make_order(customer, 1, status="delivered")
    response = owner_client.post(deliver_url(order), **HX)
    assert "delivered order to delivered" in response["HX-Trigger"]
    assert refreshed(order) == Order.DELIVERED


def test_bar_buttons_by_status(owner_client, customer):
    for number, status in enumerate(("open", "in_progress"), start=1):
        order = make_order(customer, number, status=status)
        assert (
            'id="mark-ready"'
            in owner_client.get(f"/orders/{order.pk}/").content.decode()
        )
    ready = make_order(customer, 3, status="ready")
    body = owner_client.get(f"/orders/{ready.pk}/").content.decode()
    assert 'id="mark-delivered"' in body and "hx-confirm=" in body
    Payment.objects.create(
        order=ready, amount=Decimal(1000), date="2026-11-01", method=Payment.CASH
    )
    body = owner_client.get(f"/orders/{ready.pk}/").content.decode()
    assert 'id="mark-delivered"' in body and "hx-confirm=" not in body
    done = make_order(customer, 4, status="delivered")
    body = owner_client.get(f"/orders/{done.pk}/").content.decode()
    assert "mark-ready" not in body and "mark-delivered" not in body


def test_bar_opens_sheet_when_questions_pending(owner_client, customer, blouse, option):
    order = blouse_order(customer, blouse, status="ready")
    body = owner_client.get(f"/orders/{order.pk}/").content.decode()
    assert f'hx-get="{deliver_url(order)}"' in body


def test_employee_cannot_use_finish_urls(customer, employee_user):
    user, employee = employee_user
    add_to_role(user, EMPLOYEE)
    order = make_order(customer, 1)
    order.assignee = employee
    order.save()
    client = Client()
    client.force_login(user)
    assert "mark-ready" not in client.get(f"/orders/{order.pk}/").content.decode()
    for url in (ready_url(order), deliver_url(order)):
        assert client.get(url, **HX).status_code in (302, 403, 404)
        assert client.post(url, **HX).status_code in (302, 403, 404)
    assert refreshed(order) == Order.OPEN


def send_order(customer, **kwargs):
    return make_order(customer, 1, **kwargs)


def test_ready_sheet_has_unticked_send_checkbox(owner_client, customer):
    body = owner_client.get(ready_url(send_order(customer)), **HX).content.decode()
    assert 'name="send_invoice"' in body
    assert "checked" not in body.split('name="send_invoice"')[1].split(">")[0]
    assert "Asha Rao · 90000 00011 · balance ₹1,000" in body


def test_ready_sheet_send_disabled_without_phone(owner_client, customer):
    customer.phone = ""
    customer.save()
    body = owner_client.get(ready_url(send_order(customer)), **HX).content.decode()
    assert "disabled" in body.split('name="send_invoice"')[1].split(">")[0]
    assert "Add a phone number on S07 first." in body


def test_ready_sheet_free_order_has_no_send_checkbox(owner_client, customer):
    order = send_order(customer, free=True)
    body = owner_client.get(ready_url(order), **HX).content.decode()
    assert "send_invoice" not in body


def test_ready_without_phone_still_marks_ready(owner_client, customer):
    customer.phone = ""
    customer.save()
    order = send_order(customer)
    response = owner_client.post(ready_url(order), {"send_invoice": "1"}, **HX)
    assert "HX-Redirect" not in response
    assert refreshed(order) == Order.READY
    assert order.invoice_last_sent_at is None


def test_ready_ticked_redirects_to_whatsapp(owner_client, customer):
    order = send_order(customer)
    response = owner_client.post(ready_url(order), {"send_invoice": "1"}, **HX)
    assert response["HX-Redirect"].startswith("https://wa.me/919000000011?text=")
    assert refreshed(order) == Order.READY
    assert order.invoice_last_sent_at is not None


def test_ready_ticked_without_htmx_redirects(owner_client, customer):
    order = send_order(customer)
    response = owner_client.post(ready_url(order), {"send_invoice": "1"})
    assert response.status_code == 303
    assert response["Location"].startswith("https://wa.me/919000000011?text=")


def test_ready_unticked_does_not_send(owner_client, customer):
    order = send_order(customer)
    response = owner_client.post(ready_url(order), **HX)
    assert "HX-Redirect" not in response
    assert refreshed(order) == Order.READY
    assert order.invoice_last_sent_at is None


def test_ready_ticked_on_free_order_is_ignored(owner_client, customer):
    order = send_order(customer, free=True)
    response = owner_client.post(ready_url(order), {"send_invoice": "1"}, **HX)
    assert "HX-Redirect" not in response
    assert refreshed(order) == Order.READY


def test_ready_send_ticked_kept_on_422(owner_client, customer, blouse, option):
    order = blouse_order(customer, blouse)
    data = {"action": "save", "send_invoice": "1", **answers(order, qty="0")}
    response = owner_client.post(ready_url(order), data, **HX)
    assert response.status_code == 422
    tick = response.content.decode().split('name="send_invoice"')[1].split(">")[0]
    assert "checked" in tick
    assert refreshed(order) == Order.OPEN
