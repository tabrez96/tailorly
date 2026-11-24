from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.http import QueryDict
from django.urls import reverse
from django.utils import timezone

from accounts.roles import EMPLOYEE, add_to_role
from catalog.models import Product
from orders.models import MaterialLine, Order, OrderItem, Payment, Rework
from orders.reworks import default_due, item_maker, read_staged
from orders.tests.conftest import make_order
from production.models import TimeSession
from production.timing import queue_rows
from staff.models import Employee

pytestmark = pytest.mark.django_db
HX = {"HTTP_HX_REQUEST": "true"}
D = Decimal


def employee(name, phone):
    return Employee.objects.create(name=name, phone=phone, daily_wage=800)


@pytest.fixture
def ali(db):
    return employee("Ali Khan", "9000011120")


@pytest.fixture
def order(customer, ali):
    order = make_order(customer, 1, status="delivered", price="1200")
    Order.objects.filter(pk=order.pk).update(assignee=ali)
    order.refresh_from_db()
    return order


@pytest.fixture
def item(order):
    return order.items.get()


@pytest.fixture
def cream(db):
    return Product.objects.create(
        name="Lining, cotton cream",
        kind=Product.SECONDARY,
        unit="m",
        cost_price=D("120"),
        selling_price=D("150"),
        billed_by_default=True,
    )


def url(order):
    return f"/orders/{order.pk}/reworks/new/"


def staged_data(cream, **extra):
    return {
        "m_product": [str(cream.pk)],
        "m_qty": ["0.25"],
        "m_cost": ["30"],
        "m_sell": ["37.5"],
        **extra,
    }


def save_data(item, ali, **extra):
    return {
        "step": "save",
        "item": item.pk,
        "reason": "fit",
        "note": "Loosen waist",
        "assignee": ali.pk,
        "estimate": "45m",
        "due_date": "2026-11-26",
        **extra,
    }


def test_default_due_is_two_days():
    assert default_due(date(2026, 11, 12)) == date(2026, 11, 14)


def test_item_maker_prefers_latest_session_then_order_assignee(item, ali):
    sana = employee("Sana", "9000011121")
    assert item_maker(item, None) is None
    assert item_maker(item, sana) == sana
    now = timezone.now()
    for who, ago in ((ali, 3), (sana, 1)):
        TimeSession.objects.create(
            employee=who,
            item=item,
            started_at=now - timedelta(hours=ago),
            ended_at=now - timedelta(hours=ago, minutes=-10),
        )
    item = OrderItem.objects.prefetch_related("sessions__employee").get(pk=item.pk)
    assert item_maker(item, ali) == sana


def test_read_staged_drops_bad_rows(cream):
    data = QueryDict(mutable=True)
    pks = [str(cream.pk)] * 4
    data.setlist("m_product", [pks[0], "999", *pks[1:], "x"])
    data.setlist("m_qty", ["0.25", "1", "0", "x", "1000000", "1"])
    data.setlist("m_cost", ["30", "1", "1", "1", "1", "1"])
    data.setlist("m_sell", ["37.5", "1", "1", "1", "1", "1"])
    [row] = read_staged(data)
    assert (row.product, row.qty, row.cost, row.sell) == (
        cream,
        D("0.25"),
        D("30"),
        D("37.5"),
    )
    data.setlist("m_product", [str(cream.pk)])
    data.setlist("m_qty", ["1"])
    data.setlist("m_cost", [""])
    data.setlist("m_sell", ["5"])
    assert read_staged(data)[0].cost is None


@pytest.mark.parametrize(
    "status,rework,deliver",
    [
        ("open", False, False),
        ("in_progress", False, False),
        ("ready", True, True),
        ("delivered", True, False),
    ],
)
def test_bar_shows_rework_on_ready_and_delivered(
    owner_client, customer, status, rework, deliver
):
    order = make_order(customer, 1, status=status)
    html = owner_client.get(f"/orders/{order.pk}/").content.decode()
    assert ('id="add-rework"' in html) is rework
    assert ('id="mark-delivered"' in html) is deliver


def test_sheet_404_on_open_order(owner_client, customer, ali):
    order = make_order(customer, 1, status="open")
    assert owner_client.get(url(order)).status_code == 404
    assert (
        owner_client.post(url(order), save_data(order.items.get(), ali)).status_code
        == 404
    )


def test_employee_cannot_open_sheet(client, order):
    user = User.objects.create_user("ravi", password="x")
    add_to_role(user, EMPLOYEE)
    client.force_login(user)
    assert client.get(url(order)).status_code in (302, 403, 404)


def test_sheet_defaults(owner_client, order, ali):
    html = owner_client.get(url(order), **HX).content.decode()
    due = (timezone.localdate() + timedelta(days=2)).isoformat()
    assert 'value="45m"' in html
    assert f'value="{due}"' in html
    assert f'<option value="{ali.pk}" selected>' in html
    assert "made by Ali" in html
    assert 'value="fit"' in html and "Fit alteration" in html
    assert "their balance stays the same" in html


def test_empty_what_to_do_error(owner_client, order, item, ali):
    response = owner_client.post(url(order), save_data(item, ali, note="  "), **HX)
    assert response.status_code == 422
    assert "Say what needs doing so Ali knows." in response.content.decode()
    assert Rework.objects.count() == 0


def test_bad_estimate_keeps_staged(owner_client, order, item, ali, cream):
    data = save_data(item, ali, estimate="abc") | staged_data(cream)
    response = owner_client.post(url(order), data, **HX)
    assert response.status_code == 422
    assert 'name="m_product"' in response.content.decode()


def test_pick_then_add_material_stages_it(owner_client, order, item, ali, cream):
    data = save_data(item, ali, step="pick")
    html = owner_client.post(url(order), data, **HX).content.decode()
    assert 'id="mat-bill"' not in html
    assert 'name="note" value="Loosen waist"' in html
    data = save_data(item, ali, step="material", material=cream.pk, qty="0.25")
    data |= {"cost": "30", "sell": "37.5"}
    response = owner_client.post(url(order), data, **HX)
    html = response.content.decode()
    assert response.status_code == 200
    assert "Lining, cotton cream" in html
    assert "0.25 m · never billed for rework" in html
    assert 'name="m_product"' in html
    assert MaterialLine.objects.count() == 0


def test_material_without_choice_is_422(owner_client, order, item, ali):
    data = save_data(item, ali, step="material", qty="1", cost="1", sell="1")
    assert owner_client.post(url(order), data, **HX).status_code == 422


def test_back_and_remove(owner_client, order, item, ali, cream):
    data = save_data(item, ali, step="remove:0") | staged_data(cream)
    assert "No materials." in owner_client.post(url(order), data, **HX).content.decode()
    data["step"] = "remove:9"
    assert (
        "Lining, cotton cream"
        in owner_client.post(url(order), data, **HX).content.decode()
    )
    data["step"] = "back"
    assert (
        "Lining, cotton cream"
        in owner_client.post(url(order), data, **HX).content.decode()
    )


def test_save_creates_rework_and_unbilled_materials(
    owner_client, order, item, ali, cream
):
    data = save_data(item, ali, estimate="1h 30m") | staged_data(cream)
    response = owner_client.post(url(order), data, **HX)
    assert response.status_code == 200
    rework = Rework.objects.get()
    assert (rework.item, rework.reason, rework.note, rework.assignee) == (
        item,
        "fit",
        "Loosen waist",
        ali,
    )
    assert rework.estimate_minutes == 90
    assert rework.due_date == date(2026, 11, 26)
    line = MaterialLine.objects.get()
    assert line.rework == rework and line.item is None and line.on_bill is False
    assert (line.quantity, line.cost_price, line.selling_price) == (
        D("0.25"),
        D("120.00"),
        D("150.00"),
    )


def test_save_without_cost_is_cost_unknown(owner_client, order, item, ali, cream):
    data = save_data(item, ali) | staged_data(cream, m_cost=[""])
    owner_client.post(url(order), data, **HX)
    line = MaterialLine.objects.get()
    assert line.cost_price is None


def test_save_never_changes_invoice(owner_client, order, item, ali, cream):
    Payment.objects.create(
        order=order, amount=D("500"), method="cash", date=date(2026, 11, 20)
    )
    before = order.invoice()
    owner_client.post(url(order), save_data(item, ali) | staged_data(cream), **HX)
    after = Order.objects.get(pk=order.pk).invoice()
    assert (after.total, after.received, after.balance) == (
        before.total,
        before.received,
        before.balance,
    )
    assert Payment.objects.count() == 1
    assert MaterialLine.objects.get().on_bill is False


def test_saved_rework_in_assignee_queue(owner_client, order, item, ali):
    owner_client.post(url(order), save_data(item, ali), **HX)
    rework = Rework.objects.get()
    rows = queue_rows(ali, timezone.now())
    assert any(row.get("rework") and row["rework"].pk == rework.pk for row in rows)


# --- S04: Rework after delivery -------------------------------------------

from orders.reworks import (  # noqa: E402
    materials_text,
    minus_inr,
    minutes_text,
    ready_made_with_rework,
    rework_detail,
    rework_state,
    time_with_rework,
)
from production import timing  # noqa: E402
from reports import costing  # noqa: E402
from reports.order_costs import cost_card, item_cost_card  # noqa: E402


def test_minutes_text():
    assert minutes_text(40, 45, True) == "40 min"
    assert minutes_text(25, 45, False) == "25 of 45 min"


def test_materials_text():
    assert materials_text([]) == "No materials"
    lines = [
        MaterialLine(name="Lining, cotton cream", quantity=D("0.25"), unit="m"),
        MaterialLine(name="Hooks", quantity=D("4"), unit="pcs"),
    ]
    assert materials_text(lines) == "Lining, cotton cream 0.25 m · Hooks 4 pcs"


def test_minus_inr():
    assert minus_inr(D(142)) == "\N{MINUS SIGN}₹142"
    assert minus_inr(D(0)) == "₹0"


def test_time_with_rework():
    assert time_with_rework(185, 40) == "3h 05m + 40m rework"
    assert time_with_rework(55, 20) == "55m + 20m rework"
    assert time_with_rework(185, 0) == "3h 05m"


def test_ready_made_with_rework():
    assert ready_made_with_rework(40) == "Ready-made + 40m rework"
    assert ready_made_with_rework(0) == "Ready-made"


def test_ready_made_row_shows_rework_time(owner_client, order, ali):
    scarf = OrderItem.objects.create(
        order=order,
        name="Scarf",
        type=Product.READY_MADE,
        price=D("300"),
        usual_price=D("300"),
    )
    log(ali, add_rework(scarf, ali, finished_at=timezone.now()), 40)
    assert "Ready-made + 40m rework" in page(owner_client, order)


def test_rework_detail():
    def total(count):
        return costing.ReworkTotal(count, 0, 65, D(109), D(33), D(142), False, False)

    assert rework_detail(total(2)) == "2 reworks · 1h 05m · staff ₹109 · materials ₹33"
    assert rework_detail(total(1)).startswith("1 rework · ")


def test_rework_state():
    assert rework_state(True, 40, True) == "finished"
    assert rework_state(False, 10, True) == "in_progress"
    assert rework_state(False, 0, False) == "not_started"


def add_rework(item, ali, **kw):
    return Rework.objects.create(
        item=item, assignee=ali, reason="fit", note="Loosen", **kw
    )


def log(ali, rework, minutes):
    now = timezone.now()
    TimeSession.objects.create(
        employee=ali,
        rework=rework,
        started_at=now - timedelta(minutes=minutes),
        ended_at=now,
    )


def page(client, order):
    return client.get(f"/orders/{order.pk}/").content.decode()


def test_order_delivered_with_reworks_shows_section(owner_client, order, item, ali):
    OrderItem.objects.filter(pk=item.pk).update(status="finished")
    now = timezone.now()
    TimeSession.objects.create(
        employee=ali,
        item=item,
        started_at=now - timedelta(hours=5),
        ended_at=now - timedelta(hours=5) + timedelta(minutes=185),
    )
    done = add_rework(item, ali, finished_at=now)
    log(ali, done, 40)
    open_one = add_rework(item, ali)
    log(ali, open_one, 20)
    html = page(owner_client, order)
    for text in (
        "Rework after delivery",
        "R1",
        "R2",
        "Rework open",
        "3h 05m + 1h rework",
        "Gain at delivery",
        "Gain on this order after rework",
        reverse("rework_record", args=[done.pk]),
        reverse("rework_record", args=[open_one.pk]),
    ):
        assert text in html
    assert 'class="item-row"' in html


def test_order_stays_delivered_until_reworks_finished(owner_client, order, item, ali):
    rework = add_rework(item, ali)
    assert "Rework open" in page(owner_client, order)
    now = timezone.now()
    timing.start_rework(ali, rework, now)
    assert Order.objects.get(pk=order.pk).status == "delivered"
    timing.finish_rework(ali, rework, now + timedelta(minutes=30))
    html = page(owner_client, order)
    assert Order.objects.get(pk=order.pk).status == "delivered"
    assert "Rework open" not in html
    assert "R1" in html


def test_delivered_no_reworks_empty_state(owner_client, order):
    html = page(owner_client, order)
    assert "No reworks after delivery." in html
    assert "Rework open" not in html


def test_ready_order_without_reworks_not_folded(owner_client, customer):
    order = make_order(customer, 2, status="ready")
    html = page(owner_client, order)
    assert 'class="item-row"' not in html
    assert "Rework after delivery" not in html


def test_ready_order_with_rework_is_folded(owner_client, customer, ali):
    order = make_order(customer, 2, status="ready")
    add_rework(order.items.get(), ali)
    html = page(owner_client, order)
    assert 'class="item-row"' in html
    assert "Rework after delivery" in html


def test_open_order_has_no_section(owner_client, customer):
    html = page(owner_client, make_order(customer, 3, status="in_progress"))
    assert "Rework after delivery" not in html


def test_invoice_unchanged_by_reworks(owner_client, order, item, ali, cream):
    Payment.objects.create(
        order=order, amount=D("500"), date=date(2026, 11, 1), method="cash"
    )
    import re

    def invoice_text(html):
        return re.sub(
            r"\s+", " ", html.split('id="order-invoice"')[1].split("</section>")[0]
        )

    before = invoice_text(page(owner_client, order))
    payments = Payment.objects.count()
    rework = add_rework(item, ali)
    MaterialLine.objects.create(
        rework=rework,
        product=cream,
        name=cream.name,
        unit="m",
        quantity=D("0.25"),
        cost_price=D("120"),
        selling_price=D("150"),
        on_bill=False,
    )
    log(ali, rework, 40)
    assert invoice_text(page(owner_client, order)) == before
    assert Payment.objects.count() == payments


def test_item_cost_card_subtracts_rework(order, item, ali):
    other = OrderItem.objects.create(
        order=order, name="Skirt", type=Product.CUSTOM, price=D(500), usual_price=D(500)
    )
    now = timezone.now()
    before = item_cost_card(item, now)
    assert before["reworks"] is None
    rework = add_rework(item, ali, finished_at=now)
    log(ali, rework, 60)
    add_rework(other, ali, finished_at=now)
    card = item_cost_card(item, now)
    r = card["reworks"]
    assert r["total"].cost == D(100)
    assert r["gain_after"] == before["item"].gain - D(100)
    assert r["shop_cost"] == before["item"].cost + D(100)


def test_cost_card_rework_has_no_running_share(order, item, ali):
    rework = add_rework(item, ali, finished_at=timezone.now())
    log(ali, rework, 60)
    card = cost_card(order, timezone.now())
    assert card["reworks"]["total"].cost == D(100)
    assert card["reworks"]["gain_after"] == card["total"].gain - D(100)
    assert card["reworks_estimated"] is False
    assert cost_card(order, timezone.now())["reworks"]["detail"].startswith("1 rework")
