from datetime import timedelta
from pathlib import Path

import pytest
from django.utils import timezone
from playwright.sync_api import expect

from catalog.models import Product
from customers.models import Customer
from orders.models import Order, OrderItem
from production.models import TimeSession
from staff.models import Employee

pytestmark = pytest.mark.e2e

SHOTS = Path("artifacts/screens")


@pytest.fixture(autouse=True)
def _shots():
    SHOTS.mkdir(parents=True, exist_ok=True)


def seed():
    customer = Customer.objects.create(name="Farhan Sheikh", phone="9000000011")
    ali = Employee.objects.create(name="Ali Khan", phone="9000011120", daily_wage=800)
    product = Product.objects.create(
        name="Kurta", kind=Product.PRIMARY, type=Product.CUSTOM, usual_price=1450
    )
    now = timezone.now()
    for number, minutes in ((1, 185), (2, 40)):
        order = Order.objects.create(
            customer=customer,
            number=number,
            status="open",
            due_date=timezone.localdate() + timedelta(days=2),
            assignee=ali,
        )
        item = OrderItem.objects.create(
            order=order,
            product=product,
            name="Kurta",
            type="custom",
            price=1450,
            usual_price=1450,
            estimate_minutes=165,
            status="finished",
            finished_at=now,
        )
        TimeSession.objects.create(
            employee=ali,
            item=item,
            started_at=now - timedelta(minutes=minutes),
            ended_at=now,
        )


def test_report_from_tab(signed_in, live_server):
    context, page = signed_in("owner")
    seed()
    page.goto(live_server.url + "/production/")
    page.locator("#week-so-far").click()
    expect(page.locator(".report-hero")).to_be_visible()
    expect(page.locator("#report-production_report")).to_have_attribute(
        "aria-current", "true"
    )
    expect(page.get_by_text("Estimate vs time taken")).to_be_visible()
    page.screenshot(path=str(SHOTS / "S12-production-from-reports.png"), full_page=True)
    page.locator("#period-day").click()
    expect(page.get_by_text("Finished today")).to_be_visible()
    page.screenshot(path=str(SHOTS / "S12-production-day.png"), full_page=True)
    page.get_by_role("link", name="Back").click()
    expect(page.get_by_text("This week so far")).to_be_visible()
    assert page.url.endswith("/production/")


def test_report_empty(signed_in, live_server):
    context, page = signed_in("owner")
    page.goto(live_server.url + "/production/report/")
    expect(page.get_by_text("Nothing finished this week")).to_be_visible()
    page.screenshot(path=str(SHOTS / "S12-production-empty.png"), full_page=True)
