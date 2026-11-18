import re
from pathlib import Path

import pytest
from playwright.sync_api import expect

from catalog.models import Product, ProductOption

pytestmark = pytest.mark.e2e

ARTIFACTS = Path(__file__).resolve().parent.parent.parent / "artifacts" / "screens"


def test_products_tab_and_segments_swap_in_place(live_server, signed_in, demo_catalog):
    _, page = signed_in("owner")
    page.goto(live_server.url + "/")
    page.locator(".nav__item", has_text="Products").click()
    page.wait_for_url("**/products/")
    page.evaluate("window.__marker = 1")
    page.get_by_role("link", name="Materials").click()
    page.wait_for_url("**/products/?kind=materials")
    page.get_by_text("Lining, cotton cream").wait_for()
    assert page.evaluate("window.__marker") == 1
    page.wait_for_function("document.activeElement.id === 'seg-materials'")
    assert page.get_attribute("#seg-materials", "aria-current") == "true"


def test_chip_and_search_swap_list_only(live_server, signed_in, demo_catalog):
    _, page = signed_in("owner")
    page.goto(live_server.url + "/products/")
    page.evaluate("window.__marker = 1")
    page.get_by_role("link", name="Ready-made").click()
    page.wait_for_url("**/products/?type=ready_made")
    assert page.locator("#catalog-results .list__row").count() == 2
    assert page.evaluate("window.__marker") == 1
    page.locator("#catalog-q").press_sequentially("silk")
    page.wait_for_url("**q=silk&type=ready_made")
    page.wait_for_function("document.querySelectorAll('.list__row').length === 1")
    assert page.evaluate("document.activeElement.id") == "catalog-q"
    page.locator("#catalog-q").fill("")
    page.locator("#catalog-q").press_sequentially("sherwani")
    page.get_by_text('No product called "sherwani". Add it?').wait_for()
    url = page.url
    page.reload()
    assert page.url == url
    assert page.get_by_text('No product called "sherwani". Add it?').is_visible()


def test_screenshots(live_server, signed_in, browser, demo_catalog):
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    context, page = signed_in("owner")
    page.goto(live_server.url + "/products/")
    page.evaluate("document.fonts.ready.then(() => true)")
    page.screenshot(path=ARTIFACTS / "S15-products.png")
    page.goto(live_server.url + "/products/?kind=materials")
    page.screenshot(path=ARTIFACTS / "S15-products-materials.png")

    cookies = context.cookies()
    dark = browser.new_context(
        viewport={"width": 390, "height": 844}, color_scheme="dark"
    )
    dark.add_cookies(cookies)
    dark_page = dark.new_page()
    dark_page.goto(live_server.url + "/products/")
    dark_page.evaluate("document.fonts.ready.then(() => true)")
    dark_page.screenshot(path=ARTIFACTS / "S15-products-dark.png")
    dark.close()

    ProductOption.objects.all().delete()
    Product.objects.all().delete()
    page.goto(live_server.url + "/products/")
    page.screenshot(path=ARTIFACTS / "S15-products-empty.png")


def test_add_product_from_header_refreshes_in_place(
    live_server, signed_in, demo_catalog
):
    _, page = signed_in("owner")
    page.goto(live_server.url + "/products/")
    page.evaluate("window.__marker = 1")
    page.click("#products-add")
    page.fill("#id_name", "Sherwani")
    page.fill("#id_usual_price", "5200")
    page.locator("#sheet").get_by_text("Ready-made", exact=True).click()
    page.get_by_role("button", name="Save").click()
    page.get_by_text("Sherwani added").wait_for()
    page.wait_for_function("!document.querySelector('#sheet').open")
    page.get_by_text("Sherwani", exact=True).wait_for()
    assert page.evaluate("window.__marker") == 1


def test_hold_url_opens_empty_sheet(live_server, signed_in, demo_catalog):
    _, page = signed_in("owner")
    page.goto(live_server.url + "/products/?add=1")
    page.wait_for_function("document.querySelector('#sheet').open")
    assert page.get_by_text("Add product").is_visible()


def test_validation_focuses_first_error(live_server, signed_in, demo_catalog):
    _, page = signed_in("owner")
    page.goto(live_server.url + "/products/")
    page.click("#products-add")
    page.get_by_role("button", name="Save").click()
    page.get_by_text("Enter a name.").wait_for()
    page.wait_for_function("document.activeElement.id === 'id_name'")
    assert page.evaluate("document.querySelector('#sheet').open")


def test_kind_switch_keeps_name(live_server, signed_in, demo_catalog):
    _, page = signed_in("owner")
    page.goto(live_server.url + "/products/")
    page.click("#products-add")
    page.fill("#id_name", "Lining silk")
    page.get_by_text("Secondary: material").click()
    page.get_by_role("heading", name="Add material").wait_for()
    assert page.input_value("#id_name") == "Lining silk"
    page.wait_for_function("document.activeElement.id === 'id_kind_1'")


def test_header_add_follows_list_kind(live_server, signed_in, demo_catalog):
    _, page = signed_in("owner")
    page.goto(live_server.url + "/products/")
    page.get_by_role("link", name="Materials").click()
    page.wait_for_url("**/products/?kind=materials")
    page.click("#products-add")
    page.get_by_role("heading", name="Add material").wait_for()


def test_remove_after_confirm(live_server, signed_in, demo_catalog):
    _, page = signed_in("owner")
    page.goto(live_server.url + "/products/")
    page.once("dialog", lambda d: d.accept())
    page.click(f"#row-{Product.objects.get(name='Blouse').pk}")
    page.get_by_role("button", name="Remove").click()
    page.get_by_text("Blouse removed").wait_for()
    page.wait_for_function("!document.querySelector('#sheet').open")
    expect(
        page.locator(".prow__title", has_text=re.compile(r"^Blouse$"))
    ).to_have_count(0)


def test_sheet_screenshots(live_server, signed_in, demo_catalog):
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    _, page = signed_in("owner")
    page.goto(live_server.url + "/products/")
    page.click(f"#row-{Product.objects.get(name='Blouse').pk}")
    page.wait_for_function("document.querySelector('#sheet').open")
    page.screenshot(path=ARTIFACTS / "S15-products-edit-product.png")
    page.goto(live_server.url + "/products/?kind=materials")
    page.click(f"#row-{Product.objects.get(name='Lining, cotton cream').pk}")
    page.wait_for_function("document.querySelector('#sheet').open")
    page.screenshot(path=ARTIFACTS / "S15-products-edit-material.png")
