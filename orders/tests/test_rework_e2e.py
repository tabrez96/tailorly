from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from playwright.sync_api import expect

from catalog.models import Product
from customers.models import Customer
from orders.models import Order, OrderItem, Rework
from staff.models import DayRecord, Employee

pytestmark = pytest.mark.e2e

SHOTS = Path("artifacts/screens")


@pytest.fixture
def shop(db):
    SHOTS.mkdir(parents=True, exist_ok=True)
    Product.objects.create(
        name="Lining, cotton cream",
        kind=Product.SECONDARY,
        unit="m",
        cost_price=Decimal("120"),
        selling_price=Decimal("150"),
        billed_by_default=True,
    )
    user = User.objects.create_user("ali", password="x")
    ali = Employee.objects.create(
        name="Ali Khan", phone="9000011120", daily_wage=800, user=user
    )
    meera = Customer.objects.create(name="Meera Iyer", phone="9845022110")
    order = Order.objects.create(
        customer=meera, number=1031, status="delivered", assignee=ali
    )
    for name in ("Blouse", "Petticoat"):
        OrderItem.objects.create(
            order=order,
            name=name,
            type=Product.CUSTOM,
            price=Decimal(1450),
            usual_price=Decimal(1450),
            status=OrderItem.FINISHED,
        )
    return order, ali


def test_add_rework_flow(live_server, signed_in, shop):
    order, ali = shop
    _, page = signed_in("owner")
    page.goto(live_server.url + f"/orders/{order.pk}/")
    invoice = page.locator("#order-invoice").inner_text()
    page.evaluate("window.__marker = 1")
    page.locator("#add-rework").click()
    page.get_by_role("heading", name="Add rework").wait_for()
    sheet = page.locator("#sheet")
    assert page.input_value("#id_estimate") == "45m"
    assert (
        page.input_value("#id_due_date")
        == (timezone.localdate() + timedelta(days=2)).isoformat()
    )
    expect(page.locator("#id_assignee")).to_have_value(str(ali.pk))
    sheet.get_by_role("button", name="Save rework").click()
    expect(page.get_by_text("Say what needs doing so Ali knows.").first).to_be_visible()
    page.fill("#id_note", "Loosen waist by 1 inch, shorten sleeves by half an inch.")
    page.locator("#rework-add-material").click()
    sheet.locator("label", has_text="Lining, cotton cream").click()
    page.fill("#mat-qty", "0.25")
    expect(page.locator("#mat-bill")).to_have_count(0)
    sheet.get_by_role("button", name="Add", exact=True).click()
    expect(sheet.get_by_text("0.25 m · never billed for rework")).to_be_visible()
    assert page.input_value("#id_note").startswith("Loosen waist")
    page.screenshot(path=str(SHOTS / "S04-add-rework.png"))
    page.emulate_media(color_scheme="dark")
    page.screenshot(path=str(SHOTS / "S04-add-rework-dark.png"))
    sheet.get_by_role("button", name="Save rework").click()
    expect(page.get_by_text("Rework added to Ali's queue")).to_be_visible()
    assert page.locator("#order-invoice").inner_text() == invoice
    assert page.evaluate("window.__marker") == 1
    assert Rework.objects.get().materials.count() == 1


def test_rework_timed_on_my_work(live_server, signed_in, shop):
    order, ali = shop
    now = timezone.now()
    DayRecord.objects.create(
        employee=ali, date=timezone.localdate(now), start=now - timedelta(hours=1)
    )
    Rework.objects.create(
        item=order.items.first(),
        reason="fit",
        note="Loosen waist",
        assignee=ali,
        due_date=timezone.localdate() + timedelta(days=2),
    )
    context, page = signed_in("employee")
    context.clear_cookies()
    from django.test import Client

    client = Client()
    client.force_login(ali.user)
    context.add_cookies(
        [
            {
                "name": "sessionid",
                "value": client.cookies["sessionid"].value,
                "url": live_server.url,
            }
        ]
    )
    page.goto(live_server.url + "/my-work/")
    page.get_by_role("button", name="Start rework Blouse").click()
    expect(page.locator("#work-hero-title")).to_contain_text("Rework · Blouse")
    page.get_by_role("button", name="Finish item").click()
    page.get_by_text("Finished today").wait_for()
    assert Rework.objects.get().finished_at is not None


def shoot(page, name):
    page.screenshot(path=str(SHOTS / f"{name}.png"), full_page=True)
    page.emulate_media(color_scheme="dark")
    page.screenshot(path=str(SHOTS / f"{name}-dark.png"), full_page=True)
    page.emulate_media(color_scheme="light")


def test_rework_states_screens(live_server, signed_in, shop):
    from orders.models import Payment
    from production.models import TimeSession

    order, ali = shop
    _, page = signed_in("owner")
    page.goto(live_server.url + f"/orders/{order.pk}/")
    expect(page.get_by_text("No reworks after delivery.")).to_be_visible()
    expect(page.get_by_text("Rework open")).to_have_count(0)
    shoot(page, "S04-no-rework")

    blouse, petticoat = order.items.order_by("pk")
    OrderItem.objects.filter(pk=blouse.pk).update(price=Decimal(1800))
    OrderItem.objects.filter(pk=petticoat.pk).update(price=Decimal(600))
    Payment.objects.create(
        order=order, amount=Decimal(2400), date=timezone.localdate(), method="cash"
    )
    now = timezone.now()
    for item, minutes in ((blouse, 185), (petticoat, 55)):
        TimeSession.objects.create(
            employee=ali,
            item=item,
            started_at=now - timedelta(days=2),
            ended_at=now - timedelta(days=2) + timedelta(minutes=minutes),
        )
    for item, minutes, finished in ((blouse, 40, now), (petticoat, 20, None)):
        rework = Rework.objects.create(
            item=item, reason="fit", note="Loosen", assignee=ali, finished_at=finished
        )
        TimeSession.objects.create(
            employee=ali,
            rework=rework,
            started_at=now - timedelta(hours=1),
            ended_at=now - timedelta(hours=1) + timedelta(minutes=minutes),
        )
    page.goto(live_server.url + f"/orders/{order.pk}/")
    expect(page.get_by_text("Rework open").first).to_be_visible()
    expect(page.get_by_text("3h 05m + 40m rework")).to_be_visible()
    expect(page.get_by_text("55m + 20m rework")).to_be_visible()
    expect(page.get_by_text("Gain on this order after rework")).to_be_visible()
    shoot(page, "S04-rework-open")
