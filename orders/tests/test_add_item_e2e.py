from pathlib import Path

import pytest

from catalog.models import Product, ProductOption
from customers.models import Customer, MeasurementSet
from orders.models import Order, OrderItem

pytestmark = pytest.mark.e2e

ARTIFACTS = Path(__file__).resolve().parent.parent.parent / "artifacts" / "screens"


@pytest.fixture
def shop(db, blouse, kurta):
    customer = Customer.objects.create(name="Asha Rao", phone="9000000011")
    ProductOption.objects.create(
        product=blouse, name="Sleeve", answer="choice", choices=["Short", "Elbow"]
    )
    MeasurementSet.objects.create(
        customer=customer,
        product=blouse,
        values=[{"name": "Bust", "value": "34"}, {"name": "Waist", "value": "28"}],
    )
    return customer


def open_add_item(live_server, page, customer):
    page.goto(live_server.url + f"/customers/{customer.pk}/")
    page.click("#new-order")
    page.wait_for_url("**/orders/drafts/*/")
    page.click("#add-item")
    page.wait_for_url("**/items/new/")


def test_add_item_flow(live_server, signed_in, shop):
    _, page = signed_in("owner")
    open_add_item(live_server, page, shop)
    page.evaluate("window.__noReload = 1")
    page.locator("label.row-text__label", has_text="Blouse").click()
    page.wait_for_function("document.querySelector('#id_price').value === '1200'")
    assert page.get_by_text("Uses Lining, cotton.").is_visible()
    assert page.evaluate("window.__noReload") == 1
    page.fill("#id_price", "1500")
    assert page.locator(".item-bar__total").inner_text() == "₹1,500"
    page.get_by_role("button", name="Add to order").click()
    page.wait_for_url("**/orders/drafts/*/")
    page.get_by_text("1 item").wait_for()
    assert "₹1,500" in page.locator(".draft-page .list").inner_text()
    page.reload()
    assert "Blouse" in page.locator(".draft-page .list").inner_text()
    assert Order.objects.get().items.count() == 1


def test_back_asks_when_changed(live_server, signed_in, shop):
    _, page = signed_in("owner")
    open_add_item(live_server, page, shop)
    page.click(".header__back")
    page.wait_for_url("**/orders/drafts/*/")
    page.click("#add-item")
    page.wait_for_url("**/items/new/")
    page.fill("#id_notes", "Hooks")
    page.once("dialog", lambda d: d.dismiss())
    page.click(".header__back")
    page.wait_for_timeout(300)
    assert page.url.endswith("/items/new/")
    page.once("dialog", lambda d: d.accept())
    page.click(".header__back")
    page.wait_for_url("**/orders/drafts/*/")


def test_save_without_product_focuses_it(live_server, signed_in, shop):
    _, page = signed_in("owner")
    open_add_item(live_server, page, shop)
    page.fill("#id_price", "100")
    page.get_by_role("button", name="Add to order").click()
    page.get_by_text("Choose a product.").wait_for()
    page.wait_for_function(
        "document.activeElement && document.activeElement.name === 'product'"
    )


def test_screenshots(live_server, signed_in, browser, shop):
    context, page = signed_in("owner")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    order = Order.objects.create(customer=shop)
    url = live_server.url + f"/orders/drafts/{order.pk}/items/new/"
    blouse = Product.objects.get(name="Blouse")
    kurta = Product.objects.get(name="Cotton kurta")

    def shot(target, name, goto):
        target.goto(goto)
        target.evaluate("document.fonts.ready.then(() => true)")
        target.screenshot(path=ARTIFACTS / name, full_page=True)

    shot(page, "S20-add-item.png", f"{url}?product={blouse.pk}")
    shot(page, "S20-ready-made.png", f"{url}?type=ready_made&product={kurta.pk}")
    dark = browser.new_context(
        viewport={"width": 390, "height": 844}, color_scheme="dark"
    )
    dark.add_cookies(context.cookies())
    shot(dark.new_page(), "S20-dark.png", f"{url}?product={blouse.pk}")
    dark.close()
    OrderItem.from_product(order, blouse)
    shot(page, "S05-draft-items.png", live_server.url + f"/orders/drafts/{order.pk}/")
    page.goto(f"{url}?product={blouse.pk}")
    page.fill("#id_price", "")
    page.get_by_role("button", name="Add to order").click()
    page.get_by_text("Enter a price. The usual price").wait_for()
    page.screenshot(path=ARTIFACTS / "S20-error.png", full_page=True)
    Product.objects.filter(type=Product.READY_MADE).delete()
    shot(page, "S20-no-products.png", f"{url}?type=ready_made")
