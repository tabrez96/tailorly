from datetime import date, timedelta
from pathlib import Path

import pytest

from catalog.models import Product
from customers.models import Customer
from orders.models import Order, OrderItem
from orders.tests.conftest import make_employee

pytestmark = pytest.mark.e2e

ARTIFACTS = Path(__file__).resolve().parent.parent.parent / "artifacts" / "screens"


@pytest.fixture
def shop(db, blouse, kurta):
    Customer.objects.create(name="Asha Rao", phone="9000000011")
    Customer.objects.create(name="Meera Iyer", phone="9845022110")


def search_and_choose(page, text, name):
    page.fill("#draft-customer-q", text)
    page.locator("[id^=choose-]", has_text=name).click()
    page.locator(".draft-customer", has_text=name).wait_for()


def test_hold_orders_tab_opens_new_draft(live_server, signed_in, shop):
    _, page = signed_in("owner")
    page.goto(live_server.url + "/")
    page.evaluate("window.__marker = 1")
    box = page.locator(".nav__item", has_text="Orders").bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.wait_for_timeout(600)
    page.mouse.up()
    page.wait_for_url("**/orders/drafts/*/")
    page.get_by_role("heading", name="New order").wait_for()
    assert page.evaluate("window.__marker") == 1
    assert Order.objects.get().customer is None


def test_search_choose_and_change(live_server, signed_in, shop):
    _, page = signed_in("owner")
    page.goto(live_server.url + "/orders/new/")
    page.wait_for_url("**/orders/drafts/*/")
    search_and_choose(page, "asha", "Asha Rao")
    assert Order.objects.get().customer.name == "Asha Rao"
    page.get_by_role("button", name="Change").click()
    search_and_choose(page, "98450", "Meera Iyer")
    assert Order.objects.get().customer.name == "Meera Iyer"


def test_new_customer_sheet_chooses_customer(live_server, signed_in, shop):
    _, page = signed_in("owner")
    page.goto(live_server.url + "/orders/new/")
    page.wait_for_url("**/orders/drafts/*/")
    page.click("#new-customer")
    page.fill("#id_name", "Priya Nair")
    page.fill("#id_phone", "9876543210")
    page.get_by_role("button", name="Save").click()
    page.locator(".draft-customer", has_text="Priya Nair").wait_for()
    assert Order.objects.get().customer.name == "Priya Nair"


def test_s07_new_order_has_customer_chosen(live_server, signed_in, shop):
    _, page = signed_in("owner")
    asha = Customer.objects.get(name="Asha Rao")
    page.goto(live_server.url + f"/customers/{asha.pk}/")
    page.click("#new-order")
    page.wait_for_url("**/orders/drafts/*/")
    page.locator(".draft-customer", has_text="Asha Rao").wait_for()


def two_blouse_draft():
    order = Order.objects.create(customer=Customer.objects.get(name="Meera Iyer"))
    blouse = Product.objects.get(name="Blouse")
    for _ in range(2):
        OrderItem.from_product(order, blouse)
    return order


def test_create_order_lands_on_order_page(live_server, signed_in, shop):
    _, ali = make_employee("9000000002", "Ali Khan")
    order = two_blouse_draft()
    _, page = signed_in("owner")
    page.goto(live_server.url + f"/orders/drafts/{order.pk}/")
    page.evaluate("window.__marker = 1")
    page.fill("#id_due_date", (date.today() + timedelta(days=7)).isoformat())
    page.fill("#id_advance", "1000")
    page.get_by_role("button", name="Create order").click()
    page.wait_for_url(f"**/orders/{order.pk}/")
    assert page.evaluate("window.__marker") == 1
    page.get_by_text("Balance").wait_for()
    body = page.locator("#page").inner_text()
    assert body.count("Blouse") == 2
    assert "₹1,000" in body
    assert "₹1,400" in body
    assert Order.objects.get(pk=order.pk).assignee == ali


def test_errors_focus_first_field(live_server, signed_in, shop):
    _, page = signed_in("owner")
    page.goto(live_server.url + "/orders/new/")
    page.wait_for_url("**/orders/drafts/*/")
    page.get_by_role("button", name="Create order").click()
    page.get_by_role("alert").wait_for()
    assert page.evaluate("document.activeElement.id") == "draft-customer-q"
    assert "Add at least one item." in page.locator("#draft").inner_text()


def test_free_toggle(live_server, signed_in, shop):
    order = two_blouse_draft()
    _, page = signed_in("owner")
    page.goto(live_server.url + f"/orders/drafts/{order.pk}/")
    page.get_by_text("Free: self or family").click()
    page.get_by_role("button", name="Create free order").wait_for()
    assert page.locator(".draft-bar").inner_text().startswith("Free, not charged")
    page.locator("#id_advance").wait_for(state="hidden")
    page.wait_for_function("true")
    for _ in range(20):
        if Order.objects.get(pk=order.pk).paid_by == Order.FREE:
            break
        page.wait_for_timeout(100)
    assert Order.objects.get(pk=order.pk).paid_by == Order.FREE


def test_screenshots(live_server, signed_in, browser, shop):
    context, page = signed_in("owner")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    order = Order.objects.create(customer=Customer.objects.get(name="Meera Iyer"))
    for name in ("Blouse", "Cotton kurta"):
        OrderItem.from_product(order, Product.objects.get(name=name))
    url = live_server.url + f"/orders/drafts/{order.pk}/"
    page.goto(url)
    page.evaluate("document.fonts.ready.then(() => true)")
    page.screenshot(path=ARTIFACTS / "s05-customer-light.png", full_page=True)
    dark = browser.new_context(
        viewport={"width": 390, "height": 844}, color_scheme="dark"
    )
    dark.add_cookies(context.cookies())
    dark_page = dark.new_page()
    dark_page.goto(url)
    dark_page.evaluate("document.fonts.ready.then(() => true)")
    dark_page.screenshot(path=ARTIFACTS / "s05-customer-dark.png", full_page=True)
    make_employee("9000000002", "Ali Khan")
    page.goto(url)
    page.fill("#id_due_date", (date.today() + timedelta(days=7)).isoformat())
    page.fill("#id_advance", "1000")
    page.screenshot(path=ARTIFACTS / "s05-making-light.png", full_page=True)
    dark_page.goto(url)
    dark_page.fill("#id_due_date", (date.today() + timedelta(days=7)).isoformat())
    dark_page.screenshot(path=ARTIFACTS / "s05-making-dark.png", full_page=True)
    dark.close()
    page.get_by_text("Free: self or family").click()
    page.screenshot(path=ARTIFACTS / "s05-free-light.png", full_page=True)
    empty = Order.objects.create()
    page.goto(live_server.url + f"/orders/drafts/{empty.pk}/")
    page.get_by_role("button", name="Create order").click()
    page.get_by_role("alert").wait_for()
    page.screenshot(path=ARTIFACTS / "s05-error-light.png", full_page=True)
