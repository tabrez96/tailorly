import re
from decimal import Decimal

import pytest

from customers.models import MeasurementSet
from orders.models import Order, OrderItem

pytestmark = pytest.mark.django_db


@pytest.fixture
def draft(customer):
    return Order.objects.create(customer=customer)


@pytest.fixture
def item(draft, blouse):
    OrderItem.from_product(draft, blouse)
    return OrderItem.from_product(
        draft,
        blouse,
        [{"name": "Lining", "answer": "Yes"}],
        price=Decimal("1500"),
        notes="Hooks at the back",
    )


@pytest.fixture
def edit_url(draft, item):
    return f"/orders/drafts/{draft.pk}/items/{item.pk}/"


@pytest.fixture
def draft_url(draft):
    return f"/orders/drafts/{draft.pk}/"


@pytest.fixture
def measure_url(edit_url):
    return edit_url + "measurements/"


def html(response):
    return response.content.decode()


def post_item(client, url, blouse, **extra):
    data = {"type": "custom", "product": blouse.pk, "price": "1500", **extra}
    return client.post(url, data, HTTP_HX_REQUEST="true")


def test_draft_rows_link_to_edit(owner_client, draft_url, item, edit_url):
    assert f'href="{edit_url}"' in html(owner_client.get(draft_url))


def test_edit_page_prefilled(owner_client, edit_url, blouse):
    page = html(owner_client.get(edit_url))
    assert "New order · Item 2 of 2" in page
    assert 'value="1500"' in page and "Hooks at the back" in page
    assert "Save item" in page and "Remove item" in page
    assert "Add to order" not in page
    assert re.search(r'value="Yes"[^>]*checked', page)


def test_edit_save_updates_and_returns(
    owner_client, edit_url, draft_url, draft, item, blouse
):
    response = post_item(
        owner_client,
        edit_url,
        blouse,
        price="1600",
        notes="Done",
        **{f"opt_{blouse.options.get().pk}": "No"},
    )
    assert response.status_code == 204
    assert draft_url in response["HX-Location"]
    assert "Blouse saved" in response["HX-Trigger"]
    item.refresh_from_db()
    assert item.price == Decimal("1600") and item.notes == "Done"
    assert item.options == [{"name": "Lining", "answer": "No"}]
    assert draft.items.count() == 2


def test_edit_save_keeps_item_measurements(
    owner_client, edit_url, customer, blouse, item
):
    item.measurements = [{"name": "Bust", "value": "40"}]
    item.save()
    MeasurementSet.objects.create(
        customer=customer, product=blouse, values=[{"name": "Bust", "value": "30"}]
    )
    post_item(owner_client, edit_url, blouse)
    item.refresh_from_db()
    assert item.measurements == [{"name": "Bust", "value": "40"}]


def test_edit_invalid_price_422(owner_client, edit_url, blouse, item):
    response = post_item(owner_client, edit_url, blouse, price="")
    assert response.status_code == 422
    assert "Save item" in html(response)
    item.refresh_from_db()
    assert item.price == Decimal("1500")


def test_edit_archived_product_still_saves(owner_client, edit_url, blouse, item):
    blouse.active = False
    blouse.save()
    assert "Blouse" in html(owner_client.get(edit_url))
    response = post_item(owner_client, edit_url, blouse, price="1700")
    assert response.status_code == 204
    item.refresh_from_db()
    assert item.price == Decimal("1700")


def test_remove_deletes_and_returns(owner_client, edit_url, draft_url, draft, item):
    remove = edit_url + "remove/"
    assert owner_client.get(remove).status_code == 405
    response = owner_client.post(remove, HTTP_HX_REQUEST="true")
    assert response.status_code == 204
    assert draft_url in response["HX-Location"]
    assert "Blouse removed" in response["HX-Trigger"]
    assert draft.items.count() == 1
    plain = owner_client.post(edit_url.replace(str(item.pk), "0") + "remove/")
    assert plain.status_code == 404


def test_remove_without_htmx_redirects(owner_client, edit_url, draft_url):
    response = owner_client.post(edit_url + "remove/")
    assert response.status_code == 303 and response["Location"] == draft_url


def test_other_order_item_404(owner_client, customer, draft, item, blouse):
    other = Order.objects.create(customer=customer)
    base = f"/orders/drafts/{other.pk}/items/{item.pk}/"
    assert owner_client.get(base).status_code == 404
    assert owner_client.post(base + "remove/").status_code == 404
    assert owner_client.get(base + "measurements/").status_code == 404
    draft.due_date = "2030-01-01"
    draft.place()
    mine = f"/orders/drafts/{draft.pk}/items/{item.pk}/"
    assert owner_client.get(mine).status_code == 404
    assert owner_client.post(mine + "remove/").status_code == 404
    assert owner_client.get(mine + "measurements/").status_code == 404


def test_next_measurements_goes_to_item_form(
    owner_client, edit_url, draft, item, blouse
):
    response = post_item(owner_client, edit_url, blouse, next="measurements")
    assert response["HX-Location"].count(f"{edit_url}measurements/") == 1
    assert "HX-Trigger" not in response
    add = f"/orders/drafts/{draft.pk}/items/new/"
    response = post_item(owner_client, add, blouse, next="measurements")
    new = draft.items.order_by("pk").last()
    assert f"/items/{new.pk}/measurements/" in response["HX-Location"]


def test_item_measurements_item_only(owner_client, measure_url, customer, blouse, item):
    saved = MeasurementSet.objects.create(
        customer=customer, product=blouse, values=[{"name": "Bust", "value": "30"}]
    )
    page = html(owner_client.get(measure_url))
    assert "Item 2 of 2 · Asha Rao · this order only" in page
    assert "Also update Asha&#x27;s saved Blouse measurements" in page or (
        "Also update Asha's saved Blouse measurements" in page
    )
    assert "checked" not in page.split('id="also-update"')[1].split(">")[0]
    response = owner_client.post(
        measure_url,
        {"field": ["Bust", "Waist"], "value": ["41", "33"], "unit": "in"},
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 204
    assert "measurements saved" in response["HX-Trigger"]
    item.refresh_from_db()
    saved.refresh_from_db()
    assert item.measurements[0] == {"name": "Bust", "value": "41"}
    assert saved.values == [{"name": "Bust", "value": "30"}]


def test_item_measurements_also_update(
    owner_client, measure_url, customer, blouse, item
):
    saved = MeasurementSet.objects.create(
        customer=customer, product=blouse, values=[{"name": "Bust", "value": "30"}]
    )
    owner_client.post(
        measure_url,
        {"field": ["Bust"], "value": ["41"], "unit": "in", "also_update": "1"},
    )
    saved.refresh_from_db()
    item.refresh_from_db()
    assert saved.values == item.measurements
    assert saved.values[0]["value"] == "41"


def test_item_measurements_creates_saved_set(
    owner_client, measure_url, customer, blouse, item
):
    assert not MeasurementSet.objects.exists()
    response = owner_client.post(
        measure_url,
        {"field": ["Bust"], "value": ["41"], "unit": "in", "also_update": "1"},
    )
    assert response.status_code == 303
    assert MeasurementSet.objects.get(customer=customer, product=blouse)


def test_item_measurements_invalid_422(owner_client, measure_url, customer, item):
    response = owner_client.post(
        measure_url,
        {"field": ["Bust"], "value": ["abc"], "unit": "in", "also_update": "1"},
    )
    assert response.status_code == 422
    page = html(response)
    assert "save these measurements" in page
    assert "checked" in page.split('id="also-update"')[1].split(">")[0]
    assert not MeasurementSet.objects.exists()
    item.refresh_from_db()
    assert not any(m["value"] == "abc" for m in item.measurements)


def test_no_saved_set_shows_add_measurements(owner_client, edit_url, measure_url, item):
    page = html(owner_client.get(edit_url))
    assert "Add measurements" in page and "measure-tile" not in page
    owner_client.post(measure_url, {"field": ["Bust"], "value": ["41"], "unit": "in"})
    page = html(owner_client.get(edit_url))
    assert "Add measurements" not in page
    assert "41" in page and "Measurements for this item only." in page


def test_deleted_product_item_measurements_have_no_also_update(
    owner_client, edit_url, measure_url, blouse, item
):
    item.measurements = [{"name": "Bust", "value": "40"}]
    item.save()
    blouse.delete()
    page = html(owner_client.get(measure_url))
    assert "also-update" not in page and "40" in page
    assert owner_client.get(edit_url).status_code == 200


def test_ready_made_item_measurements_404(owner_client, draft, kurta):
    item = OrderItem.from_product(draft, kurta)
    url = f"/orders/drafts/{draft.pk}/items/{item.pk}/measurements/"
    assert owner_client.get(url).status_code == 404
