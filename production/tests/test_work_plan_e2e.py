from datetime import timedelta
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone
from playwright.sync_api import expect

from customers.models import Customer
from orders.models import Order, OrderItem
from production.plan import clear_queue
from production.timing import queue_rows
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


def queue_keys(employee):
    return [r["key"] for r in queue_rows(employee, timezone.now())]


def kurta_handle(page):
    return page.locator(".queue li", has_text="Kurta").locator(".qrow__handle")


def test_reorder_keyboard(signed_in, live_server):
    context, page = signed_in("owner")
    seed()
    page.goto(live_server.url + "/production/plan/")
    kurta_handle(page).focus()
    page.keyboard.press("Enter")
    expect(page.locator(".move-bar")).to_contain_text("Kurta, 4th of 6")
    page.screenshot(path=str(SHOTS / "S16-work-plan-reorder.png"))
    page.get_by_role("button", name="↓ Down").click()
    expect(page.locator(".plan-queue [aria-live=polite]")).to_have_text(
        "Kurta moved to position 5 of 6."
    )
    expect(page.locator(".move-bar")).to_contain_text("Kurta, 5th of 6")
    page.get_by_role("button", name="↑ Up").click()
    expect(page.locator(".plan-queue [aria-live=polite]")).to_have_text(
        "Kurta moved to position 4 of 6."
    )
    page.get_by_role("button", name="Done").click()
    expect(page.get_by_text("You moved 2 items.")).to_be_visible()
    expect(page.locator(".queue li", has_text="Kurta")).to_contain_text("Moved by you")
    page.get_by_role("button", name="Back to suggested").click()
    expect(page.get_by_text("Moved by you")).to_have_count(0)
    expect(page.get_by_text("You moved")).to_have_count(0)


def test_drag_and_keyboard_save_the_same_order(signed_in, live_server):
    context, page = signed_in("owner")
    seed()
    ali = Employee.objects.get(name="Ali Khan")
    pins = list(
        OrderItem.objects.filter(queue_rank__isnull=False).values_list(
            "pk", "queue_rank"
        )
    )
    page.goto(live_server.url + "/production/plan/")
    kurta_handle(page).scroll_into_view_if_needed()
    page.locator(".queue li", has_text="Lehenga").scroll_into_view_if_needed()
    handle = kurta_handle(page).bounding_box()
    target = page.locator(".queue li", has_text="Lehenga").bounding_box()
    page.mouse.move(handle["x"] + 22, handle["y"] + 22)
    page.mouse.down()
    page.mouse.move(
        target["x"] + target["width"] / 2,
        target["y"] + target["height"] / 2 + 10,
        steps=10,
    )
    page.mouse.up()
    expect(page.locator(".plan-queue [aria-live=polite]")).to_have_text(
        "Kurta moved to position 5 of 6."
    )
    dragged = queue_keys(ali)
    clear_queue(ali, timezone.now())
    for pk, rank in pins:
        OrderItem.objects.filter(pk=pk).update(queue_rank=rank)
    page.goto(live_server.url + "/production/plan/")
    kurta_handle(page).focus()
    page.keyboard.press("Enter")
    page.get_by_role("button", name="↓ Down").click()
    expect(page.locator(".plan-queue [aria-live=polite]")).to_have_text(
        "Kurta moved to position 5 of 6."
    )
    assert queue_keys(ali) == dragged


def test_failed_save_snaps_back(signed_in, live_server):
    context, page = signed_in("owner")
    seed()
    page.goto(live_server.url + "/production/plan/")
    page.route("**/queue/*/move/", lambda r: r.abort())
    kurta_handle(page).focus()
    page.keyboard.press("Enter")
    page.get_by_role("button", name="↓ Down").click()
    expect(page.get_by_role("alert")).to_contain_text(
        "Couldn't save the new order. Check your connection and try again."
    )
    expect(page.locator(".queue li").nth(3)).to_contain_text("Kurta")
