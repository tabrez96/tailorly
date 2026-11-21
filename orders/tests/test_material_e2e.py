from decimal import Decimal
from pathlib import Path

import pytest
from playwright.sync_api import expect

from catalog.models import Product
from customers.models import Customer
from orders.models import Order, OrderItem
from orders.tests.conftest import make_order

pytestmark = pytest.mark.e2e

ARTIFACTS = Path(__file__).resolve().parent.parent.parent / "artifacts" / "screens"


@pytest.fixture
def shop(db):
    meera = Customer.objects.create(name="Meera Iyer", phone="9845022110")
    for name, cost, sell in (
        ("Canvas interlining", "80", "100"),
        ("Lining, cotton cream", "120", "150"),
        ("Falls, cotton", "20", "30"),
        ("Hooks", "5", "8"),
    ):
        Product.objects.create(
            name=name,
            kind=Product.SECONDARY,
            unit="m",
            cost_price=Decimal(cost),
            selling_price=Decimal(sell),
            billed_by_default=True,
        )
    order = make_order(meera, 1, status="open", price="1800")
    OrderItem.objects.create(
        order=order,
        name="Skirt",
        type=Product.CUSTOM,
        price=Decimal(900),
        usual_price=Decimal(900),
    )
    return order


def fill_sheet(page):
    page.locator("label", has_text="Canvas interlining").click()
    expect(page.get_by_label("Canvas interlining")).to_be_checked()
    page.fill("#mat-qty", "0.5")
    assert page.input_value("#mat-cost") == "40"
    assert page.input_value("#mat-sell") == "50"
    page.fill("#mat-sell", "55")
    assert page.input_value("#mat-sell") == "55"


def test_add_material_from_order_page(live_server, signed_in, shop):
    _, page = signed_in("owner")
    page.goto(live_server.url + f"/orders/{shop.pk}/")
    page.evaluate("window.__marker = 1")
    page.locator("[id^='material-add-item-']").first.click()
    page.get_by_role("heading", name="Add material").wait_for()
    assert page.get_by_text("Show all 4 materials").is_visible()
    fill_sheet(page)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=ARTIFACTS / "S04-add-material.png")
    page.emulate_media(color_scheme="dark")
    page.screenshot(path=ARTIFACTS / "S04-add-material-dark.png")
    page.get_by_role("button", name="Add", exact=True).click()
    expect(page.locator(".item-materials").first).to_contain_text("Canvas interlining")
    expect(page.locator(".item-materials").first).to_contain_text("₹55")
    expect(page.locator("#order-invoice")).to_contain_text("₹2,755")
    assert page.evaluate("window.__marker") == 1


def test_add_material_from_item_page(live_server, signed_in, shop):
    _, page = signed_in("owner")
    draft = Order.objects.create(customer=shop.customer)
    item = OrderItem.objects.create(
        order=draft,
        name="Blouse",
        type=Product.CUSTOM,
        price=Decimal(700),
        usual_price=Decimal(700),
    )
    page.goto(live_server.url + f"/orders/drafts/{draft.pk}/items/{item.pk}/")
    page.locator(f"#material-add-item-{item.pk}-materials").click()
    page.get_by_role("heading", name="Add material").wait_for()
    assert page.get_by_role("button", name="Change").count() == 0
    fill_sheet(page)
    page.screenshot(path=ARTIFACTS / "S20-add-material.png")
    page.get_by_role("button", name="Add", exact=True).click()
    page.locator(f"#item-{item.pk}-materials").get_by_text(
        "Canvas interlining"
    ).wait_for()
