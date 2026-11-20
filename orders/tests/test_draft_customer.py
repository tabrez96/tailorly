import pytest

from customers.models import Customer, MeasurementSet
from orders.models import Order, OrderItem
from orders.tests.conftest import make_employee

pytestmark = pytest.mark.django_db


@pytest.fixture
def empty_draft():
    return Order.objects.create()


@pytest.fixture
def blank_item(empty_draft, blouse):
    return OrderItem.from_product(empty_draft, blouse)


def html(response):
    return response.content.decode()


def test_orders_new_creates_draft_without_customer(owner_client):
    response = owner_client.get("/orders/new/", HTTP_HX_REQUEST="true")
    order = Order.objects.get()
    assert response.status_code == 204
    assert f"/orders/drafts/{order.pk}/" in response["HX-Location"]
    assert order.customer is None and order.status == Order.DRAFT
    plain = owner_client.get("/orders/new/")
    assert plain.status_code == 303
    assert plain["Location"] == f"/orders/drafts/{Order.objects.latest('pk').pk}/"


def test_orders_new_employee_redirected(client):
    user, _ = make_employee("9000000001", "ravi")
    client.force_login(user)
    assert client.get("/orders/new/").status_code == 302
    assert not Order.objects.exists()


def test_draft_without_customer_shows_search(owner_client, empty_draft):
    body = html(owner_client.get(f"/orders/drafts/{empty_draft.pk}/"))
    assert 'id="draft-customer-q"' in body
    assert "+ New customer" in body and "Customer" in body and "Items" in body
    assert 'href="/"' in body


def test_draft_with_customer_shows_card(owner_client, customer, blouse):
    placed = Order.objects.create(customer=customer, due_date="2026-12-01")
    OrderItem.from_product(placed, blouse)
    placed.place()
    draft = Order.objects.create(customer=customer)
    body = html(owner_client.get(f"/orders/drafts/{draft.pk}/"))
    assert "Asha Rao" in body and "90000 00011" in body
    assert "1 order" in body and "1 orders" not in body
    assert "Change" in body


def test_search_by_name_and_phone(owner_client, empty_draft, customer):
    base = f"/orders/drafts/{empty_draft.pk}/customer/search/"
    for q in ("asha", "90000000"):
        body = html(owner_client.get(base, {"q": q}))
        assert f'id="choose-{customer.pk}"' in body
    assert 'No customer matches "zzz".' in html(owner_client.get(base, {"q": "zzz"}))
    assert html(owner_client.get(base, {"q": "  "})).strip() == ""
    assert html(owner_client.get(base)).strip() == ""


def test_choose_customer_sets_draft(owner_client, empty_draft, customer):
    url = f"/orders/drafts/{empty_draft.pk}/customer/"
    response = owner_client.post(url, {"customer": customer.pk}, HTTP_HX_REQUEST="true")
    empty_draft.refresh_from_db()
    assert response.status_code == 204 and "HX-Location" in response.headers
    assert empty_draft.customer == customer
    other = Customer.objects.create(name="Meera Iyer")
    plain = owner_client.post(url, {"customer": other.pk})
    empty_draft.refresh_from_db()
    assert plain.status_code == 303 and empty_draft.customer == other


@pytest.mark.parametrize("value", ["", "abc", "999999"])
def test_choose_customer_bad_value_404(owner_client, empty_draft, value):
    url = f"/orders/drafts/{empty_draft.pk}/customer/"
    assert owner_client.post(url, {"customer": value}).status_code == 404
    empty_draft.refresh_from_db()
    assert empty_draft.customer is None


def test_change_customer_recopies_measurements(
    owner_client, empty_draft, blank_item, blouse, customer
):
    MeasurementSet.objects.create(
        customer=customer, product=blouse, values=[{"name": "Bust", "value": "36"}]
    )
    owner_client.post(
        f"/orders/drafts/{empty_draft.pk}/customer/", {"customer": customer.pk}
    )
    blank_item.refresh_from_db()
    assert blank_item.measurements[0] == {"name": "Bust", "value": "36"}


def test_new_customer_sheet_get_and_post(owner_client, empty_draft):
    url = f"/orders/drafts/{empty_draft.pk}/customer/new/"
    assert "Add customer" in html(owner_client.get(url, {"q": "Priya"}))
    response = owner_client.post(url, {"name": "Priya Nair", "phone": "9876543210"})
    customer = Customer.objects.get(name="Priya Nair")
    empty_draft.refresh_from_db()
    assert empty_draft.customer == customer
    assert "HX-Location" in response.headers
    assert "Priya Nair added" in response["HX-Trigger"]
    invalid = owner_client.post(url, {"name": "", "phone": ""})
    assert invalid.status_code == 422
    assert Customer.objects.count() == 1


def test_customer_routes_404_on_placed_order(owner_client, customer, blouse):
    order = Order.objects.create(customer=customer, due_date="2026-12-01")
    OrderItem.from_product(order, blouse)
    order.place()
    base = f"/orders/drafts/{order.pk}/customer/"
    assert owner_client.post(base, {"customer": customer.pk}).status_code == 404
    assert owner_client.get(base + "search/").status_code == 404
    assert owner_client.get(base + "new/").status_code == 404


def test_item_pages_without_customer(owner_client, empty_draft, blouse):
    add = f"/orders/drafts/{empty_draft.pk}/items/new/"
    body = html(owner_client.get(add, {"product": blouse.pk}))
    assert "New order" in body and "Choose the customer to copy" in body
    response = owner_client.post(
        add, {"type": "custom", "product": blouse.pk, "price": "1200"}
    )
    assert response.status_code == 303
    item = empty_draft.items.get()
    assert [m["value"] for m in item.measurements] == ["", ""]
    edit = f"/orders/drafts/{empty_draft.pk}/items/{item.pk}/"
    assert owner_client.get(edit).status_code == 200
    measurements = edit + "measurements/"
    page = owner_client.get(measurements)
    assert page.status_code == 200 and "Also update" not in html(page)
    saved = owner_client.post(
        measurements,
        {
            "unit": "in",
            "field": ["Bust", "Waist"],
            "value": ["34", "28"],
            "also_update": "1",
        },
    )
    assert saved.status_code == 303
    assert not MeasurementSet.objects.exists()


def test_draft_hint_only_with_items(owner_client, empty_draft, blouse):
    url = f"/orders/drafts/{empty_draft.pk}/"
    hint = "Tap an item to change its options"
    assert hint not in html(owner_client.get(url))
    OrderItem.from_product(empty_draft, blouse)
    assert hint in html(owner_client.get(url))
