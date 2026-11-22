from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from accounts.roles import OWNER, add_to_role
from orders.models import Order, OrderItem
from production import timing
from production.plan import plan_context
from production.timing import queue_rows
from staff.models import Employee

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 11, 22, 6, 0, tzinfo=UTC)
URL = "/production/plan/"


@pytest.fixture
def owner(client):
    user = User.objects.create_user("owner", password="x")
    add_to_role(user, OWNER)
    client.force_login(user)
    return client


def timezone_day(n):
    return timezone.localdate() + timedelta(days=n)


def day(n):
    return date(2026, 11, 22) + timedelta(days=n)


def test_owner_sees_queue_in_suggested_order(owner, ali, make_item):
    make_item(ali, name="Aaa", due=day(5), estimate=60)
    make_item(ali, name="Bbb", due=day(6), estimate=60)
    c = make_item(ali, name="Ccc", due=day(7), estimate=60)
    c.queue_rank = 1
    c.save()
    html = owner.get(URL).content.decode()
    assert [html.index(n) for n in ("Ccc", "Aaa", "Bbb")] == sorted(
        html.index(n) for n in ("Ccc", "Aaa", "Bbb")
    )
    assert html.count("Moved by you") == 1


def test_queue_row_shows_item_photo(owner, ali, make_item, add_photos):
    item = make_item(ali, name="Photoed", due=day(5), estimate=60)
    add_photos(item, 1)
    row = plan_context(NOW)["sections"][0]["rows"][0]
    url = reverse("item_photo_thumb", args=[item.photos.first().pk])
    assert row["photo"] == url
    assert url in owner.get(URL).content.decode()


def test_s08_and_s16_same_order(ali, make_item, make_rework):
    a = make_item(ali, due=day(3))
    b = make_item(ali, due=day(1))
    c = make_item(ali, due=day(2))
    c.status = OrderItem.IN_PROGRESS
    c.save()
    b.queue_rank = 2
    b.save()
    make_rework(a, ali, due=day(1))
    full = [r["key"] for r in queue_rows(ali, NOW)]
    plan = [r["key"] for r in plan_context(NOW)["sections"][0]["rows"]]
    up_next = [r["key"] for r in timing.panel(ali, NOW)["up_next"]]
    assert plan == full == up_next


def test_late_risk_chip_and_hero_sentence(owner, ali, make_item):
    make_item(ali, due=day(-1), estimate=60)
    html = owner.get(URL).content.decode()
    assert "Late risk" in html
    assert "1 item won&#x27;t make its due date." in html or (
        "1 item won't make its due date." in html
    )


def test_not_assigned_and_assign_pill(owner, ali, make_item):
    make_item(ali, estimate=60)
    html = owner.get(URL).content.decode()
    assert "Not assigned" not in html
    assert "header__action" not in html
    waiting = make_item(None, due=day(2))
    Order.objects.filter(pk=waiting.order_id).update(paid_by=Order.FREE)
    html = owner.get(URL).content.decode()
    assert "Not assigned" in html
    assert "Free" in html
    assert "header__action" in html


def test_nothing_to_plan(owner, ali):
    html = owner.get(URL).content.decode()
    assert "Nothing to plan" in html
    assert 'href="/orders/new/"' in html


def test_empty_employee_queue(owner, ali, make_item):
    Employee.objects.create(name="Sana Shah", phone="9000011118", daily_wage=800)
    make_item(ali, estimate=60)
    html = owner.get(URL).content.decode()
    assert "Nothing in Sana&#x27;s queue yet." in html or (
        "Nothing in Sana's queue yet." in html
    )


def test_due_bold_within_two_days(owner, ali, make_item):
    make_item(ali, due=timezone_day(2), estimate=60)
    assert "qrow__due--soon" in owner.get(URL).content.decode()
    OrderItem.objects.all().delete()
    Order.objects.all().delete()
    make_item(ali, due=timezone_day(3), estimate=60)
    assert "qrow__due--soon" not in owner.get(URL).content.decode()


def test_employee_cannot_open(ali):
    response = ali.client.get(URL)
    assert response.status_code == 302


def test_no_handle_on_readonly_rows(owner, ali, make_item):
    make_item(ali, estimate=60)
    assert "qrow__handle" not in owner.get(URL).content.decode()


def test_rework_row_shows_chip_and_reason(owner, ali, make_item, make_rework):
    item = make_item(ali)
    make_rework(item, ali, due=day(2))
    html = owner.get(URL).content.decode()
    assert "Rework" in html
    assert "Fit" in html


def test_unassigned_groups_custom_items(make_item):
    first = make_item(None, name="Kurta", due=day(2))
    OrderItem.objects.create(
        order=first.order, name="Pant", type="custom", price=Decimal(1), usual_price=1
    )
    OrderItem.objects.create(
        order=first.order,
        name="Hat",
        type="ready_made",
        price=Decimal(1),
        usual_price=1,
    )
    [row] = plan_context(NOW)["unassigned"]
    assert row["garment"] == "Kurta and 1 more"
