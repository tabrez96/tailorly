from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from orders.models import Order, OrderItem
from orders.tests.conftest import make_employee, make_order
from orders.views import ONE_ITEM

pytestmark = pytest.mark.django_db


def html(response):
    return response.content.decode()


def future(days=5):
    return timezone.localdate() + timedelta(days=days)


@pytest.fixture
def order(customer, blouse):
    placed = make_order(customer, 1, due=future())
    placed.items.all().delete()
    OrderItem.from_product(
        placed,
        blouse,
        [{"name": "Lining", "answer": "No"}],
        price=Decimal("1200"),
    )
    return placed


@pytest.fixture
def item(order):
    return order.items.get()


@pytest.fixture
def edit_url(order):
    return f"/orders/{order.pk}/edit/"


@pytest.fixture
def item_url(order, item):
    return f"/orders/{order.pk}/edit/items/{item.pk}/"


def post_item(client, url, product, **extra):
    data = {"type": product.type, "product": product.pk, "price": "1500", **extra}
    return client.post(url, data, HTTP_HX_REQUEST="true")


def test_edit_button_on_s04_for_owner(owner_client, order, edit_url):
    page = html(owner_client.get(f"/orders/{order.pk}/"))
    assert f'href="{edit_url}"' in page and "Edit" in page


def test_no_edit_button_for_employee_or_delivered_ready_made(
    client, customer, owner_client
):
    placed = make_order(customer, 1, due=future())
    ready_made = make_order(customer, 2, status="delivered")
    ready_made.items.update(type="ready_made")
    page = html(owner_client.get(f"/orders/{ready_made.pk}/"))
    assert f"/orders/{ready_made.pk}/edit/" not in page
    user, ali = make_employee("9000000002", "ali")
    placed.assignee = ali
    placed.save()
    client.force_login(user)
    assert f"/orders/{placed.pk}/edit/" not in html(client.get(f"/orders/{placed.pk}/"))


def test_edit_page_shows_due_date_and_items(owner_client, order, item, edit_url):
    page = html(owner_client.get(edit_url))
    assert f'value="{order.due_date.isoformat()}"' in page
    assert "Blouse" in page and f"{edit_url}items/{item.pk}/" in page


def test_save_due_date_returns_to_s04_with_toast(owner_client, order, edit_url):
    new = future(9)
    response = owner_client.post(
        edit_url, {"due_date": new.isoformat()}, HTTP_HX_REQUEST="true"
    )
    assert f"/orders/{order.pk}/" in response["HX-Location"]
    assert "Order #1 saved" in response["HX-Trigger"]
    order.refresh_from_db()
    assert order.due_date == new


def test_empty_due_date_refused(owner_client, order, edit_url):
    response = owner_client.post(edit_url, {"due_date": ""}, HTTP_HX_REQUEST="true")
    assert response.status_code == 422
    assert "Choose a due date." in html(response)
    order.refresh_from_db()
    assert order.due_date == future()


def test_past_due_date_refused_unless_unchanged(owner_client, order, edit_url):
    past = timezone.localdate() - timedelta(days=3)
    response = owner_client.post(
        edit_url, {"due_date": past.isoformat()}, HTTP_HX_REQUEST="true"
    )
    assert response.status_code == 422
    assert "Choose today or a later date." in html(response)
    Order.objects.filter(pk=order.pk).update(due_date=past)
    response = owner_client.post(edit_url, {"due_date": past.isoformat()})
    assert response.status_code == 303


def test_ready_made_order_has_no_due_date(owner_client, customer, kurta):
    placed = make_order(customer, 3)
    placed.items.all().delete()
    OrderItem.from_product(placed, kurta)
    url = f"/orders/{placed.pk}/edit/"
    assert 'name="due_date"' not in html(owner_client.get(url))
    assert owner_client.post(url, {}).status_code == 303


def test_edit_item_price_and_notes(owner_client, order, item, item_url, blouse):
    response = post_item(owner_client, item_url, blouse, notes="Hooks")
    assert f"/orders/{order.pk}/edit/" in response["HX-Location"]
    assert "Blouse saved" in response["HX-Trigger"]
    item.refresh_from_db()
    assert item.price == Decimal("1500") and item.notes == "Hooks"
    assert "₹1,500" in html(owner_client.get(f"/orders/{order.pk}/"))


def test_edit_item_negative_price_saves_nothing(owner_client, item, item_url, blouse):
    response = post_item(owner_client, item_url, blouse, price="-5")
    assert response.status_code == 422
    assert "Enter a price of ₹0 or more." in html(response)
    item.refresh_from_db()
    assert item.price == Decimal("1200")


def test_placed_item_keeps_its_product(owner_client, item, item_url, kurta, blouse):
    item.measurements = [{"name": "Bust", "value": "34"}]
    item.save()
    post_item(owner_client, item_url, kurta, type="ready_made")
    item.refresh_from_db()
    assert item.name == "Blouse" and item.type == "custom"
    assert item.measurements == [{"name": "Bust", "value": "34"}]


def test_item_page_hides_product_change_measure_and_photos(
    owner_client, item_url, item
):
    item.measurements = [{"name": "Bust", "value": "34"}]
    item.save()
    page = html(owner_client.get(item_url))
    assert "Order #1 · Item 1 of 1" in page
    for gone in ("measure-edit", "photo-add", "Change</button>", 'name="type"'):
        assert gone not in page


def test_add_item_to_placed_order(owner_client, order, kurta, edit_url):
    response = post_item(owner_client, edit_url + "items/new/", kurta, price="799")
    assert edit_url in response["HX-Location"]
    assert "Cotton kurta added" in response["HX-Trigger"]
    assert order.items.count() == 2
    assert "₹1,999" in html(owner_client.get(f"/orders/{order.pk}/"))


def test_remove_item(owner_client, order, kurta, edit_url):
    extra = OrderItem.from_product(order, kurta)
    response = owner_client.post(
        f"{edit_url}items/{extra.pk}/remove/", HTTP_HX_REQUEST="true"
    )
    assert order.items.count() == 1
    assert "Cotton kurta removed" in response["HX-Trigger"]


def test_remove_last_item_refused(owner_client, order, item, item_url):
    response = owner_client.post(item_url + "remove/", HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    assert response["HX-Reswap"] == "none"
    assert ONE_ITEM in response["HX-Trigger"]
    assert order.items.count() == 1
    plain = owner_client.post(item_url + "remove/")
    assert plain.status_code == 303 and order.items.count() == 1


def test_remove_refused_when_delivered_after_load(
    owner_client, order, kurta, edit_url, monkeypatch
):
    from orders import views

    extra = OrderItem.from_product(order, kurta)
    loaded = views._editable_or_404

    def load_then_deliver(pk):
        found = loaded(pk)  # still Ready here, as in a request that raced delivery
        Order.objects.filter(pk=pk).update(status=Order.DELIVERED)
        return found

    monkeypatch.setattr(views, "_editable_or_404", load_then_deliver)
    response = owner_client.post(
        f"{edit_url}items/{extra.pk}/remove/", HTTP_HX_REQUEST="true"
    )
    assert response.status_code == 404
    assert order.items.count() == 2


def _deliver_after_load(monkeypatch):
    from orders import views

    loaded = views._editable_or_404

    def load_then_deliver(pk):
        found = loaded(pk)  # still Ready here, as in a request that raced delivery
        Order.objects.filter(pk=pk).update(status=Order.DELIVERED)
        return found

    monkeypatch.setattr(views, "_editable_or_404", load_then_deliver)


def test_edit_item_refused_when_delivered_after_load(
    owner_client, order, item, item_url, blouse, monkeypatch
):
    _deliver_after_load(monkeypatch)
    assert post_item(owner_client, item_url, blouse).status_code == 404
    item.refresh_from_db()
    assert item.price == Decimal("1200")


def test_add_item_refused_when_delivered_after_load(
    owner_client, order, edit_url, kurta, monkeypatch
):
    _deliver_after_load(monkeypatch)
    assert post_item(owner_client, edit_url + "items/new/", kurta).status_code == 404
    assert order.items.count() == 1


def test_delivered_items_locked(owner_client, order, item, item_url, blouse, kurta):
    Order.objects.filter(pk=order.pk).update(status="delivered")
    assert owner_client.get(item_url).status_code == 404
    assert post_item(owner_client, item_url, blouse).status_code == 404
    assert owner_client.get(f"/orders/{order.pk}/edit/items/new/").status_code == 404
    assert (
        post_item(
            owner_client, f"/orders/{order.pk}/edit/items/new/", kurta
        ).status_code
        == 404
    )
    assert owner_client.post(item_url + "remove/").status_code == 404
    item.refresh_from_db()
    assert item.price == Decimal("1200") and order.items.count() == 1
    page = html(owner_client.get(f"/orders/{order.pk}/edit/"))
    assert 'id="add-item"' not in page and item_url not in page


def test_employee_cannot_edit(client, order, item, item_url, edit_url, blouse):
    user, _ = make_employee("9000000002", "ali")
    client.force_login(user)
    assert client.get(edit_url).status_code == 302
    assert client.post(edit_url, {"due_date": future(9).isoformat()}).status_code == 302
    assert client.get(item_url).status_code == 302
    assert post_item(client, item_url, blouse).status_code == 403
    order.refresh_from_db()
    item.refresh_from_db()
    assert order.due_date == future() and item.price == Decimal("1200")


def test_draft_and_edit_routes_do_not_cross(owner_client, customer, order, item):
    draft = Order.objects.create(customer=customer)
    assert owner_client.get(f"/orders/{draft.pk}/edit/").status_code == 404
    assert owner_client.get(f"/orders/{draft.pk}/edit/items/new/").status_code == 404
    assert (
        owner_client.get(f"/orders/drafts/{order.pk}/items/{item.pk}/").status_code
        == 404
    )


def test_free_order_shows_usual_prices(owner_client, customer):
    placed = make_order(customer, 4, free=True, due=future())
    page = html(owner_client.get(f"/orders/{placed.pk}/edit/"))
    assert "usual" in page and "Free, not charged" in page
