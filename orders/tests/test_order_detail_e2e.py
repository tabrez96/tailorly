from pathlib import Path

import pytest

from customers.models import Customer
from orders.models import Order, OrderItem
from orders.tests.conftest import make_employee, make_order

pytestmark = pytest.mark.e2e

ARTIFACTS = Path(__file__).resolve().parent.parent.parent / "artifacts" / "screens"


@pytest.fixture
def shop(db):
    meera = Customer.objects.create(name="Meera Iyer", phone="9845022110")
    _, ali = make_employee("9000000002", "Ali Khan")
    order = make_order(meera, 1, status="in_progress", price="1800")
    order.assignee = ali
    order.save()
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
