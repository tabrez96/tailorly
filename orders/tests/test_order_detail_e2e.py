from pathlib import Path

import pytest

from catalog.models import Product, ProductOption
from customers.models import Customer
from orders.models import Order, OrderItem
from orders.tests.conftest import make_employee, make_order
from orders.tests.test_item_photos_e2e import files
from reports.models import ShopSettings

pytestmark = pytest.mark.e2e

ARTIFACTS = Path(__file__).resolve().parent.parent.parent / "artifacts" / "screens"


@pytest.fixture
def shop(db):
    meera = Customer.objects.create(name="Meera Iyer", phone="9845022110")
    _, ali = make_employee("9000000002", "Ali Khan")
    order = make_order(meera, 1, status="in_progress", price="1800")
    order.assignee = ali
    order.save()
    ShopSettings.objects.create(
        pk=1, running_costs=[{"name": "Rent", "amount": "9500"}]
    )
    OrderItem.objects.filter(order=order).update(
        notes="Princess cut, back hooks, no padding.",
        measurements=[
            {"name": "Bust", "value": "34"},
            {"name": "Waist", "value": "28"},
        ],
    )
    return order


def settle(page):
    page.evaluate("document.fonts.ready.then(() => true)")


def test_record_payment_in_place(live_server, signed_in, shop):
    _, page = signed_in("owner")
    page.goto(live_server.url + f"/orders/{shop.pk}/")
    page.evaluate("window.__marker = 1")
    page.click("#record-payment")
    assert page.input_value("#id_amount") == "1800"
    page.get_by_role("button", name="Save payment").click()
    page.locator(".order-invoice__paid").wait_for()
    assert page.locator("#record-payment").count() == 0
    assert page.evaluate("window.__marker") == 1


def test_customer_name_opens_s07(live_server, signed_in, shop):
    _, page = signed_in("owner")
    page.goto(live_server.url + f"/orders/{shop.pk}/")
    page.click(".order-head__name")
    page.wait_for_url(f"**/customers/{shop.customer.pk}/")
    page.go_back()
    page.wait_for_url(f"**/orders/{shop.pk}/")
    page.get_by_role("heading", name="Order #1").wait_for()


def test_fold_item_card(live_server, signed_in, shop):
    _, page = signed_in("owner")
    page.goto(live_server.url + f"/orders/{shop.pk}/")
    body = page.locator(".item-card >> div[id$='-body']")
    assert body.is_visible()
    page.click(".item-card__toggle")
    body.wait_for(state="hidden")
    assert page.locator(".item-card__summary").is_visible()


def test_screenshots(live_server, signed_in, browser, shop):
    context, page = signed_in("owner")
    url = live_server.url + f"/orders/{shop.pk}/"
    page.goto(url)
    settle(page)
    page.screenshot(path=ARTIFACTS / "S04-order-detail.png", full_page=True)

    dark = browser.new_context(
        viewport={"width": 390, "height": 844}, color_scheme="dark"
    )
    dark.add_cookies(context.cookies())
    dark_page = dark.new_page()
    dark_page.goto(url)
    settle(dark_page)
    dark_page.screenshot(path=ARTIFACTS / "S04-order-detail-dark.png", full_page=True)
    dark.close()

    page.click("#record-payment")
    page.locator("#sheet").get_by_text("Record payment").first.wait_for()
    settle(page)
    page.screenshot(path=ARTIFACTS / "S04-record-payment.png")

    Order.objects.filter(pk=shop.pk).update(paid_by=Order.FREE)
    page.goto(url)
    settle(page)
    page.screenshot(path=ARTIFACTS / "S04-free.png", full_page=True)


def blouse_item(shop):
    blouse = Product.objects.create(
        name="Blouse",
        kind=Product.PRIMARY,
        type=Product.CUSTOM,
        usual_price=1800,
        measurement_fields=["Bust", "Waist"],
    )
    item = shop.items.get()
    item.product = blouse
    item.save()
    return item


def test_edit_measurements_sheet_saves_card_in_place(
    live_server, signed_in, browser, shop
):
    item = blouse_item(shop)
    context, page = signed_in("owner")
    url = live_server.url + f"/orders/{shop.pk}/"
    page.goto(url)
    page.evaluate("window.__marker = 1")
    page.click(f"#measure-{item.pk}")
    page.locator("#sheet").get_by_text("Blouse measurements").first.wait_for()
    settle(page)
    page.screenshot(path=ARTIFACTS / "S04-edit-measurements.png")

    dark = browser.new_context(
        viewport={"width": 390, "height": 844}, color_scheme="dark"
    )
    dark.add_cookies(context.cookies())
    dark_page = dark.new_page()
    dark_page.goto(url)
    dark_page.click(f"#measure-{item.pk}")
    dark_page.locator("#sheet").get_by_text("Blouse measurements").first.wait_for()
    settle(dark_page)
    dark_page.screenshot(path=ARTIFACTS / "S04-edit-measurements-dark.png")
    dark.close()

    page.fill("#ms-1", "36")
    page.get_by_role("button", name="Save", exact=True).click()
    page.locator(f"#item-{item.pk}-body").get_by_text("36").first.wait_for()
    assert page.url == url
    assert page.evaluate("window.__marker") == 1
    page.wait_for_selector(".toast:has-text('Blouse measurements saved')")
    item.refresh_from_db()
    assert item.measurements[0]["value"] == "36"


def test_add_photo_on_card_and_retry(live_server, signed_in, shop):
    item = shop.items.get()
    _, page = signed_in("owner")
    page.goto(live_server.url + f"/orders/{shop.pk}/")
    card = page.locator(f"#item-{item.pk}")
    one, two = files(2)
    card.locator("input[type=file]").set_input_files(one)
    link = card.locator(".photos a")
    link.wait_for()
    page.wait_for_function("document.querySelector('.photos a').getAttribute('href')")
    assert "/orders/photos/" in link.get_attribute("href")

    page.route("**/photos/", lambda route: route.abort(), times=1)
    card.locator("input[type=file]").set_input_files(two)
    retry = card.get_by_role("button", name="Upload failed. Tap to retry.")
    retry.first.wait_for()
    retry.first.click()
    page.wait_for_function("document.querySelectorAll('.photos a[href]').length === 2")
    assert shop.items.get().photos.count() == 2


@pytest.fixture
def finishing_shop(shop, blouse):
    ProductOption.objects.filter(product=blouse).update(
        asked_when=ProductOption.WHEN_DONE
    )
    item = shop.items.get()
    item.product = blouse
    item.options = [{"name": "Lining", "answer": "Yes"}]
    item.save()
    return shop


def test_mark_ready_with_options_in_place(
    live_server, signed_in, browser, finishing_shop
):
    context, page = signed_in("owner")
    url = live_server.url + f"/orders/{finishing_shop.pk}/"
    page.goto(url)
    page.evaluate("window.__marker = 1")
    page.click("#mark-ready")
    qty = page.locator("input[name^=qty_]")
    qty.wait_for()
    qty.fill("0.8")
    assert page.locator("input[name^=cost_]").input_value() == "48"
    assert page.locator("input[name^=sell_]").input_value() == "72"
    settle(page)
    page.screenshot(path=ARTIFACTS / "S04-ready-options.png")

    dark = browser.new_context(
        viewport={"width": 390, "height": 844}, color_scheme="dark"
    )
    dark.add_cookies(context.cookies())
    dark_page = dark.new_page()
    dark_page.goto(url)
    dark_page.click("#mark-ready")
    dark_page.locator("input[name^=qty_]").wait_for()
    settle(dark_page)
    dark_page.screenshot(path=ARTIFACTS / "S04-ready-options-dark.png")
    dark.close()

    page.get_by_role("button", name="Save and mark ready").click()
    page.locator("#mark-delivered").wait_for()
    assert page.locator(".order-head__chips").get_by_text("Ready").count() == 1
    assert page.url == url
    assert page.evaluate("window.__marker") == 1
    assert finishing_shop.items.get().materials.count() == 1


def test_mark_delivered_confirm(live_server, signed_in, shop):
    shop.status = Order.READY
    shop.save()
    _, page = signed_in("owner")
    page.goto(live_server.url + f"/orders/{shop.pk}/")
    page.once("dialog", lambda d: d.accept())
    page.click("#mark-delivered")
    page.locator("#mark-delivered").wait_for(state="detached")
    assert page.locator(".order-head__chips").get_by_text("Delivered").count() == 1
    shop.refresh_from_db()
    assert shop.status == Order.DELIVERED
