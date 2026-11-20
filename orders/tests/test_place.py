import json
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from accounts.roles import EMPLOYEE, add_to_role
from orders.models import Order, OrderError, OrderItem
from orders.tests.conftest import make_employee


def draft_with(customer, *products):
    order = Order.objects.create(customer=customer)
    items = [OrderItem.from_product(order, p) for p in products]
    return order, items


def place(client, order, **data):
    return client.post(
        f"/orders/drafts/{order.pk}/place/", data, headers={"HX-Request": "true"}
    )


def due(days=7):
    return (timezone.localdate() + timedelta(days=days)).isoformat()


def test_place_custom_order_with_advance(owner_client, customer, blouse):
    _, ravi = make_employee("9000000002", "ravi2")
    order, (a, b) = draft_with(customer, blouse, blouse)
    response = place(
        owner_client,
        order,
        paid_by="customer",
        due_date=due(),
        assignee=ravi.pk,
        **{f"estimate_{a.pk}": "2h 30m", f"estimate_{b.pk}": "3h"},
        advance="1000",
        method="upi",
    )
    assert response.status_code == 204
    assert json.loads(response["HX-Location"])["path"] == f"/orders/{order.pk}/"
    order.refresh_from_db()
    assert order.status == Order.OPEN
    assert order.number == 1
    assert order.assignee == ravi
    a.refresh_from_db()
    b.refresh_from_db()
    assert (a.estimate_minutes, b.estimate_minutes) == (150, 180)
    payment = order.payments.get()
    assert (payment.amount, payment.method) == (Decimal("1000"), "upi")
    assert payment.date == timezone.localdate()
    assert order.invoice().balance == Decimal("1400")


def test_place_without_htmx_redirects(owner_client, customer, kurta):
    order, _ = draft_with(customer, kurta)
    response = owner_client.post(
        f"/orders/drafts/{order.pk}/place/", {"paid_by": "customer", "method": "cash"}
    )
    assert response.status_code == 303
    assert response["Location"] == f"/orders/{order.pk}/"


def test_place_ready_made_only_is_delivered(owner_client, customer, kurta):
    order, _ = draft_with(customer, kurta)
    response = place(
        owner_client, order, paid_by="customer", method="cash", advance="799"
    )
    assert response.status_code == 204
    order.refresh_from_db()
    assert order.status == Order.DELIVERED
    assert order.due_date is None
    assert order.assignee is None
    assert order.payments.count() == 1


def test_place_free_order_has_no_payments(owner_client, customer, blouse):
    order, _ = draft_with(customer, blouse)
    place(
        owner_client,
        order,
        paid_by="free",
        due_date=due(),
        advance="500",
        method="cash",
    )
    order.refresh_from_db()
    assert order.status == Order.OPEN
    assert order.payments.count() == 0
    assert order.invoice() is None


def test_place_errors(owner_client):
    order = Order.objects.create()
    response = place(owner_client, order, paid_by="customer", method="cash")
    body = response.content.decode()
    assert response.status_code == 422
    assert "2 things need fixing" in body
    assert "Choose a customer, or add a new one." in body
    assert "Add at least one item." in body
    assert 'role="alert"' in body
    order.refresh_from_db()
    assert order.status == Order.DRAFT


def test_place_due_date_required_for_custom(owner_client, customer, blouse):
    order, _ = draft_with(customer, blouse)
    response = place(owner_client, order, paid_by="customer", method="cash")
    body = response.content.decode()
    assert response.status_code == 422
    assert "Choose a due date." in body
    field = body.split('id="id_due_date"')[0].rsplit("<input", 1)[1]
    assert 'aria-invalid="true"' in field


def test_place_rejects_bad_estimate(owner_client, customer, blouse):
    order, (item,) = draft_with(customer, blouse)
    response = place(
        owner_client,
        order,
        due_date=due(),
        method="cash",
        **{f"estimate_{item.pk}": "2h 75m"},
    )
    assert response.status_code == 422
    assert "Enter a time like 2h 30m." in response.content.decode()


def test_place_rejects_past_due_and_big_advance(owner_client, customer, blouse):
    order, _ = draft_with(customer, blouse)
    response = place(
        owner_client,
        order,
        paid_by="customer",
        due_date=due(-2),
        advance="5000",
        method="cash",
    )
    body = response.content.decode()
    assert response.status_code == 422
    assert "Choose today or a later date." in body
    assert "The advance can&#x27;t be more than the total." in body


def test_place_item_removed_elsewhere(owner_client, customer, blouse, monkeypatch):
    order, _ = draft_with(customer, blouse)

    def gone(self):
        raise OrderError("Add at least one item.")

    monkeypatch.setattr(Order, "place", gone)
    response = place(
        owner_client, order, paid_by="customer", due_date=due(), method="cash"
    )
    assert response.status_code == 422
    order.refresh_from_db()
    assert order.status == Order.DRAFT
    assert order.payments.count() == 0


def test_paid_by_saved(owner_client, customer):
    order = Order.objects.create(customer=customer)
    url = f"/orders/drafts/{order.pk}/paid-by/"
    assert owner_client.post(url, {"paid_by": "free"}).status_code == 204
    order.refresh_from_db()
    assert order.paid_by == Order.FREE
    assert owner_client.post(url, {"paid_by": "nope"}).status_code == 400


def test_draft_defaults_only_active_employee(owner_client, customer, blouse):
    _, ravi = make_employee("9000000002", "ravi2")
    order, _ = draft_with(customer, blouse)
    body = owner_client.get(f"/orders/drafts/{order.pk}/").content.decode()
    assert f'<option value="{ravi.pk}" selected>' in body
    assert "2h" in body
    make_employee("9000000003", "meena")
    body = owner_client.get(f"/orders/drafts/{order.pk}/").content.decode()
    assert '<option value="" selected>Not assigned yet</option>' in body


def test_making_hidden_for_ready_made_only(owner_client, customer, kurta, blouse):
    order, _ = draft_with(customer, kurta)
    page = f"/orders/drafts/{order.pk}/"
    assert "Making it" not in owner_client.get(page).content.decode()
    OrderItem.from_product(order, blouse)
    assert "Making it" in owner_client.get(page).content.decode()


def test_free_draft_shows_usual_price(owner_client, customer, blouse):
    order, _ = draft_with(customer, blouse)
    order.paid_by = Order.FREE
    order.save()
    body = owner_client.get(f"/orders/drafts/{order.pk}/").content.decode()
    assert "free: true" in body
    assert "Usual price" in body


def test_queue_hint(owner_client, customer, blouse):
    _, ravi = make_employee("9000000002", "ravi2")
    earlier = Order.objects.create(
        customer=customer, status=Order.OPEN, number=1, assignee=ravi,
        due_date=timezone.localdate(),
    )  # fmt: skip
    order, _ = draft_with(customer, blouse)
    url = f"/orders/drafts/{order.pk}/queue-hint/"
    body = owner_client.get(
        url, {"assignee": ravi.pk, "due_date": due()}
    ).content.decode()
    assert "Goes 2nd in" in body
    assert earlier.assignee == ravi
    body = owner_client.get(url, {"assignee": "", "due_date": "bad"}).content.decode()
    assert "Not in anyone&#x27;s queue yet" in body


def test_order_detail(owner_client, client, customer, blouse):
    order, _ = draft_with(customer, blouse)
    assert owner_client.get(f"/orders/{order.pk}/").status_code == 404
    place(
        owner_client,
        order,
        paid_by="customer",
        due_date=due(),
        advance="500",
        method="cash",
    )
    body = owner_client.get(f"/orders/{order.pk}/").content.decode()
    assert "Blouse" in body
    assert "₹500" in body
    assert "₹700" in body
    user, _ = make_employee("9000000004", "other")
    add_to_role(user, EMPLOYEE)
    client.force_login(user)
    assert client.get(f"/orders/{order.pk}/").status_code == 404


def test_free_order_ignores_junk_advance(owner_client, customer, kurta):
    order, _ = draft_with(customer, kurta)
    response = place(owner_client, order, paid_by="free", advance="abc")
    assert response.status_code == 204
    order.refresh_from_db()
    assert order.status == Order.DELIVERED
    assert order.payments.count() == 0


def test_second_place_of_same_draft_changes_nothing(
    owner_client, customer, kurta, monkeypatch
):
    from orders import views

    order, _ = draft_with(customer, kurta)
    stale = views._draft_or_404(order.pk)
    data = {"paid_by": "customer", "advance": "100", "method": "cash"}
    assert place(owner_client, order, **data).status_code == 204
    number = Order.objects.get(pk=order.pk).number
    monkeypatch.setattr(views, "_draft_or_404", lambda pk: stale)
    response = place(owner_client, order, **data)
    assert response.status_code == 204
    assert json.loads(response["HX-Location"])["path"] == f"/orders/{order.pk}/"
    order.refresh_from_db()
    assert order.number == number
    assert order.payments.count() == 1


def test_paid_by_conflicts_once_placed(owner_client, customer, kurta, monkeypatch):
    from orders import views

    order, _ = draft_with(customer, kurta)
    stale = views._draft_or_404(order.pk)
    place(owner_client, order, paid_by="customer", advance="100", method="cash")
    monkeypatch.setattr(views, "_draft_or_404", lambda pk: stale)
    response = owner_client.post(
        f"/orders/drafts/{order.pk}/paid-by/", {"paid_by": "free"}
    )
    assert response.status_code == 409
    order.refresh_from_db()
    assert order.paid_by == Order.CUSTOMER
