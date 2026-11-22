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
    started_day(ali)
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
