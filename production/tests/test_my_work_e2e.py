from datetime import timedelta
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone
from playwright.sync_api import expect

from orders.models import Order, OrderItem
from staff.models import DayRecord, Employee

pytestmark = pytest.mark.e2e

SHOTS = Path("artifacts/screens")


@pytest.fixture(autouse=True)
def _shots():
    SHOTS.mkdir(parents=True, exist_ok=True)


@pytest.fixture
def ali(signed_in):
    context, page = signed_in("employee")
    user = User.objects.get(username="employee")
    employee = Employee.objects.create(
        name="Ali Khan", phone="9000011120", daily_wage=800, user=user
    )
    employee.context, employee.page = context, page
    return employee


def add_item(employee, customer, name, number):
    order = Order.objects.create(
        customer=customer,
        number=number,
        status="open",
        due_date=timezone.localdate() + timedelta(days=number),
        assignee=employee,
    )
    return OrderItem.objects.create(
        order=order, name=name, type="custom", price=1450, usual_price=1450
    )


def open_page(signed_in, live_server, ali, names=("Blouse", "Petticoat"), day=False):
    from customers.models import Customer

    customer = Customer.objects.create(name="Meera Iyer", phone="9000000011")
    for n, name in enumerate(names, start=1):
        add_item(ali, customer, name, n)
    if day:
        now = timezone.now()
        DayRecord.objects.create(
            employee=ali, date=timezone.localdate(now), start=now - timedelta(hours=1)
        )
    return ali.context, ali.page


def test_time_items_in_place(signed_in, live_server, ali):
    context, page = open_page(signed_in, live_server, ali)
    page.goto(live_server.url + "/my-work/")
    page.evaluate("window.__marker = 1")
    page.screenshot(path=str(SHOTS / "S08-not-started.png"))
    page.get_by_role("button", name="Start my day").click()
    page.get_by_text("Day started").wait_for()
    page.get_by_role("button", name="Start Blouse").click()
    page.get_by_text("Now working on").wait_for()
    page.get_by_role("button", name="Switch Petticoat").click()
    expect(page.locator("#work-hero-title")).to_contain_text("Petticoat")
    page.screenshot(path=str(SHOTS / "S08-main.png"))
    page.get_by_role("button", name="Pause").click()
    page.get_by_text("Paused", exact=True).wait_for()
    page.screenshot(path=str(SHOTS / "S08-paused.png"))
    page.get_by_role("button", name="Resume").click()
    page.get_by_text("Now working on").wait_for()
    page.get_by_role("button", name="Finish item").click()
    page.get_by_text("Finished today").wait_for()
    page.get_by_role("button", name="End my day").click()
    page.get_by_text("Day ended at").wait_for()
    page.screenshot(path=str(SHOTS / "S08-day-ended.png"))
    assert page.evaluate("window.__marker") == 1


def test_timer_resyncs_after_hidden(signed_in, live_server, ali):
    context, page = open_page(signed_in, live_server, ali, day=True)
    page.clock.install()
    page.goto(live_server.url + "/my-work/")
    page.get_by_role("button", name="Start Blouse").click()
    timer = page.locator(".work-hero__timer")
    expect(timer).to_have_text("0:00:00")
    page.clock.set_system_time(timezone.now() + timedelta(hours=1))
    page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    expect(timer).to_contain_text("1:00:")


def test_nothing_assigned_and_dark(signed_in, live_server, ali, browser):
    context, page = open_page(signed_in, live_server, ali, names=(), day=True)
    page.goto(live_server.url + "/my-work/")
    page.get_by_text("Nothing assigned to you right now.").wait_for()
    page.screenshot(path=str(SHOTS / "S08-nothing-assigned.png"))
    from customers.models import Customer

    add_item(ali, Customer.objects.get(), "Blouse", 1)
    client = Client()
    client.force_login(ali.user)
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
    page.goto(live_server.url + "/my-work/")
    page.get_by_role("button", name="Start Blouse").click()
    page.get_by_text("Now working on").wait_for()
    page.screenshot(path=str(SHOTS / "S08-dark.png"))
    dark.close()


def test_offline_banner(signed_in, live_server, ali):
    context, page = open_page(signed_in, live_server, ali, day=True)
    page.clock.install()
    page.goto(live_server.url + "/my-work/")
    page.get_by_role("button", name="Start Blouse").click()
    timer = page.locator(".work-hero__timer")
    expect(timer).to_be_visible()
    before = timer.inner_text()
    context.set_offline(True)
    page.evaluate("dispatchEvent(new Event('offline'))")
    expect(page.get_by_text("Offline. Your time will be saved")).to_be_visible()
    page.clock.run_for(2000)
    expect(timer).not_to_have_text(before)
