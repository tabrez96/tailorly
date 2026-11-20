from datetime import timedelta
from pathlib import Path

import pytest
from django.utils import timezone

from customers.models import Customer
from orders.models import Order
from orders.tests.conftest import make_order

pytestmark = pytest.mark.e2e

ARTIFACTS = Path(__file__).resolve().parent.parent.parent / "artifacts" / "screens"


@pytest.fixture
def shop(db):
    asha = Customer.objects.create(name="Asha Rao", phone="9000000011")
    meera = Customer.objects.create(name="Meera Iyer", phone="9845022110")
    today = timezone.localdate()
    make_order(asha, 1, due=today - timedelta(days=1))
    make_order(meera, 2, status="ready", due=today)
    make_order(meera, 3, status="delivered")
    make_order(asha, 4, free=True, due=today + timedelta(days=4))
    return asha


def rows(page):
    return page.locator(".orow").count()


def test_chip_and_search_swap_list_in_place(live_server, signed_in, shop):
    _, page = signed_in("owner")
    page.goto(live_server.url + "/orders/")
    page.evaluate("window.__marker = 1")
    page.click("#chip-ready")
    page.wait_for_url("**/orders/?show=ready")
    page.wait_for_function("document.querySelectorAll('.orow').length === 1")
    assert page.evaluate("window.__marker") == 1
    page.click("#chip-all")
    page.wait_for_function("document.querySelectorAll('.orow').length === 4")
    page.locator("#orders-q").press_sequentially("meera")
    page.wait_for_function("document.querySelectorAll('.orow').length === 2")
    page.wait_for_url("**/orders/?q=meera&show=all")
    assert page.evaluate("window.__marker") == 1
    page.reload()
    assert rows(page) == 2
    assert page.input_value("#orders-q") == "meera"
    assert page.locator("#chip-all").get_attribute("aria-current") == "true"


def test_row_opens_order_detail(live_server, signed_in, shop):
    _, page = signed_in("owner")
    page.goto(live_server.url + "/orders/")
    page.evaluate("window.__marker = 1")
    page.click(f"#order-{Order.objects.get(number=1).pk}")
    page.get_by_role("heading", name="Order #1").wait_for()
    assert page.evaluate("window.__marker") == 1


def test_screenshots(live_server, signed_in, browser, shop):
    context, page = signed_in("owner")
    page.goto(live_server.url + "/orders/")
    page.evaluate("document.fonts.ready.then(() => true)")
    page.screenshot(path=ARTIFACTS / "S03-orders.png")
    page.goto(live_server.url + f"/customers/{shop.pk}/")
    page.evaluate("document.fonts.ready.then(() => true)")
    page.screenshot(path=ARTIFACTS / "S07-customer-orders.png", full_page=True)

    dark = browser.new_context(
        viewport={"width": 390, "height": 844}, color_scheme="dark"
    )
    dark.add_cookies(context.cookies())
    dark_page = dark.new_page()
    dark_page.goto(live_server.url + "/orders/")
    dark_page.evaluate("document.fonts.ready.then(() => true)")
    dark_page.screenshot(path=ARTIFACTS / "S03-orders-dark.png")
    dark.close()

    Order.objects.all().delete()
    page.goto(live_server.url + "/orders/")
    page.evaluate("document.fonts.ready.then(() => true)")
    page.screenshot(path=ARTIFACTS / "S03-orders-empty.png")
