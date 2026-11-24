from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import expect

from catalog.models import Product, ProductOption
from customers.models import Customer
from orders.models import MaterialLine, OrderItem
from orders.photos import add_photo
from orders.tests.conftest import make_employee, make_order

pytestmark = pytest.mark.e2e

ARTIFACTS = Path(__file__).resolve().parent.parent.parent / "artifacts" / "screens"


def png():
    buffer = BytesIO()
    Image.new("RGB", (400, 300), "teal").save(buffer, "PNG")
    return SimpleUploadedFile("p.png", buffer.getvalue(), "image/png")


def click(page, locator, step):
    """Click; on a timeout, say which step failed and what is on top of the target."""
    try:
        locator.click(timeout=10_000)
    except PlaywrightTimeoutError:
        box = locator.bounding_box()
        top = "no box"
        if box:
            x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
            top = page.evaluate(
                "([x, y]) => { const e = document.elementFromPoint(x, y);"
                " return e ? e.outerHTML.slice(0, 160) : 'nothing (off screen)'; }",
                [x, y],
            )
        target = locator.evaluate("e => e.outerHTML.slice(0, 160)")
        raise AssertionError(
            f"{step}: click timed out. box={box} target={target} on top={top}"
        ) from None


@pytest.fixture
def shop(db, media):
    meera = Customer.objects.create(name="Meera Iyer", phone="9845022110")
    Product.objects.create(
        name="Canvas interlining",
        kind=Product.SECONDARY,
        unit="m",
        cost_price=Decimal(80),
        selling_price=Decimal(100),
        billed_by_default=True,
    )
    blouse = Product.objects.create(
        name="Blouse",
        kind=Product.PRIMARY,
        type=Product.CUSTOM,
        usual_price=Decimal(1800),
        measurement_fields=["Bust", "Waist", "Shoulder"],
    )
    ProductOption.objects.create(
        product=blouse, name="Lining", asked_when=ProductOption.WHEN_DONE
    )
    _, ali = make_employee("9000000002", "ali")
    order = make_order(meera, 1042, status="in_progress", price="1800")
    order.assignee, order.due_date = ali, date(2026, 11, 13)
    order.save()
    item = order.items.get()
    item.product = blouse
    item.options = [
        {"name": "Lining", "answer": "Yes"},
        {"name": "Sleeve style", "answer": "Elbow"},
        {"name": "Padding", "answer": "No"},
    ]
    item.measurements = [
        {"name": "Bust", "value": "34"},
        {"name": "Waist", "value": "28"},
        {"name": "Shoulder", "value": "14"},
    ]
    item.estimate_minutes = 180
    item.save()
    add_photo(item, png())
    add_photo(item, png())
    OrderItem.objects.create(
        order=order,
        name="Skirt",
        type=Product.CUSTOM,
        price=Decimal(900),
        usual_price=Decimal(900),
    )
    return order


def item_url(live_server, item):
    return live_server.url + f"/orders/{item.order_id}/items/{item.pk}/"


def test_chevron_opens_item_detail_in_place(live_server, signed_in, shop):
    _, page = signed_in("owner")
    item = shop.items.order_by("pk").first()
    page.goto(live_server.url + f"/orders/{shop.pk}/")
    page.evaluate("window.__marker = 1")
    page.locator(f"#item-{item.pk} .item-card__chevron").click()
    page.get_by_role("heading", name="Blouse", exact=True).wait_for()
    assert page.url.endswith(f"/items/{item.pk}/")
    assert page.evaluate("window.__marker") == 1
    expect(page.locator(".item-detail__badge")).to_have_text("1/2")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=ARTIFACTS / "S19.png")
    page.emulate_media(color_scheme="dark")
    page.screenshot(path=ARTIFACTS / "S19-dark.png")


def test_item_detail_direct_load_and_back(live_server, signed_in, shop):
    _, page = signed_in("owner")
    item = shop.items.order_by("pk").first()
    page.goto(item_url(live_server, item))
    expect(page.get_by_role("heading", name="Blouse", exact=True)).to_be_visible()
    page.get_by_role("link", name="Back").click()
    expect(page).to_have_url(live_server.url + f"/orders/{shop.pk}/")
    expect(page.locator(f"#item-{item.pk}")).to_be_visible()


def test_ready_made_state(live_server, signed_in, db):
    meera = Customer.objects.create(name="Meera Iyer", phone="9845022110")
    order = make_order(meera, 1043, status="open", price="450")
    item = order.items.get()
    item.name, item.type = "Cotton dupatta", Product.READY_MADE
    item.save()
    MaterialLine.objects.create(
        item=item,
        name="Cotton dupatta",
        unit="pc",
        quantity=Decimal(1),
        cost_price=Decimal(280),
        selling_price=Decimal(0),
    )
    _, page = signed_in("owner")
    page.goto(item_url(live_server, item))
    expect(page.locator("#item-costs")).to_contain_text("₹170")
    expect(page.get_by_role("heading", name="Measurements")).to_have_count(0)
    expect(page.get_by_role("heading", name="Options")).to_have_count(0)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=ARTIFACTS / "S19-ready-made.png")


def test_add_material_from_item_detail_updates_gain(live_server, signed_in, shop):
    _, page = signed_in("owner")
    item = shop.items.order_by("pk").first()
    page.goto(item_url(live_server, item))
    page.evaluate("window.__marker = 1")
    expect(page.locator("#item-costs")).to_contain_text("Gain on this item")
    before = page.locator("#item-costs .cost-card__gain").inner_text()
    add_button = page.locator("#item-add-material")
    expect(add_button).to_be_visible()
    click(page, add_button, "bottom-bar + Add material")
    page.get_by_role("heading", name="Add material").wait_for()
    assert page.get_by_role("button", name="Change").count() == 0
    label = page.locator("label", has_text="Canvas interlining")
    expect(label).to_be_visible()
    click(page, label, "Canvas interlining label")
    expect(page.get_by_label("Canvas interlining")).to_be_checked()
    page.fill("#mat-qty", "2")
    submit = page.get_by_role("button", name="Add", exact=True)
    expect(submit).to_be_visible()
    click(page, submit, "sheet Add submit")
    expect(page.locator(".item-materials")).to_contain_text("Canvas interlining")
    expect(page.locator("#item-costs .cost-card__gain")).not_to_have_text(before)
    assert page.url == item_url(live_server, item)
    assert page.evaluate("window.__marker") == 1
