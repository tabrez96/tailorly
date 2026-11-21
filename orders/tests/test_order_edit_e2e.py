from pathlib import Path

import pytest

from catalog.models import Product
from customers.models import Customer
from orders.models import OrderItem
from orders.tests.conftest import make_order

pytestmark = pytest.mark.e2e

ARTIFACTS = Path(__file__).resolve().parent.parent.parent / "artifacts" / "screens"


@pytest.fixture
def placed(db):
    from datetime import timedelta

    from django.utils import timezone

    meera = Customer.objects.create(name="Meera Iyer", phone="9845022110")
    order = make_order(
        meera, 1, status="in_progress", due=timezone.localdate() + timedelta(days=6)
    )
    product = Product.objects.create(
        name="Blouse",
        kind=Product.PRIMARY,
        type=Product.CUSTOM,
        usual_price=1800,
        measurement_fields=["Bust"],
    )
    order.items.all().delete()
    OrderItem.from_product(order, product, [], price=1800)
    return order


def test_edit_price_in_place(live_server, signed_in, placed):
    _, page = signed_in("owner")
    page.goto(live_server.url + f"/orders/{placed.pk}/")
    page.evaluate("window.__marker = 1")
    page.get_by_role("link", name="Edit", exact=True).click()
    page.wait_for_url(f"**/orders/{placed.pk}/edit/")
    page.evaluate("document.fonts.ready.then(() => true)")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=ARTIFACTS / "S04-edit-order.png", full_page=True)
    page.locator(".draft-page__open").first.click()
    page.fill("#id_price", "2000")
    page.click("#item-submit")
    page.wait_for_url(f"**/orders/{placed.pk}/edit/")
    page.click("#order-edit-save")
    page.wait_for_url(f"**/orders/{placed.pk}/")
    page.get_by_text("₹2,000").first.wait_for()
    assert page.evaluate("window.__marker") == 1
