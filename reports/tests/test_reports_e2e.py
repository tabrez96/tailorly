from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from django.utils import timezone

from customers.models import Customer
from orders.models import Payment
from orders.tests.conftest import make_order
from staff.models import DayRecord, Employee

pytestmark = pytest.mark.e2e

ARTIFACTS = Path(__file__).resolve().parent.parent.parent / "artifacts" / "screens"


def seed_payments():
    today = timezone.localdate()
    customer = Customer.objects.create(name="Priya Shetty", phone="9000000101")
    old = make_order(customer, 1, status="delivered", price="2000")
    old.delivered_at = timezone.now() - timedelta(days=12)
    old.save()
    open_order = make_order(customer, 2, price="1500")
    for order, amount, method in ((old, "500", "upi"), (open_order, "700", "cash")):
        Payment.objects.create(
            order=order, amount=Decimal(amount), date=today, method=method
        )
    return old


def seed_staff():
    today = timezone.localdate()
    ali = Employee.objects.create(
        name="Ali Khan", phone="9000000001", daily_wage=Decimal(800)
    )
    for i in range(1, 4):
        day = today - timedelta(days=i)
        start = timezone.make_aware(datetime.combine(day, datetime.min.time())).replace(
            hour=9
        )
        DayRecord.objects.create(
            employee=ali, date=day, start=start, end=start + timedelta(hours=10)
        )


def settle(page):
    page.evaluate("document.fonts.ready.then(() => true)")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)


def test_payments_flow(live_server, signed_in):
    old = seed_payments()
    _, page = signed_in("owner")
    page.goto(live_server.url + "/reports/payments/")
    page.locator("#payments-hero").wait_for()
    settle(page)
    page.screenshot(path=ARTIFACTS / "S13-payments.png", full_page=True)
    page.evaluate("window.__marker = 1")
    page.locator("#period-week").click()
    page.wait_for_url("**period=week**")
    page.locator("#period-month").click()
    page.wait_for_function("!location.search.includes('period=week')")
    page.locator("#period-prev").click()
    page.wait_for_url("**date=**")
    assert page.evaluate("window.__marker") == 1
    page.locator("#period-next").click()
    page.locator("#payments-owing a").first.wait_for()
    page.locator("#payments-owing a").first.click()
    page.wait_for_url(f"**/orders/{old.pk}/")


def test_payments_dark(live_server, signed_in):
    seed_payments()
    _, page = signed_in("owner")
    page.emulate_media(color_scheme="dark")
    page.goto(live_server.url + "/reports/payments/")
    page.locator("#payments-hero").wait_for()
    settle(page)
    page.screenshot(path=ARTIFACTS / "S13-payments-dark.png", full_page=True)


def test_staff_report_flow(live_server, signed_in):
    seed_staff()
    _, page = signed_in("owner")
    page.goto(live_server.url + "/reports/staff/")
    page.locator("#staff-hero").wait_for()
    settle(page)
    page.screenshot(path=ARTIFACTS / "S14-staff-report.png", full_page=True)
    page.locator("#period-week").click()
    page.wait_for_url("**period=week**")
    page.locator("#period-month").click()
    page.wait_for_function("!location.search.includes('period=week')")
    assert page.locator("#period-day").count() == 0
    page.locator("#report-payments_report").click()
    page.wait_for_url("**/reports/payments/**")


def test_staff_report_dark(live_server, signed_in):
    seed_staff()
    _, page = signed_in("owner")
    page.emulate_media(color_scheme="dark")
    page.goto(live_server.url + "/reports/staff/")
    page.locator("#staff-hero").wait_for()
    settle(page)
    page.screenshot(path=ARTIFACTS / "S14-staff-report-dark.png", full_page=True)
