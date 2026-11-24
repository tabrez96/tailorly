from decimal import Decimal
from pathlib import Path

import pytest
from django.utils import timezone

from customers.models import Customer
from orders.tests.conftest import make_order
from reports.models import ShopBill, ShopSettings

pytestmark = pytest.mark.e2e

ARTIFACTS = Path(__file__).resolve().parent.parent.parent / "artifacts" / "screens"

SALES = [
    ("Priya Shetty", [1600, 1600, 1600]),
    ("Meera Iyer", [1650, 1600]),
    ("Anjali Rao", [1550, 1550]),
]


def seed():
    number = 1
    for i, (name, prices) in enumerate(SALES):
        customer = Customer.objects.create(name=name, phone=f"90000001{i:02d}")
        for price in prices:
            make_order(customer, number, price=str(Decimal(price)))
            number += 1
    free = Customer.objects.create(name="Farhan Sheikh", phone="9000000199")
    make_order(free, number, free=True, price="1200")
    ShopBill.objects.create(
        name="Rent", amount=Decimal(7000), date=timezone.localdate()
    )


def settle(page):
    page.evaluate("document.fonts.ready.then(() => true)")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)


def test_profit_report_flow(live_server, signed_in):
    seed()
    _, page = signed_in("owner")
    page.goto(live_server.url + "/reports/sales/")
    page.locator("#sales-hero").wait_for()
    page.evaluate("window.__marker = 1")
    page.locator("#report-profit_report").click()
    page.wait_for_url("**/reports/profit/**")
    page.locator("#shop-profit").wait_for()
    assert page.evaluate("window.__marker") == 1  # no full reload
    settle(page)
    page.screenshot(path=ARTIFACTS / "S11-profit.png", full_page=True)
    page.locator("#profit-rows a").first.click()
    page.wait_for_url("**/customers/*/")
    page.go_back()
    page.locator("#shop-profit").wait_for()
    page.locator("#by-sale").click()
    page.wait_for_url("**by=sale**")
    page.locator("#profit-rows a").first.click()
    page.wait_for_url("**/orders/*/")
    page.go_back()
    page.locator("#free-work").click()
    page.wait_for_url("**/orders/?show=free**")


def test_profit_report_dark(live_server, signed_in):
    seed()
    _, page = signed_in("owner")
    page.emulate_media(color_scheme="dark")
    page.goto(live_server.url + "/reports/profit/")
    page.locator("#shop-profit").wait_for()
    settle(page)
    page.screenshot(path=ARTIFACTS / "S11-profit-dark.png", full_page=True)


def test_add_bill_sheet(live_server, signed_in):
    _, page = signed_in("owner")
    page.goto(live_server.url + "/reports/profit/")
    page.locator("#add-bill").click()
    page.get_by_role("button", name="Save bill").click()
    page.get_by_text("2 things need fixing before you can save this bill.").wait_for()
    page.get_by_label("Name").fill("Electricity")
    page.get_by_label("Amount (₹)").fill("1800")
    page.get_by_role("button", name="Save bill").click()
    page.locator("#shop-bills").get_by_text("Electricity").wait_for()
    assert "₹1,800" in page.locator("#shop-bills").inner_text()
    assert "−₹1,800" in page.locator("#shop-profit").inner_text()


def seed_garments():
    seed()
    customer = Customer.objects.get(name="Priya Shetty")
    ready = make_order(customer, 20, price="799")
    ready.items.update(name="Kurta", type="ready_made")
    ShopSettings.objects.create(
        pk=1, running_costs=[{"name": "Rent", "amount": "9500"}]
    )


def test_profit_by_garment(live_server, signed_in):
    seed_garments()
    _, page = signed_in("owner")
    page.goto(live_server.url + "/reports/profit/")
    page.locator("#by-garment").click()
    page.locator("#garment-rows").wait_for()
    settle(page)
    page.screenshot(path=ARTIFACTS / "S11-by-garment.png", full_page=True)
    page.locator("#running-edit").click()
    page.locator("#cost-1").wait_for()
    settle(page)
    page.screenshot(path=ARTIFACTS / "S11-running-costs-sheet.png")
    page.locator("#cost-1").fill("20800")
    page.get_by_role("button", name="Save", exact=True).click()
    page.get_by_text("₹100 an hour of work").wait_for()
    assert "by=garment" in page.url


def test_profit_by_garment_dark(live_server, signed_in):
    seed_garments()
    _, page = signed_in("owner")
    page.emulate_media(color_scheme="dark")
    page.goto(live_server.url + "/reports/profit/?by=garment")
    page.locator("#garment-rows").wait_for()
    settle(page)
    page.screenshot(path=ARTIFACTS / "S11-by-garment-dark.png", full_page=True)
