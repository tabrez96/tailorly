import json
import re
from datetime import date
from decimal import Decimal

import pytest
from django.test import Client

from accounts.roles import EMPLOYEE, add_to_role
from catalog.models import Product, ProductOption
from orders.models import MaterialLine, Order, OrderItem
from orders.tests.conftest import make_order

pytestmark = pytest.mark.django_db
HX = {"HTTP_HX_REQUEST": "true"}
D = Decimal


@pytest.fixture
def order(customer):
    return make_order(customer, 1)


@pytest.fixture
def item(order):
    return order.items.get()


@pytest.fixture
def canvas(db):
    return Product.objects.create(
        name="Canvas interlining",
        kind=Product.SECONDARY,
        unit="m",
        cost_price=D("80"),
        selling_price=D("100"),
        billed_by_default=False,
    )


def add_url(item, on="order"):
    return f"/orders/{item.order_id}/items/{item.pk}/materials/new/?on={on}"


def edit_url(line, on="order"):
    return (
        f"/orders/{line.item.order_id}/items/{line.item_id}/materials/{line.pk}/"
        f"?on={on}"
    )


def post_data(item, material, **extra):
    return {
        "item": item.pk,
        "material": material.pk,
        "qty": "0.5",
        "cost": "40",
        "sell": "50",
        "bought_on": "2026-11-12",
        **extra,
    }


def sheet_json(response):
    html = response.content.decode()
    raw = re.search(
        r'<script id="material-sheet-data" type="application/json">(.*?)</script>',
        html,
        re.S,
    ).group(1)
    return json.loads(raw)


def test_add_sheet_lists_most_used_first(owner_client, item, lining, canvas):
    MaterialLine.from_product(lining, D(1), item=item)
    MaterialLine.from_product(lining, D(1), item=item)
    data = sheet_json(owner_client.get(add_url(item), **HX))
    assert [m["name"] for m in data["materials"]] == [lining.name, canvas.name]
    assert data["qty"] == "1" and data["picked"] is None


def test_add_sheet_preselects_new_material(owner_client, item, canvas):
    data = sheet_json(owner_client.get(add_url(item) + f"&material={canvas.pk}"))
    assert data["picked"] == canvas.pk
    assert (data["cost"], data["sell"], data["unit"]) == ("80", "100", "m")


def test_add_saves_line_from_totals(owner_client, item, canvas):
    response = owner_client.post(
        add_url(item), post_data(item, canvas, on_bill="on"), **HX
    )
    assert response.status_code == 200
    line = item.materials.get()
    assert (line.cost_price, line.selling_price) == (D("80"), D("100"))
    assert line.quantity == D("0.5") and line.on_bill is True
    assert line.bought_on == date(2026, 11, 12)
    assert "Canvas interlining added to Blouse" in response["HX-Trigger"]


def test_add_with_blank_cost_then_edit_adds_cost(owner_client, item, canvas):
    owner_client.post(add_url(item), post_data(item, canvas, cost=""), **HX)
    line = item.materials.get()
    assert line.cost_price is None
    sheet = owner_client.get(edit_url(line)).content.decode()
    assert "Edit material" in sheet and 'placeholder="Later"' in sheet
    owner_client.post(
        edit_url(line),
        {"item": item.pk, "qty": "1.5", "cost": "60", "sell": "150"},
        **HX,
    )
    line.refresh_from_db()
    assert line.cost_price == D("40.00") and line.quantity == D("1.5")
    assert line.selling_price == D("100.00") and line.on_bill is False
    assert line.bought_on is None


def test_billed_line_adds_to_invoice_unbilled_does_not(
    owner_client, order, item, canvas
):
    assert order.invoice().total == D(1000)
    owner_client.post(add_url(item), post_data(item, canvas, qty="2", sell="200"), **HX)
    assert order.invoice().total == D(1000)
    owner_client.post(
        add_url(item), post_data(item, canvas, qty="2", sell="200", on_bill="on"), **HX
    )
    assert order.invoice().total == D(1200)
    page = owner_client.get(f"/orders/{order.pk}/").content.decode()
    invoice = page[page.index('id="order-invoice"') :]
    assert "Canvas interlining · 2 m" in invoice
    assert invoice.index("1 Blouse") < invoice.index("Canvas interlining")


def test_change_item_saves_to_other_item(owner_client, order, item, canvas):
    other = OrderItem.objects.create(
        order=order, name="Skirt", type=Product.CUSTOM, price=D(500), usual_price=D(500)
    )
    page = owner_client.get(add_url(item)).content.decode()
    assert "Change" in page and f'id="mat-item-{other.pk}"' in page
    owner_client.post(add_url(item), post_data(other, canvas), **HX)
    assert other.materials.count() == 1 and item.materials.count() == 0


def test_change_hidden_for_single_item_and_on_page(owner_client, order, item):
    assert "mat-item-" not in owner_client.get(add_url(item)).content.decode()
    OrderItem.objects.create(
        order=order, name="Skirt", type=Product.CUSTOM, price=D(5), usual_price=D(5)
    )
    assert "mat-item-" not in owner_client.get(add_url(item, "page")).content.decode()


def test_item_from_other_order_rejected(owner_client, customer, item, canvas):
    stranger = make_order(customer, 2).items.get()
    response = owner_client.post(add_url(item), post_data(stranger, canvas), **HX)
    assert response.status_code == 422
    assert MaterialLine.objects.count() == 0


def test_invalid_qty_422_keeps_sheet(owner_client, item, canvas):
    response = owner_client.post(
        add_url(item), post_data(item, canvas, qty="abc", cost=""), **HX
    )
    assert response.status_code == 422
    html = response.content.decode()
    assert "Enter a quantity above zero" in html
    assert sheet_json(response)["qty"] == "abc"
    assert MaterialLine.objects.count() == 0


def test_no_material_chosen(owner_client, item):
    response = owner_client.post(
        add_url(item), {"item": item.pk, "qty": "1", "sell": "5"}
    )
    assert response.status_code == 422
    assert "Choose a material." in response.content.decode()


def test_no_materials_yet_message(owner_client, item):
    html = owner_client.get(add_url(item)).content.decode()
    assert "No materials yet. Add one with + New material." in html


def test_remove_line(owner_client, item, canvas):
    line = MaterialLine.from_product(canvas, D(1), item=item)
    url = f"/orders/{item.order_id}/items/{item.pk}/materials/{line.pk}/remove/"
    assert owner_client.get(url).status_code == 405
    response = owner_client.post(url, **HX)
    assert response.status_code == 200
    assert MaterialLine.objects.count() == 0
    assert "Canvas interlining removed" in response["HX-Trigger"]


def test_line_on_other_item_is_404(owner_client, order, item, canvas):
    other = OrderItem.objects.create(
        order=order, name="Skirt", type=Product.CUSTOM, price=D(5), usual_price=D(5)
    )
    line = MaterialLine.from_product(canvas, D(1), item=other)
    bad = f"/orders/{order.pk}/items/{item.pk}/materials/{line.pk}/"
    assert owner_client.get(bad).status_code == 404


def test_on_page_swaps_materials_block(owner_client, item, canvas):
    response = owner_client.post(
        add_url(item, "page"), post_data(item, canvas, on="page"), **HX
    )
    assert response["HX-Retarget"] == f"#item-{item.pk}-materials"
    assert "Canvas interlining" in response.content.decode()


def test_on_order_refreshes_page(owner_client, item, canvas):
    response = owner_client.post(add_url(item), post_data(item, canvas), **HX)
    assert response["HX-Retarget"] == "#page"


def test_staff_cannot_add(order, item, canvas, employee_user):
    user, _ = employee_user
    add_to_role(user, EMPLOYEE)
    client = Client()
    client.force_login(user)
    response = client.post(add_url(item), post_data(item, canvas), **HX)
    assert response.status_code in (302, 403, 404)
    assert MaterialLine.objects.count() == 0


def test_item_card_empty_line_and_add_button(owner_client, order):
    page = owner_client.get(f"/orders/{order.pk}/").content.decode()
    assert "No materials for this item." in page
    assert "+ Add material" in page


def test_staff_sees_read_only_list(order, item, canvas, employee_user):
    user, employee = employee_user
    add_to_role(user, EMPLOYEE)
    order.assignee = employee
    order.save()
    MaterialLine.from_product(canvas, D(1), item=item)
    client = Client()
    client.force_login(user)
    page = client.get(f"/orders/{order.pk}/").content.decode()
    assert "Canvas interlining" in page
    assert "+ Add material" not in page and "/materials/" not in page


def test_no_order_level_materials_section(owner_client, order, item, canvas):
    OrderItem.objects.create(
        order=order, name="Skirt", type=Product.CUSTOM, price=D(5), usual_price=D(5)
    )
    MaterialLine.from_product(canvas, D(1), item=item)
    page = owner_client.get(f"/orders/{order.pk}/").content.decode()
    assert page.count('class="item-materials"') == 2
    for block in re.split(r"<article", page)[1:]:
        assert block.count('class="item-materials"') == 1
    assert page.split("</article>")[-1].count('class="item-materials"') == 0


def test_s20_option_at_order_adds_line(owner_client, customer, blouse, lining):
    ProductOption.objects.filter(product=blouse).update(
        asked_when=ProductOption.AT_ORDER
    )
    option = blouse.options.get()
    draft = Order.objects.create(customer=customer)
    url = f"/orders/drafts/{draft.pk}/items/new/"
    data = {
        "type": "custom",
        "product": blouse.pk,
        "price": "1200",
        f"opt_{option.pk}": "Yes",
    }
    owner_client.post(url, data)
    item = draft.items.get()
    line = item.materials.get()
    assert line.product == lining and line.quantity == D(1) and line.on_bill is True
    owner_client.post(f"/orders/drafts/{draft.pk}/items/{item.pk}/", data)
    assert item.materials.count() == 1


def test_s20_next_material_saves_and_opens_sheet(owner_client, customer, blouse):
    draft = Order.objects.create(customer=customer)
    url = f"/orders/drafts/{draft.pk}/items/new/"
    response = owner_client.post(
        url,
        {"type": "custom", "product": blouse.pk, "price": "1200", "next": "material"},
    )
    item = draft.items.get()
    assert (
        response["Location"] == f"/orders/drafts/{draft.pk}/items/{item.pk}/?material=1"
    )
    page = owner_client.get(response["Location"]).content.decode()
    assert 'hx-trigger="load"' in page and f"item-{item.pk}-materials" in page
