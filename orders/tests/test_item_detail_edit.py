from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from accounts.roles import EMPLOYEE, add_to_role
from catalog.models import Product
from customers.models import MeasurementSet
from orders.models import ItemPhoto, Order, OrderItem
from orders.photos import NOT_A_PHOTO, TOO_MANY, add_photo
from orders.tests.conftest import make_employee, make_order
from orders.tests.test_photos import png

HX = {"HTTP_HX_REQUEST": "true"}


@pytest.fixture
def item(customer, blouse):
    order = make_order(customer, 1)
    order.items.all().delete()
    return OrderItem.objects.create(
        order=order,
        product=blouse,
        name="Blouse",
        type=Product.CUSTOM,
        price=Decimal("1200"),
        usual_price=Decimal("1200"),
        measurements=[{"name": "Bust", "value": "34"}],
    )


def sheet(item):
    return reverse("order_item_measurements_sheet", args=[item.order_id, item.pk])


def photo_url(item):
    return reverse("order_item_photo_add", args=[item.order_id, item.pk])


def save(client, item, also="1", **extra):
    data = {"field": ["Bust", "Waist"], "value": ["35", "28"], **extra}
    if also:
        data["also_update"] = also
    return client.post(sheet(item), data, **HX)


def test_sheet_get_shows_item_values_and_also_switch_on(owner_client, item):
    response = owner_client.get(sheet(item))
    body = response.content.decode()
    assert response.status_code == 200
    assert "Blouse measurements" in body
    assert 'value="34"' in body
    assert "Item 1 of 1" in body
    assert "Also update Asha&#x27;s saved Blouse measurements" in body
    assert "checked" in body


def test_save_with_also_updates_item_and_customer_set(owner_client, item, blouse):
    response = save(owner_client, item)
    pairs = [{"name": "Bust", "value": "35"}, {"name": "Waist", "value": "28"}]
    item.refresh_from_db()
    assert response.status_code == 200
    assert item.measurements == pairs
    saved = MeasurementSet.objects.get(customer=item.order.customer, product=blouse)
    assert saved.values == pairs
    assert response["HX-Retarget"] == f"#item-{item.pk}"
    assert response["HX-Reswap"] == "outerHTML"
    body = response.content.decode()
    assert f'id="item-{item.pk}"' in body
    assert "order-invoice" not in body
    assert "sheet:close" in response["HX-Trigger"]


def test_save_without_also_changes_only_item(owner_client, item, blouse):
    old = [{"name": "Bust", "value": "30"}]
    MeasurementSet.objects.create(
        customer=item.order.customer, product=blouse, values=old
    )
    save(owner_client, item, also="")
    item.refresh_from_db()
    assert item.measurements[0]["value"] == "35"
    assert MeasurementSet.objects.get(product=blouse).values == old


def test_save_without_also_does_not_create_set(owner_client, item):
    save(owner_client, item, also="")
    assert not MeasurementSet.objects.exists()


def test_save_without_htmx_redirects_to_order(owner_client, item):
    response = owner_client.post(sheet(item), {"field": ["Bust"], "value": ["35"]})
    assert response.status_code == 303
    assert response.url == reverse("order", args=[item.order_id])


def test_invalid_value_keeps_sheet_and_saves_nothing(owner_client, item, blouse):
    response = owner_client.post(
        sheet(item),
        {"field": ["Bust", "Waist"], "value": ["abc", "28"], "also_update": "1"},
        **HX,
    )
    body = response.content.decode()
    assert response.status_code == 422
    assert "Enter a number" in body
    assert "aria-invalid" in body
    assert 'value="abc"' in body
    item.refresh_from_db()
    assert item.measurements == [{"name": "Bust", "value": "34"}]
    assert not MeasurementSet.objects.exists()


def test_ready_made_item_404(owner_client, item, kurta):
    item.type, item.product, item.measurements = Product.READY_MADE, kurta, []
    item.save()
    assert owner_client.get(sheet(item)).status_code == 404


def test_draft_order_404(owner_client, item):
    Order.objects.filter(pk=item.order_id).update(status=Order.DRAFT)
    assert owner_client.get(sheet(item)).status_code == 404
    response = owner_client.post(photo_url(item), {"photo": png(40, 40)})
    assert response.status_code == 404


def test_item_from_other_order_404(owner_client, item, customer):
    other = make_order(customer, 2)
    url = reverse("order_item_measurements_sheet", args=[other.pk, item.pk])
    assert owner_client.get(url).status_code == 404


def test_no_product_hides_switch_and_ignores_also(owner_client, item):
    item.product = None
    item.save()
    assert "Also update" not in owner_client.get(sheet(item)).content.decode()
    save(owner_client, item)
    assert not MeasurementSet.objects.exists()


def test_employee_cannot_save_measurements(client, item):
    user, _ = make_employee("9000000002", "ali")
    add_to_role(user, EMPLOYEE)
    client.force_login(user)
    assert save(client, item).status_code in (302, 403)
    item.refresh_from_db()
    assert item.measurements == [{"name": "Bust", "value": "34"}]


def test_signed_out_cannot_save_measurements(client, item):
    response = save(client, item)
    assert response["HX-Redirect"].startswith(reverse("sign_in"))
    item.refresh_from_db()
    assert item.measurements == [{"name": "Bust", "value": "34"}]


def test_photo_add_attaches_to_item(owner_client, item, media):
    response = owner_client.post(photo_url(item), {"photo": png(400, 300)})
    data = response.json()
    assert response.status_code == 201
    assert {"id", "thumb", "full"} <= set(data)
    assert item.photos.count() == 1


def test_photo_add_limit(owner_client, item, media):
    for _ in range(3):
        add_photo(item, png(40, 40))
    response = owner_client.post(photo_url(item), {"photo": png(40, 40)})
    assert response.status_code == 400
    assert response.json()["error"] == TOO_MANY
    assert item.photos.count() == 3


def test_photo_add_not_an_image(owner_client, item, media):
    text = SimpleUploadedFile("a.txt", b"hello", "text/plain")
    response = owner_client.post(photo_url(item), {"photo": text})
    assert response.status_code == 400
    assert response.json()["error"] == NOT_A_PHOTO


def test_photo_add_without_file(owner_client, item, media):
    assert owner_client.post(photo_url(item)).status_code == 400


def test_photo_add_employee_and_signed_out_denied(client, item, media):
    client.post(photo_url(item), {"photo": png(40, 40)})
    user, _ = make_employee("9000000002", "ali")
    add_to_role(user, EMPLOYEE)
    client.force_login(user)
    client.post(photo_url(item), {"photo": png(40, 40)})
    assert not ItemPhoto.objects.exists()


def test_detail_card_edit_and_add_for_owner_only(owner_client, client, item):
    page = reverse("order", args=[item.order_id])
    body = owner_client.get(page).content.decode()
    assert f"measure-{item.pk}" in body
    assert f"photo-add-{item.pk}" in body
    user, ali = make_employee("9000000002", "ali")
    add_to_role(user, EMPLOYEE)
    Order.objects.update(assignee=ali)
    client.force_login(user)
    body = client.get(page).content.decode()
    assert f"measure-{item.pk}" not in body
    assert f"photo-add-{item.pk}" not in body


def test_card_empty_measurements_shows_add_button(owner_client, item):
    item.measurements = []
    item.save()
    body = owner_client.get(reverse("order", args=[item.order_id])).content.decode()
    assert f"measure-{item.pk}" in body
    assert "Add measurements" in body
    assert ">Edit</button>" not in body
