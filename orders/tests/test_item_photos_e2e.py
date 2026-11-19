from io import BytesIO

import pytest
from PIL import Image

from catalog.models import Product
from orders.models import Order, OrderItem
from orders.photos import add_photo
from orders.tests.test_add_item_e2e import ARTIFACTS, open_add_item, shop  # noqa: F401
from orders.tests.test_photos import png

pytestmark = pytest.mark.e2e


def files(n):
    out = []
    for i in range(n):
        buffer = BytesIO()
        Image.new("RGB", (60, 60), (40 * i, 120, 160)).save(buffer, "PNG")
        out.append(
            {"name": f"p{i}.png", "mimeType": "image/png", "buffer": buffer.getvalue()}
        )
    return out


def pick_blouse(page):
    page.locator("label.row-text__label", has_text="Blouse").click()
    page.wait_for_function("document.querySelector('#id_price').value === '1200'")


def test_add_three_photos_then_no_more(live_server, signed_in, shop):  # noqa: F811
    _, page = signed_in("owner")
    open_add_item(live_server, page, shop)
    pick_blouse(page)
    page.set_input_files("input[type=file]", files(3))
    tiles = page.locator(".photo-tile img")
    tiles.nth(2).wait_for()
    assert [tiles.nth(i).get_attribute("alt") for i in range(3)] == [
        f"Blouse, photo {n} of 3" for n in (1, 2, 3)
    ]
    page.wait_for_function(
        "[...document.querySelectorAll('input[name=photo]')]"
        ".filter((i) => i.value && !i.disabled).length === 3"
    )
    assert not page.locator("#photo-add").is_visible()
    card = page.locator(".product-pick")
    assert card.locator("img").get_attribute("src")
    assert card.locator(".thumb__badge").inner_text() == "1/3"
    page.get_by_role("button", name="Add to order").click()
    page.wait_for_url("**/orders/drafts/*/")
    page.locator(".thumb--sm img").wait_for()
    assert Order.objects.get().items.get().photos.count() == 3


def test_failed_upload_retry(live_server, signed_in, shop):  # noqa: F811
    _, page = signed_in("owner")
    open_add_item(live_server, page, shop)
    pick_blouse(page)
    calls = []

    def handle(route):
        calls.append(1)
        route.abort() if len(calls) == 1 else route.continue_()

    page.route("**/photos/", handle)
    page.set_input_files("input[type=file]", files(1))
    retry = page.get_by_role("button", name="Upload failed. Tap to retry.")
    retry.wait_for()
    retry.click()
    retry.wait_for(state="hidden")
    page.wait_for_function("document.querySelector('input[name=photo]').value")
    assert len(calls) == 2


def test_photos_on_edit(live_server, signed_in, shop, media):  # noqa: F811
    _, page = signed_in("owner")
    order = Order.objects.create(customer=shop)
    item = OrderItem.from_product(order, Product.objects.get(name="Blouse"))
    add_photo(item, png(80, 80))
    page.goto(f"{live_server.url}/orders/drafts/{order.pk}/items/{item.pk}/")
    page.locator(".photo-tile img").wait_for()
    page.set_input_files("input[type=file]", files(1))
    page.locator(".photo-tile img").nth(1).wait_for()
    page.wait_for_function(
        "document.querySelectorAll('input[name=photo]:not(:disabled)').length === 1"
    )
    page.get_by_role("button", name="Save item").click()
    page.wait_for_url(f"**/orders/drafts/{order.pk}/")
    assert item.photos.count() == 2


def test_photo_screenshots(live_server, signed_in, browser, shop, media):  # noqa: F811
    context, page = signed_in("owner")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    order = Order.objects.create(customer=shop)
    item = OrderItem.from_product(order, Product.objects.get(name="Blouse"))
    for _ in range(2):
        add_photo(item, png(120, 120))
    url = f"{live_server.url}/orders/drafts/{order.pk}/items/{item.pk}/"
    page.goto(url)
    page.locator(".photo-tile img").nth(1).wait_for()
    page.evaluate("document.fonts.ready.then(() => true)")
    page.screenshot(path=ARTIFACTS / "S20-photos.png", full_page=True)
    dark = browser.new_context(
        viewport={"width": 390, "height": 844}, color_scheme="dark"
    )
    dark.add_cookies(context.cookies())
    dpage = dark.new_page()
    dpage.goto(url)
    dpage.locator(".photo-tile img").nth(1).wait_for()
    dpage.evaluate("document.fonts.ready.then(() => true)")
    dpage.screenshot(path=ARTIFACTS / "S20-photos-dark.png", full_page=True)
    dark.close()
