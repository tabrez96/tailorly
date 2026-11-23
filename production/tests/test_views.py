import json
import re
from datetime import timedelta

import pytest
from django.contrib.auth.models import Group, User
from django.test import Client
from django.utils import timezone

from orders.models import OrderItem, Payment
from production import timing
from production.models import TimeSession
from production.tests.conftest import PARTIAL

pytestmark = pytest.mark.django_db


def post(client, url):
    return client.post(url, headers=PARTIAL)


def start(item):
    return f"/my-work/items/{item.pk}/start/"


def test_start_before_day_does_nothing(ali, make_item):
    item = make_item(ali)
    response = post(ali.client, start(item))
    assert response.status_code == 200
    assert TimeSession.objects.count() == 0
    assert json.loads(response["HX-Trigger"])["toast"]["message"] == (
        "Start your day first."
    )


def test_switch_in_one_request(ali, make_item, started_day):
    started_day(ali)
    a, b = make_item(ali), make_item(ali, name="Suit")
    post(ali.client, start(a))
    html = post(ali.client, start(b)).content.decode()
    assert a.sessions.get().ended_at is not None
    assert b.sessions.get().ended_at is None
    assert "Now working on" in html
    assert "#2 · Suit" in html


def test_pause_and_resume(ali, make_item, started_day):
    started_day(ali)
    item = make_item(ali)
    post(ali.client, start(item))
    html = post(ali.client, "/my-work/pause/").content.decode()
    assert "Paused" in html
    assert "Resume" in html
    assert timing.open_session(ali) is None
    post(ali.client, start(item))
    assert timing.open_session(ali).item == item
    assert item.sessions.count() == 2


def test_end_my_day_stops_running_timer(ali, make_item, started_day):
    started_day(ali)
    item = make_item(ali)
    post(ali.client, start(item))
    html = post(ali.client, "/my-work/day/end/").content.decode()
    assert timing.open_session(ali) is None
    assert "Day ended at" in html
    assert "Paused" not in html


def test_start_my_day_closes_yesterdays_session(ali, make_item):
    item = make_item(ali)
    start_at = timezone.now() - timedelta(days=1)
    TimeSession.objects.create(employee=ali, item=item, started_at=start_at)
    post(ali.client, "/my-work/day/start/")
    assert item.sessions.get().ended_at == start_at
    assert ali.days.count() == 1


def test_owner_day_end_stops_timer(ali, make_item, started_day):
    started_day(ali)
    item = make_item(ali)
    post(ali.client, start(item))
    user = User.objects.create_user("owner", password="x")
    user.groups.add(Group.objects.get_or_create(name="owner")[0])
    owner = Client()
    owner.force_login(user)
    today = timezone.localdate().isoformat()
    owner.post(f"/settings/staff/{ali.pk}/days/{today}/end/", headers=PARTIAL)
    assert timing.open_session(ali) is None


def test_other_employees_item_404(ali, make_item, started_day, db):
    started_day(ali)
    other = make_item(None)
    assert post(ali.client, start(other)).status_code == 404
    assert post(ali.client, f"/my-work/items/{other.pk}/finish/").status_code == 404


def test_get_not_allowed(ali, make_item):
    item = make_item(ali)
    assert ali.client.get(start(item)).status_code == 405
    assert ali.client.get("/my-work/pause/").status_code == 405


def test_finish_item(ali, make_item, started_day):
    started_day(ali)
    item = make_item(ali)
    post(ali.client, start(item))
    response = post(ali.client, f"/my-work/items/{item.pk}/finish/")
    html = response.content.decode()
    item.refresh_from_db()
    assert item.status == OrderItem.FINISHED
    assert "Finished today" in html
    assert "0m" in html
    assert "Now working on" not in html
    assert timing.open_session(ali) is None


def test_nothing_assigned(ali, started_day):
    started_day(ali)
    html = ali.client.get("/my-work/").content.decode()
    assert "Nothing assigned to you right now." in html


def test_not_started_buttons_disabled(ali, make_item):
    make_item(ali)
    html = ali.client.get("/my-work/").content.decode()
    assert "Start your day first, then you can start an item." in html
    row = html[html.index("work-row") :]
    assert "disabled" in row[: row.index("</li>")]


def test_page_without_employee_record(db):
    user = User.objects.create_user("lonely", password="x")
    client = Client()
    client.force_login(user)
    assert client.get("/my-work/").status_code == 200


def test_no_money_or_estimates_on_employee_pages(ali, make_item, started_day):
    day = started_day(ali)
    a = make_item(ali, price="1450", estimate=137)
    b = make_item(ali, name="Suit", price="1450", estimate=137)
    Payment.objects.create(
        order=a.order, amount=500, date=timezone.localdate(), method="cash"
    )
    pages = [ali.client.get("/my-work/").content.decode()]
    pages.append(post(ali.client, start(a)).content.decode())
    pages.append(post(ali.client, start(b)).content.decode())
    pages.append(post(ali.client, "/my-work/pause/").content.decode())
    pages.append(post(ali.client, f"/my-work/items/{b.pk}/finish/").content.decode())
    pages.append(post(ali.client, "/my-work/day/end/").content.decode())
    # Fix the day to 8 hours so the pay shown is ₹800 whatever time the test runs.
    day.refresh_from_db()
    day.end = day.start + timedelta(hours=8)
    day.save(update_fields=["end"])
    pay = ali.client.get("/my-pay/").content.decode().lower()
    # "estimate" is the pay week wording there, so check the item values instead.
    for word in ("1,450", "1450", "2h 17m", "137"):
        assert word not in pay
    for html in pages:
        lowered = html.lower()
        for bad in ("₹", "1,450", "2h 17m", "balance", "profit", "estimate"):
            assert bad not in lowered, bad
        # Numbers are checked in visible text only: tokens in attributes are random.
        text = re.sub(r"<[^>]*>", " ", html)
        assert not re.search(r"\b(1450|137)\b", text)


MONEY_WORDS = ["₹", "estimate", "balance", "cost", "gain", "profit"]
MONEY_NUMBERS = ["1,450", "1450", "7,315", "7315", "8,642", "8642"]


def assert_no_money(html, where=""):
    low = html.lower()
    for word in MONEY_WORDS:
        assert word.lower() not in low, (where, word)
    for number in MONEY_NUMBERS:
        assert not re.search(rf"(?<![\w.,]){re.escape(number)}(?![\w,]|\.\d)", html), (
            where,
            number,
        )


def delivered_rework(make_item, make_rework, ali, **kwargs):
    item = make_item(ali, estimate=90)
    OrderItem.objects.filter(pk=item.pk).update(status="finished")
    item.order.status = "delivered"
    item.order.save()
    return make_rework(item, ali, **kwargs)


def rework_url(rework, action):
    return f"/my-work/reworks/{rework.pk}/{action}/"


def test_rework_start_and_finish_views(ali, make_item, make_rework, started_day):
    started_day(ali)
    rework = delivered_rework(make_item, make_rework, ali)
    assert post(ali.client, rework_url(rework, "start")).status_code == 200
    assert timing.open_session(ali).rework == rework
    response = post(ali.client, rework_url(rework, "finish"))
    assert response.status_code == 200
    assert (
        "Rework · Blouse finished"
        in json.loads(response["HX-Trigger"])["toast"]["message"]
    )
    rework.refresh_from_db()
    assert rework.finished_at is not None


def test_rework_start_other_employee_404(ali, make_item, make_rework, started_day):
    from staff.models import Employee

    started_day(ali)
    other = Employee.objects.create(name="Sam", phone="9000011118", daily_wage=800)
    rework = delivered_rework(make_item, make_rework, other)
    assert post(ali.client, rework_url(rework, "start")).status_code == 404
    assert post(ali.client, rework_url(rework, "finish")).status_code == 404


def test_rework_start_before_day_toast(ali, make_item, make_rework):
    rework = delivered_rework(make_item, make_rework, ali)
    response = post(ali.client, rework_url(rework, "start"))
    assert (
        json.loads(response["HX-Trigger"])["toast"]["message"]
        == "Start your day first."
    )
    response = post(ali.client, rework_url(rework, "finish"))
    assert (
        json.loads(response["HX-Trigger"])["toast"]["message"]
        == "Start your day first."
    )
    assert TimeSession.objects.count() == 0


def test_finished_rework_start_404(ali, make_item, make_rework, started_day):
    started_day(ali)
    rework = delivered_rework(make_item, make_rework, ali)
    timing.start_rework(ali, rework, timezone.now())
    timing.finish_rework(ali, rework, timezone.now())
    assert post(ali.client, rework_url(rework, "start")).status_code == 404


def test_hero_rework_html(ali, make_item, make_rework, started_day):
    started_day(ali)
    rework = delivered_rework(make_item, make_rework, ali)
    html = post(ali.client, rework_url(rework, "start")).content.decode()
    assert "Rework · Blouse" in html
    assert "Fit alteration" in html
    assert "Loosen waist by 1 inch" in html
    assert "Photos, measurements and notes" in html
    assert f"/my-work/reworks/{rework.pk}/details/" in html


def test_hint_text(ali, make_item, started_day):
    started_day(ali)
    make_item(ali)
    make_item(ali, name="Suit")
    html = ali.client.get("/my-work/").content.decode()
    assert "Tap a photo for details. Switching pauses what you" in html


def test_rows_have_rework_chip(ali, make_item, make_rework, started_day):
    started_day(ali)
    queued = delivered_rework(make_item, make_rework, ali)
    done = delivered_rework(make_item, make_rework, ali)
    html = ali.client.get("/my-work/").content.decode()
    assert html.count("Rework") >= 2
    timing.start_rework(ali, done, timezone.now())
    timing.finish_rework(ali, done, timezone.now())
    html = ali.client.get("/my-work/").content.decode()
    assert "Finished today" in html
    finished_part = html.split("Finished today")[1]
    assert "Rework" in finished_part
    assert queued.pk


def test_no_money_in_my_work_html(ali, make_item, make_rework, started_day):
    from orders.models import MaterialLine

    started_day(ali)
    make_item(ali, estimate=90)
    rework = delivered_rework(make_item, make_rework, ali)
    MaterialLine.objects.create(
        rework=rework,
        name="Lining",
        unit="m",
        quantity=1,
        cost_price=7315,
        selling_price=8642,
    )
    post(ali.client, rework_url(rework, "start"))
    html = ali.client.get("/my-work/").content.decode()
    assert_no_money(html)
