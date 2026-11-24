from decimal import Decimal
from pathlib import Path

import pytest
from django.utils import timezone

from customers.models import Customer
from orders.tests.conftest import make_order

pytestmark = pytest.mark.e2e

ARTIFACTS = Path(__file__).resolve().parent.parent.parent / "artifacts" / "screens"

SALES = [
    ("Priya Shetty", [1600, 1600, 1600]),
    ("Meera Iyer", [1650, 1600]),
    ("Anjali Rao", [1550, 1550]),
    ("Farhan Sheikh", [2200]),
    ("Arjun Pillai", [1000, 950]),
]


def seed():
    number = 1
    for i, (name, prices) in enumerate(SALES):
        customer = Customer.objects.create(name=name, phone=f"90000001{i:02d}")
        for price in prices:
            make_order(customer, number, price=str(Decimal(price)))
            number += 1


def settle(page):
    page.evaluate("document.fonts.ready.then(() => true)")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)


def test_sales_report_flow(live_server, signed_in):
    seed()
    _, page = signed_in("owner")
    page.goto(live_server.url + "/reports/sales/")
    page.locator("#sales-hero").wait_for()
    settle(page)
    page.screenshot(path=ARTIFACTS / "S11-sales.png", full_page=True)
    page.locator("#sales-rows a").first.click()
    page.wait_for_url("**/customers/*/")
    page.go_back()
    page.locator("#sales-hero").wait_for()
    page.locator("#report-production_report").click()
    page.wait_for_url("**/production/report/**")
    assert "period=month" in page.url
    page.locator("#report-sales_report").wait_for()
    page.locator("#report-sales_report").click()
    page.wait_for_url("**/reports/sales/**")
    page.locator("#period").select_option("last_month")
    page.wait_for_url("**period=last_month**")
    page.locator("#report-production_report").click()
    page.wait_for_url("**/production/report/**")
    assert "period=last_month" in page.url
    page.locator("#report-sales_report").click()
    page.wait_for_url("**/reports/sales/**")
    page.locator("#period").select_option("month")
    page.wait_for_url("**period=month**")
    page.locator("#group-garment").click()
    page.wait_for_url("**group=garment**")


def test_sales_report_dark(live_server, signed_in):
    seed()
    _, page = signed_in("owner")
    page.emulate_media(color_scheme="dark")
    page.goto(live_server.url + "/reports/sales/")
    page.locator("#sales-hero").wait_for()
    settle(page)
    page.screenshot(path=ARTIFACTS / "S11-sales-dark.png", full_page=True)


def test_sales_report_empty(live_server, signed_in):
    _, page = signed_in("owner")
    page.goto(live_server.url + "/reports/sales/")
    today = timezone.localdate()
    page.get_by_text(f"No sales in {today:%B} {today.year}.").wait_for()
