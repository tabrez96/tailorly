from datetime import timedelta
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone
from playwright.sync_api import expect

from customers.models import Customer
from orders.models import Order, OrderItem
from staff.models import Employee

pytestmark = pytest.mark.e2e

SHOTS = Path("artifacts/screens")
NAMES = ["Blouse", "Petticoat", "Kurta", "Lehenga", "Saree blouse", "Salwar"]


@pytest.fixture(autouse=True)
def _shots():
    SHOTS.mkdir(parents=True, exist_ok=True)


def order(customer, number, assignee, name, days, free=False):
    row = Order.objects.create(
        customer=customer,
        number=number,
        status="open",
        due_date=timezone.localdate() + timedelta(days=days),
        assignee=assignee,
        paid_by=Order.FREE if free else Order.CUSTOMER,
    )
    return OrderItem.objects.create(
        order=row,
        name=name,
        type="custom",
        price=1450,
        usual_price=1450,
        estimate_minutes=120,
    )


def seed():
    customer = Customer.objects.create(name="Meera Iyer", phone="9000000011")
    ali = Employee.objects.create(name="Ali Khan", phone="9000011120", daily_wage=800)
    items = [
        order(customer, n, ali, name, n + 1) for n, name in enumerate(NAMES, start=1)
    ]
    items[0].status = OrderItem.IN_PROGRESS
    items[0].save()
    items[4].queue_rank = 2
    items[4].save()
    order(customer, 7, None, "Anarkali", 5)
    order(customer, 8, None, "Saree blouse", 5, free=True)


def test_work_plan_main(signed_in, live_server):
    context, page = signed_in("owner")
    seed()
    page.goto(live_server.url + "/")
    page.evaluate("window.__marker = 1")
    page.evaluate(
        "htmx.ajax('get', '/production/plan/', {target: '#page', push: 'true'})"
    )
    expect(page.get_by_text("Suggested next for Ali")).to_be_visible()
    expect(page.get_by_text("Not assigned")).to_be_visible()
    expect(page.get_by_text("Ali's queue")).to_be_visible()
    expect(page.locator(".nav [aria-current]")).to_contain_text("Production")
    assert page.evaluate("window.__marker") == 1
    page.screenshot(path=str(SHOTS / "S16-work-plan.png"), full_page=True)


def test_work_plan_empty_and_dark(signed_in, live_server, browser):
    context, page = signed_in("owner")
    page.goto(live_server.url + "/production/plan/")
    expect(page.get_by_text("Nothing to plan")).to_be_visible()
    page.screenshot(path=str(SHOTS / "S16-work-plan-empty.png"))
    seed()
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
    page.goto(live_server.url + "/production/plan/")
    expect(page.get_by_text("Suggested next for Ali")).to_be_visible()
    page.screenshot(path=str(SHOTS / "S16-work-plan-dark.png"), full_page=True)
    dark.close()


def test_assign_sheet_flow(signed_in, live_server):
    context, page = signed_in("owner")
    seed()
    page.goto(live_server.url + "/production/plan/")
    page.locator("li", has_text="Anarkali").get_by_role("button", name="Assign").click()
    expect(page.get_by_text("Who makes it")).to_be_visible()
    expect(page.get_by_text("Assign Anarkali")).to_be_visible()
    page.screenshot(path=str(SHOTS / "S16-work-plan-assign.png"))
    page.locator("#sheet").get_by_text("Next up", exact=True).click()
    expect(page.locator("#assign-place-next")).to_be_checked()
    page.get_by_role("button", name="Assign to Ali").click()
    expect(page.get_by_text("#7 assigned to Ali")).to_be_visible()
    queue = page.locator(".queue li")
    expect(queue.nth(1)).to_contain_text("Anarkali")


def test_hold_production_opens_assign_sheet(signed_in, live_server):
    context, page = signed_in("owner")
    seed()
    page.goto(live_server.url + "/production/plan/?assign=next")
    expect(page.get_by_text("Assign Anarkali")).to_be_visible()
    expect(page.get_by_text("Who makes it")).to_be_visible()
