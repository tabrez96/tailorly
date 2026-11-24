from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.http import QueryDict
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
