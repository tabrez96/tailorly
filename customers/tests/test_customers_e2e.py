from pathlib import Path

import pytest

from customers.models import Customer

pytestmark = pytest.mark.e2e

ARTIFACTS = Path(__file__).resolve().parent.parent.parent / "artifacts" / "screens"


@pytest.fixture
def people(db):
    Customer.objects.create(
        name="Meera Iyer", phone="9845022110", notes="Loose sleeves."
    )
    Customer.objects.create(name="Arjun Pillai", phone="9900177345")
    Customer.objects.create(name="Kavya Nair", phone="9741158830")


def test_search_swaps_list_only(live_server, signed_in, people):
    _, page = signed_in("owner")
    page.goto(live_server.url + "/customers/")
    page.evaluate("window.__marker = 1")
    page.locator("#customers-q").press_sequentially("mee")
    page.wait_for_url("**/customers/?q=mee")
    page.wait_for_function("document.querySelectorAll('.list__row').length === 1")
    assert page.evaluate("window.__marker") == 1
    assert page.evaluate("document.activeElement.id") == "customers-q"
    page.locator("#customers-q").fill("")
    page.locator("#customers-q").press_sequentially("98410")
    page.wait_for_function("document.querySelectorAll('.list__row').length === 0")
    page.locator("#customers-q").fill("")
    page.locator("#customers-q").press_sequentially("77345")
    page.wait_for_function("document.querySelectorAll('.list__row').length === 1")


def test_no_match_offers_add_prefilled(live_server, signed_in, people):
    _, page = signed_in("owner")
    page.goto(live_server.url + "/customers/")
    page.locator("#customers-q").press_sequentially("Zed")
    page.get_by_text('No customer matches "Zed".').wait_for()
    page.click("#search-add")
    page.wait_for_function("document.querySelector('#sheet').open")
    assert page.input_value("#id_name") == "Zed"


def test_add_customer_lands_on_detail(live_server, signed_in, people):
    _, page = signed_in("owner")
    page.goto(live_server.url + "/customers/")
    page.evaluate("window.__marker = 1")
    page.click("#customers-add")
    page.fill("#id_name", "Priya Shetty")
    page.fill("#id_phone", "+91 90080 66112")
    page.get_by_role("button", name="Save").click()
    page.get_by_text("Priya Shetty added").wait_for()
    page.wait_for_url("**/customers/*/")
    page.get_by_role("heading", name="Priya Shetty").wait_for()
    assert page.get_by_text("90080 66112").is_visible()
    assert page.evaluate("window.__marker") == 1


def test_hold_tab_opens_add_sheet(live_server, signed_in, people):
    _, page = signed_in("owner")
    page.goto(live_server.url + "/")
    box = page.locator(".nav__item", has_text="Customers").bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.wait_for_timeout(600)
    page.mouse.up()
    page.wait_for_url("**/customers/?add=1")
    page.wait_for_function("document.querySelector('#sheet').open")
    assert page.get_by_role("heading", name="Add customer").is_visible()


def test_edit_changes_title_and_new_order_link(live_server, signed_in, people):
    _, page = signed_in("owner")
    c = Customer.objects.get(name="Meera Iyer")
    page.goto(live_server.url + f"/customers/{c.pk}/")
    assert page.get_attribute("#new-order", "href") == f"/orders/new/?customer={c.pk}"
    page.click("#customer-edit")
    page.fill("#id_name", "Meera Rao")
    page.get_by_role("button", name="Save").click()
    page.get_by_text("Meera Rao saved").wait_for()
    page.get_by_role("heading", name="Meera Rao").wait_for()
    page.get_by_text("+ New order for Meera").wait_for()


def test_screenshots(live_server, signed_in, browser, people):
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    context, page = signed_in("owner")
    meera = Customer.objects.get(name="Meera Iyer")
    page.goto(live_server.url + "/customers/")
    page.evaluate("document.fonts.ready.then(() => true)")
    page.screenshot(path=ARTIFACTS / "S06-customers.png")
    page.goto(live_server.url + f"/customers/{meera.pk}/")
    page.evaluate("document.fonts.ready.then(() => true)")
    page.screenshot(path=ARTIFACTS / "S07-customer.png")

    dark = browser.new_context(
        viewport={"width": 390, "height": 844}, color_scheme="dark"
    )
    dark.add_cookies(context.cookies())
    dark_page = dark.new_page()
    dark_page.goto(live_server.url + "/customers/")
    dark_page.evaluate("document.fonts.ready.then(() => true)")
    dark_page.screenshot(path=ARTIFACTS / "S06-customers-dark.png")
    dark_page.goto(live_server.url + f"/customers/{meera.pk}/")
    dark_page.evaluate("document.fonts.ready.then(() => true)")
    dark_page.screenshot(path=ARTIFACTS / "S07-customer-dark.png")
    dark.close()

    Customer.objects.all().delete()
    page.goto(live_server.url + "/customers/")
    page.evaluate("document.fonts.ready.then(() => true)")
    page.screenshot(path=ARTIFACTS / "S06-customers-empty.png")
