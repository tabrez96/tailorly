from datetime import timedelta
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.test import Client
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


def kurta(customer, product, ali, number, estimate, minutes, finished, days_ago=0):
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
        estimate_minutes=estimate,
        status="finished" if finished else "in_progress",
        finished_at=timezone.now() - timedelta(days=days_ago) if finished else None,
    )
    start = timezone.now() - timedelta(days=days_ago, minutes=minutes + 1)
    if not finished:
        # A running session from before local midnight is stale, so keep it today.
        midnight = timezone.localtime().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        start = max(start, midnight)
    if minutes:
        TimeSession.objects.create(
            employee=ali,
            item=item,
            started_at=start,
            ended_at=start + timedelta(minutes=minutes) if finished else None,
        )
    return item


def seed(finished=True):
    customer = Customer.objects.create(name="Farhan Sheikh", phone="9000000011")
    ali = Employee.objects.create(name="Ali Khan", phone="9000011120", daily_wage=800)
    product = Product.objects.create(
        name="Kurta", kind=Product.PRIMARY, type=Product.CUSTOM, usual_price=1450
    )
    for n in range(3):
        kurta(customer, product, ali, 10 + n, 165, 170, True, days_ago=10 + n)
    if not finished:
        return kurta(customer, product, ali, 1, 165, 72, False)
    item = kurta(customer, product, ali, 1, 165, 0, True)
    now = timezone.now()
    for i, minutes in enumerate((88, 30, 60, 7)):
        start = now - timedelta(days=4 - i, hours=1)
        TimeSession.objects.create(
            employee=ali,
            item=item,
            started_at=start,
            ended_at=start + timedelta(minutes=minutes),
        )
    return item


def test_record_finished(signed_in, live_server):
    context, page = signed_in("owner")
    item = seed()
    page.goto(live_server.url + f"/orders/{item.order.pk}/")
    page.locator(".item-card__production").click()
    expect(page.get_by_text("Time taken", exact=True)).to_be_visible()
    expect(page.get_by_text("20m over (+12%)")).to_be_visible()
    expect(page.get_by_text("Estimate vs time taken")).to_be_visible()
    expect(page.locator(".record-session")).to_have_count(5)
    page.screenshot(path=str(SHOTS / "S17-production-record.png"), full_page=True)
    page.get_by_label("Why it took longer").fill("Lining was thin")
    page.get_by_role("button", name="Save note").click()
    expect(page.get_by_text("Note saved")).to_be_visible()
    page.reload()
    expect(page.get_by_label("Why it took longer")).to_have_value("Lining was thin")


def test_record_in_progress(signed_in, live_server):
    context, page = signed_in("owner")
    item = seed(finished=False)
    page.goto(live_server.url + f"/production/items/{item.pk}/record/")
    expect(page.get_by_text("Logged so far")).to_be_visible()
    expect(page.locator(".record-hero__chip")).to_contain_text("Running")
    expect(page.get_by_text("Estimate vs time taken")).to_have_count(0)
    page.screenshot(
        path=str(SHOTS / "S17-production-record-in-progress.png"), full_page=True
    )


def test_record_dark(signed_in, live_server, browser):
    context, page = signed_in("owner")
    item = seed()
    client = Client()
    client.force_login(User.objects.get(username="owner"))
    dark = browser.new_context(
        viewport={"width": 390, "height": 844}, color_scheme="dark"
    )
    dark.add_cookies(
        [
            {
                "name": "sessionid",
                "value": client.cookies["sessionid"].value,
                "url": live_server.url,
            }
        ]
    )
    page = dark.new_page()
    page.goto(live_server.url + f"/production/items/{item.pk}/record/")
    expect(page.get_by_text("Time taken", exact=True)).to_be_visible()
    page.screenshot(path=str(SHOTS / "S17-production-record-dark.png"), full_page=True)
    dark.close()
