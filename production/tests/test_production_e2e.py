from datetime import timedelta
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone
from playwright.sync_api import expect

from customers.models import Customer
from orders.models import Order, OrderItem
from production.models import TimeSession
from staff.models import DayRecord, Employee

pytestmark = pytest.mark.e2e

SHOTS = Path("artifacts/screens")


@pytest.fixture(autouse=True)
def _shots():
    SHOTS.mkdir(parents=True, exist_ok=True)


def order(customer, number, assignee, name, days):
    row = Order.objects.create(
        customer=customer,
        number=number,
        status="open",
        due_date=timezone.localdate() + timedelta(days=days),
        assignee=assignee,
    )
    return OrderItem.objects.create(
        order=row,
        name=name,
        type="custom",
        price=1450,
        usual_price=1450,
        estimate_minutes=165,
    )


def seed(day=True, session=None):
    """Ali with three items, two waiting orders; session: None, "open" or "closed"."""
    customer = Customer.objects.create(name="Priya Sharma", phone="9000000011")
    ali = Employee.objects.create(name="Ali Khan", phone="9000011120", daily_wage=800)
    kurta = order(customer, 1, ali, "Kurta", 2)
    order(customer, 2, ali, "Blouse", 3)
    order(customer, 3, ali, "Salwar", 4)
    order(customer, 4, None, "Anarkali", 5)
    order(customer, 5, None, "Saree blouse", 7)
    now = timezone.now()
    if day:
        DayRecord.objects.create(
            employee=ali,
            date=timezone.localdate(now),
            start=now - timedelta(hours=3),
        )
    if session:
        TimeSession.objects.create(
            employee=ali,
            item=kurta,
            started_at=now - timedelta(minutes=72),
            ended_at=now - timedelta(minutes=1) if session == "closed" else None,
        )
    return ali


def test_production_main(signed_in, live_server):
    context, page = signed_in("owner")
    seed(session="open")
    page.goto(live_server.url + "/production/")
    expect(page.get_by_text("Working", exact=True)).to_be_visible()
    expect(page.locator(".live-item__timer")).to_have_text("1h 12m")
    expect(page.locator(".nav [aria-current]")).to_contain_text("Production")
    page.screenshot(path=str(SHOTS / "S12-production.png"), full_page=True)


def test_production_paused(signed_in, live_server):
    context, page = signed_in("owner")
    seed(session="closed")
    page.goto(live_server.url + "/production/")
    expect(page.get_by_text("Paused at")).to_be_visible()
    page.screenshot(path=str(SHOTS / "S12-production-paused.png"), full_page=True)


def test_production_not_in_yet(signed_in, live_server):
    context, page = signed_in("owner")
    seed(day=False)
    page.goto(live_server.url + "/production/")
    page.evaluate("window.__marker = 1")
    expect(page.get_by_text("Not in yet", exact=True)).to_be_visible()
    page.screenshot(path=str(SHOTS / "S12-production-not-in-yet.png"), full_page=True)
    page.get_by_role("button", name="Start Ali's day").click()
    expect(page.get_by_text("Not timing anything", exact=True)).to_be_visible()
    assert page.evaluate("window.__marker") == 1


def test_production_dark(signed_in, live_server, browser):
    context, page = signed_in("owner")
    seed(session="open")
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
    page.goto(live_server.url + "/production/")
    expect(page.get_by_text("Working", exact=True)).to_be_visible()
    page.screenshot(path=str(SHOTS / "S12-production-dark.png"), full_page=True)
    dark.close()


def test_give_work_opens_assign_sheet_and_returns(signed_in, live_server):
    context, page = signed_in("owner")
    seed(session="open")
    page.goto(live_server.url + "/production/")
    page.get_by_role("button", name="Give Ali work").click()
    expect(page.get_by_text("Who makes it")).to_be_visible()
    expect(page.get_by_text("Assign Anarkali")).to_be_visible()
    page.get_by_role("button", name="Assign to Ali").click()
    expect(page.get_by_text("#4 assigned to Ali")).to_be_visible()
    assert page.url.endswith("/production/")
    waiting = page.locator("h2", has_text="Waiting for someone").locator(
        "xpath=following-sibling::*[1]"
    )
    expect(waiting).not_to_contain_text("Anarkali")


def test_polling_starts_and_stops(signed_in, live_server):
    context, page = signed_in("owner")
    seed(session="open")
    page.clock.install()
    polls = []
    page.on("request", lambda r: "/production/now/" in r.url and polls.append(r.url))
    page.goto(live_server.url + "/production/")
    expect(page.locator("#right-now")).to_be_visible()
    page.clock.run_for(31_000)
    page.wait_for_timeout(300)
    assert len(polls) >= 1
    page.get_by_role("link", name="Work plan").click()
    page.clock.run_for(1_000)
    expect(page.get_by_role("heading", name="Work plan")).to_be_visible()
    page.wait_for_timeout(300)
    seen = len(polls)
    page.clock.run_for(61_000)
    page.wait_for_timeout(300)
    assert len(polls) == seen
