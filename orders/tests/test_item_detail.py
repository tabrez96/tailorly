import json
from datetime import date
from decimal import Decimal as D

import pytest
from django.test import Client
from django.utils import timezone

from accounts.roles import EMPLOYEE, add_to_role
from catalog.models import Product, ProductOption
from core.money import format_inr
from orders.models import MaterialLine, Order, OrderItem
from orders.tests.conftest import make_employee, make_order
from reports.order_costs import item_cost_card

pytestmark = pytest.mark.django_db
HX = {"HTTP_HX_REQUEST": "true"}
PARTIAL = {"HTTP_HX_REQUEST": "true", "HTTP_HX_REQUEST_TYPE": "partial"}


@pytest.fixture
def order(customer, blouse):
    _, ali = make_employee("9000000002", "ali")
    order = make_order(customer, 1042, status="in_progress", price="1800")
    order.assignee = ali
    order.due_date = date(2026, 11, 13)
    order.save()
    item = order.items.get()
    item.product = blouse
    item.options = [{"name": "Lining", "answer": "Yes"}]
    item.measurements = [{"name": "Bust", "value": "34"}]
    item.notes = "Keep the hem narrow"
    item.save()
    ProductOption.objects.filter(product=blouse).update(
        asked_when=ProductOption.WHEN_DONE
    )
    return order


@pytest.fixture
def item(order):
    return order.items.get()


def url(item):
    return f"/orders/{item.order_id}/items/{item.pk}/"


def test_owner_sees_item_detail(owner_client, item):
    body = owner_client.get(url(item)).content.decode()
    assert "ORD-1042 · ASHA RAO · ITEM 1 OF 1" in body
    assert "<h1" in body and "Blouse" in body
    assert "₹1,800" in body
    assert "Options" in body and "asked when done" in body
    assert "Measurements" in body and "Keep the hem narrow" in body
    assert "Notes for ali" in body
    assert (
        f'href="/production/items/{item.pk}/"' in body
        or "item-card__production" in body
    )
    assert "Open order" in body and f'href="/orders/{item.order_id}/"' in body


def test_direct_load_renders_full_shell(owner_client, item):
    assert "<html" in owner_client.get(url(item)).content.decode()


def test_partial_request_renders_fragment(owner_client, item):
    response = owner_client.get(url(item), **PARTIAL)
    assert response.status_code == 200
    assert "<html" not in response.content.decode()


def test_employee_gets_404(client, item):
    user, _ = make_employee("9000000003", "ravi")
    add_to_role(user, EMPLOYEE)
    client.force_login(user)
    assert client.get(url(item)).status_code == 404
    assert client.get(url(item), **PARTIAL).status_code == 404


def test_signed_out_redirects(item):
    assert Client().get(url(item)).status_code == 302


def test_item_of_other_order_404(owner_client, customer, item):
    other = make_order(customer, 7)
    assert owner_client.get(f"/orders/{other.pk}/items/{item.pk}/").status_code == 404


def test_draft_order_404(owner_client, customer):
    draft = make_order(customer, 0, status="draft")
    item = draft.items.get()
    assert owner_client.get(url(item)).status_code == 404


def test_ready_made_has_no_measurements_options_production(owner_client, customer):
    order = make_order(customer, 2, price="450")
    item = order.items.get()
    item.type = Product.READY_MADE
    item.save()
    body = owner_client.get(url(item)).content.decode()
    assert "Sold off the shelf" in body
    assert "Ready-made items cost their materials only." in body
    for absent in ("Measurements", "Options", "item-card__production"):
        assert absent not in body
    assert 'id="item-add-material"' not in body


def test_no_materials_empty_state(owner_client, item):
    assert "No materials yet." in owner_client.get(url(item)).content.decode()


def test_free_order_shows_cost_to_shop(owner_client, customer):
    order = make_order(customer, 3, free=True, price="1000")
    body = owner_client.get(url(order.items.get())).content.decode()
    assert "Cost to the shop" in body and "Usual price" in body
    assert "Gain on this item" not in body


def test_gain_matches_costing(owner_client, item):
    MaterialLine.objects.create(
        item=item,
        name="Lining",
        unit="m",
        quantity=D(2),
        cost_price=D(60),
        selling_price=D(90),
    )
    gain = item_cost_card(OrderItem.objects.get(pk=item.pk), timezone.now())[
        "item"
    ].gain
    body = owner_client.get(url(item)).content.decode()
    assert "Gain on this item" in body and format_inr(gain) in body


def test_add_material_on_item_returns_item_page(owner_client, item, lining):
    response = owner_client.post(
        f"{url(item)}materials/new/?on=item",
        {
            "item": item.pk,
            "material": lining.pk,
            "qty": "2",
            "cost": "120",
            "sell": "180",
            "bought_on": "2026-11-12",
            "on": "item",
        },
        **HX,
    )
    assert response.status_code == 200
    assert response["HX-Retarget"] == "#page"
    assert "sheet:close" in json.loads(response["HX-Trigger"])
    body = response.content.decode()
    assert "Lining, cotton" in body and "Gain on this item" in body
    assert "item-detail" in body and "No materials yet." not in body


def test_material_sheet_on_item_has_no_item_picker(owner_client, order, item, lining):
    OrderItem.objects.create(
        order=order, name="Skirt", type=Product.CUSTOM, price=D(5), usual_price=D(5)
    )
    body = owner_client.get(f"{url(item)}materials/new/?on=item").content.decode()
    assert "mat-item-" not in body
    assert 'name="on" value="item"' in body


def test_measurements_save_on_item_returns_item_page(owner_client, item):
    response = owner_client.post(
        f"{url(item)}measurements/?on=item",
        {"field": ["Bust", "Waist"], "value": ["36", "30"]},
        **HX,
    )
    assert response.status_code == 200
    assert response["HX-Retarget"] == "#page"
    assert "item-detail" in response.content.decode()
    item.refresh_from_db()
    assert item.measurements[0]["value"] == "36"


def test_s04_chevron_links_to_item_detail(owner_client, client, item):
    link = f'href="{url(item)}"'
    assert link in owner_client.get(f"/orders/{item.order_id}/").content.decode()
    user, _ = make_employee("9000000004", "meena")
    add_to_role(user, EMPLOYEE)
    client.force_login(user)
    assert link not in client.get(f"/orders/{item.order_id}/").content.decode()


def test_edit_hidden_when_delivered(owner_client, order, item):
    assert "Edit</a>" in owner_client.get(url(item)).content.decode()
    Order.objects.filter(pk=order.pk).update(status=Order.DELIVERED)
    assert "Edit</a>" not in owner_client.get(url(item)).content.decode()
