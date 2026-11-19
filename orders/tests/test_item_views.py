from decimal import Decimal

import pytest

from catalog.models import Product
from core.pages import page_location
from customers.models import MeasurementSet
from orders.models import Order, OrderItem

pytestmark = pytest.mark.django_db


@pytest.fixture
def draft(customer):
    return Order.objects.create(customer=customer)


@pytest.fixture
def add_url(draft):
    return f"/orders/drafts/{draft.pk}/items/new/"


@pytest.fixture
def saved_set(customer, blouse):
    return MeasurementSet.objects.create(
        customer=customer,
        product=blouse,
        values=[{"name": "Bust", "value": "34"}, {"name": "Waist", "value": "28"}],
    )


def html(response):
    return response.content.decode()


def test_new_order_creates_draft_and_moves_to_it(owner_client, customer):
    response = owner_client.post(
        "/orders/drafts/", {"customer": customer.pk}, HTTP_HX_REQUEST="true"
    )
    order = Order.objects.get()
    assert order.status == Order.DRAFT and order.customer == customer
    assert response.status_code == 204
    assert f"/orders/drafts/{order.pk}/" in response["HX-Location"]
    plain = owner_client.post("/orders/drafts/", {"customer": customer.pk})
    assert plain.status_code == 303
    assert plain["Location"] == f"/orders/drafts/{Order.objects.latest('pk').pk}/"


def test_page_location_without_toast_has_no_trigger():
    assert "HX-Trigger" not in page_location("/x/")


def test_new_order_get_not_allowed(owner_client):
    assert owner_client.get("/orders/drafts/").status_code == 405


@pytest.mark.parametrize("value", ["999999", "abc", ""])
def test_new_order_unknown_customer_404(owner_client, value):
    assert owner_client.post("/orders/drafts/", {"customer": value}).status_code == 404
    assert not Order.objects.exists()


def test_employee_cannot_open_draft(client, employee_user, draft):
    client.force_login(employee_user[0])
    response = client.get(f"/orders/drafts/{draft.pk}/")
    assert response.status_code == 302


def test_draft_page_lists_items_and_add_link(owner_client, draft, blouse, add_url):
    OrderItem.from_product(draft, blouse, [{"name": "Lining", "answer": "Yes"}])
    page = html(owner_client.get(f"/orders/drafts/{draft.pk}/"))
    assert "Blouse" in page and "Custom" in page and "Lining · no measurements" in page
    assert "₹1,200" in page and "1 item" in page
    assert f'href="{add_url}"' in page and "+ Add item" in page


def test_placed_order_draft_and_item_pages_404(owner_client, draft, blouse):
    OrderItem.from_product(draft, blouse)
    draft.due_date = "2030-01-01"
    draft.place()
    assert owner_client.get(f"/orders/drafts/{draft.pk}/").status_code == 404
    assert owner_client.get(f"/orders/drafts/{draft.pk}/items/new/").status_code == 404
    assert owner_client.get("/orders/drafts/99999/items/new/").status_code == 404


def test_add_item_page_defaults_to_custom_products(
    owner_client, add_url, blouse, kurta
):
    page = html(owner_client.get(add_url))
    assert "New order · Asha Rao" in page
    assert "Blouse" in page and "Cotton kurta" not in page


def test_choosing_product_fills_price_and_options(owner_client, add_url, blouse):
    page = html(owner_client.get(f"{add_url}?type=custom&product={blouse.pk}"))
    assert 'value="1200"' in page
    assert "Usual price ₹1,200" in page
    assert "Uses Lining, cotton." in page
    assert "Custom · 1 option · 2 measurements" in page


def test_option_group_labels_have_real_ids(owner_client, add_url, blouse):
    page = html(owner_client.get(f"{add_url}?type=custom&product={blouse.pk}"))
    assert 'id="-label"' not in page
    assert 'aria-labelledby="id_opt_' in page
    assert 'id="id_opt_' in page


def test_bad_product_param_is_ignored(owner_client, add_url, kurta, blouse):
    for raw in ("abc", str(kurta.pk), "0"):
        page = html(owner_client.get(f"{add_url}?type=custom&product={raw}"))
        assert 'value="1200"' not in page


def test_measurement_tiles_from_saved_set(owner_client, add_url, blouse, saved_set):
    page = html(owner_client.get(f"{add_url}?product={blouse.pk}"))
    assert "Bust" in page and "34" in page
    assert "Copied from Asha's Blouse set" in page


def test_no_saved_set_line(owner_client, add_url, blouse):
    page = html(owner_client.get(f"{add_url}?product={blouse.pk}"))
    assert "No saved Blouse measurements for Asha yet." in page


def test_ready_made_shows_no_options_or_measurements(owner_client, add_url, kurta):
    page = html(owner_client.get(f"{add_url}?type=ready_made&product={kurta.pk}"))
    assert "Sold as it is" in page
    assert "Measurements" not in page and "Options" not in page
    assert "No materials for this item." in page


def test_no_products_state(owner_client, add_url, blouse):
    page = html(owner_client.get(f"{add_url}?type=ready_made"))
    assert "No ready-made products yet. Add one in Products first." in page
    assert 'href="/products/"' in page


def test_save_without_product_shows_error(owner_client, add_url, blouse):
    response = owner_client.post(add_url, {"type": "custom", "price": "1200"})
    page = html(response)
    assert response.status_code == 422
    assert "Choose a product." in page
    assert 'aria-invalid="true"' in page
    assert "1 thing needs fixing before you can add this item." in page


def test_save_empty_price_shows_usual_price(owner_client, add_url, blouse):
    response = owner_client.post(
        add_url, {"type": "custom", "product": blouse.pk, "price": ""}
    )
    assert response.status_code == 422
    assert "Enter a price. The usual price for a Blouse is ₹1,200." in html(response)


def test_no_product_and_no_price_gives_plain_price_message(owner_client, add_url):
    page = html(owner_client.post(add_url, {"type": "custom"}))
    assert "Enter a price." in page and "2 things need fixing" in page


@pytest.mark.parametrize(
    ("price", "message"),
    [
        ("abc", "Enter a price in rupees, like 1800."),
        ("-5", "Enter a price of ₹0 or more."),
    ],
)
def test_bad_prices(owner_client, add_url, blouse, price, message):
    response = owner_client.post(
        add_url, {"type": "custom", "product": blouse.pk, "price": price}
    )
    assert response.status_code == 422 and message in html(response)


def test_add_to_order_saves_copy(owner_client, draft, add_url, blouse, saved_set):
    option = blouse.options.get()
    response = owner_client.post(
        add_url,
        {
            "type": "custom",
            "product": blouse.pk,
            "price": "1,500",
            f"opt_{option.pk}": "Yes",
            "notes": " Hooks ",
        },
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 204
    assert f"/orders/drafts/{draft.pk}/" in response["HX-Location"]
    assert "Blouse added" in response["HX-Trigger"]
    item = draft.items.get()
    assert item.price == Decimal("1500") and item.usual_price == Decimal("1200")
    assert item.options == [{"name": "Lining", "answer": "Yes"}]
    assert item.notes == "Hooks"
    assert item.measurements == saved_set.values


def test_form_guards_double_submit_and_latest_pick(owner_client, add_url):
    page = html(owner_client.get(add_url))
    assert 'hx-sync="this:drop"' in page
    assert 'hx-disable="find button[type=submit]"' in page
    assert 'hx-sync="this:replace"' in page
    assert 'hx-disable="#item-submit"' in page
    assert 'id="item-submit"' in page


def test_one_post_makes_one_item(owner_client, draft, add_url, blouse):
    owner_client.post(
        add_url,
        {"type": "custom", "product": blouse.pk, "price": "1200"},
        HTTP_HX_REQUEST="true",
    )
    assert draft.items.count() == 1


def test_item_measurements_ignore_later_set_changes(
    owner_client, draft, add_url, blouse, saved_set
):
    owner_client.post(add_url, {"type": "custom", "product": blouse.pk, "price": "1"})
    saved_set.values = [{"name": "Bust", "value": "40"}]
    saved_set.save()
    assert draft.items.get().measurements[0]["value"] == "34"


def test_unanswered_yes_no_is_stored_as_no(owner_client, draft, add_url, blouse):
    owner_client.post(add_url, {"type": "custom", "product": blouse.pk, "price": "1"})
    assert draft.items.get().options == [{"name": "Lining", "answer": "No"}]


def test_plain_post_redirects(owner_client, draft, add_url, blouse):
    response = owner_client.post(
        add_url, {"type": "custom", "product": blouse.pk, "price": "1"}
    )
    assert response.status_code == 303
    assert response["Location"] == f"/orders/drafts/{draft.pk}/"


def test_ready_made_item_saved_without_measurements(
    owner_client, draft, add_url, kurta
):
    owner_client.post(
        add_url, {"type": "ready_made", "product": kurta.pk, "price": "799"}
    )
    item = draft.items.get()
    assert item.type == Product.READY_MADE and item.measurements == []


def test_other_type_product_rejected(owner_client, draft, add_url, kurta):
    response = owner_client.post(
        add_url, {"type": "custom", "product": kurta.pk, "price": "799"}
    )
    assert response.status_code == 422
    assert not draft.items.exists()


def test_choice_option_stored_and_left_out_when_empty(
    owner_client, draft, add_url, blouse
):
    from catalog.models import ProductOption

    sleeve = ProductOption.objects.create(
        product=blouse, name="Sleeve", answer="choice", choices=["Short", "Full"]
    )
    base = {"type": "custom", "product": blouse.pk, "price": "1"}
    owner_client.post(add_url, base)
    owner_client.post(add_url, {**base, f"opt_{sleeve.pk}": "Full"})
    first, second = draft.items.all()
    assert [o["name"] for o in first.options] == ["Lining"]
    assert second.options[-1] == {"name": "Sleeve", "answer": "Full"}
    page = html(owner_client.get(f"{add_url}?product={blouse.pk}"))
    assert "ochip" in page and "Short" in page
