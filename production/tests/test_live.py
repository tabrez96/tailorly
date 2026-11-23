from datetime import datetime, timedelta

import pytest
from django.contrib.auth.models import Group, User
from django.test import Client
from django.utils import timezone

from orders.models import Order, OrderItem
from production import live
from production.models import TimeSession
from production.tests.conftest import PARTIAL
from staff.models import DayRecord, Employee

pytestmark = pytest.mark.django_db


@pytest.fixture
def owner():
    user = User.objects.create_user("owner", password="x")
    user.groups.add(Group.objects.get_or_create(name="owner")[0])
    client = Client()
    client.force_login(user)
    return client


def card(employee, now=None):
    return live.employee_card(employee, now or timezone.now(), "")


def run(item, employee, minutes, now, closed=False):
    started = now - timedelta(minutes=minutes)
    return TimeSession.objects.create(
        employee=employee,
        item=item,
        started_at=started,
        ended_at=now if closed else None,
    )


def waiting(customer, number, days):
    order = Order.objects.create(
        customer=customer,
        number=number,
        status="open",
        due_date=timezone.localdate() + timedelta(days=days),
    )
    OrderItem.objects.create(
        order=order, name="Anarkali", type="custom", price=1, usual_price=1
    )
    return order


@pytest.mark.parametrize(
    ("day", "hero", "expected"),
    [
        ("not_started", None, live.NOT_IN),
        ("not_started", "running", live.WORKING),
        ("started", "running", live.WORKING),
        ("ended", "running", live.WORKING),
        ("started", "paused", live.PAUSED),
        ("started", None, live.IDLE),
        ("ended", None, live.GONE),
        ("ended", "paused", live.GONE),
    ],
)
def test_card_state_table(day, hero, expected):
    assert live.card_state(day, hero) == expected


def test_minutes_left_text():
    assert live.minutes_left_text(72, 165) == ("1h 33m left", False)
    assert live.minutes_left_text(165, 165) == ("0m left", False)
    assert live.minutes_left_text(185, 165) == ("20m over", True)


def test_bar_percent():
    assert live.bar_percent(0, 100) == 0
    assert live.bar_percent(50, 100) == 50
    assert live.bar_percent(150, 100) == 100
    assert live.bar_percent(10, 0) == 100


def local_noon():
    day = timezone.localdate()
    return timezone.make_aware(datetime(day.year, day.month, day.day, 12))


def test_working_card(ali, make_item, started_day):
    started_day(ali)
    item = make_item(ali, estimate=165)
    now = local_noon()
    session = run(item, ali, 72, now)
    c = card(ali, now)
    assert c["state"] == live.WORKING
    assert c["chip_label"] == "Working"
    assert c["item"]["title"] == f"Blouse · #{item.order.number}"
    assert c["item"]["minutes_text"] == "1h 12m"
    assert c["item"]["left_text"] == "1h 33m left"
    assert live.format_clock(session.started_at) in c["item"]["since"]
    assert c["give_url"] == ""


def test_working_over_estimate(ali, make_item, started_day):
    started_day(ali)
    item = make_item(ali, estimate=165)
    now = local_noon()
    run(item, ali, 185, now)
    c = card(ali, now)["item"]
    assert c["left_text"] == "20m over"
    assert c["over"] is True
    assert c["percent"] == 100


def test_paused_card(ali, make_item, started_day):
    started_day(ali)
    item = make_item(ali, estimate=165)
    now = local_noon()
    closed = run(item, ali, 30, now - timedelta(minutes=1), closed=True)
    c = card(ali, now)
    assert c["chip_label"] == "Paused"
    assert c["item"]["sub"].startswith(
        f"Paused at {live.format_clock(closed.ended_at)}"
    )
    assert "logged of est." in c["item"]["sub"]
    assert "base_seconds" not in c["item"]


def test_paused_card_without_earlier_closed_session_in_hero(
    ali, make_item, started_day, monkeypatch
):
    # The hero's own session list may lag a pause; paused_at must not depend on it.
    started_day(ali)
    item = make_item(ali, estimate=165)
    now = local_noon()
    closed = run(item, ali, 30, now - timedelta(minutes=1), closed=True)
    real = live.panel

    def stale(employee, at):
        data = real(employee, at)
        data["hero"]["sessions"] = []
        return data

    monkeypatch.setattr(live, "panel", stale)
    sub = card(ali, now)["item"]["sub"]
    assert sub.startswith(f"Paused at {live.format_clock(closed.ended_at)}")


def test_idle_card(ali, make_item, started_day):
    started_day(ali)
    c = card(ali)
    assert c["chip_label"] == "Not timing anything"
    assert c["chip_tone"] == "warn"
    assert c["item"] is None


def test_not_in_yet_card(ali, make_item):
    make_item(ali)
    c = live.employee_card(ali, timezone.now(), "/x/")
    assert c["chip_label"] == "Not in yet"
    assert c["rows_label"] == "FIRST UP FOR ALI"
    assert c["start_day_url"]
    assert c["give_url"] == ""
    assert "queue is ready" in c["note"]


def test_not_in_yet_empty_queue(ali):
    assert card(ali)["note"].startswith("Nothing in Ali's queue yet.")


def test_gone_home_card(ali, make_item, started_day):
    day = timezone.localdate()
    end = timezone.make_aware(datetime(day.year, day.month, day.day, 18, 10))
    started_day(ali, end=end)
    make_item(ali)
    make_item(ali, name="Suit")
    c = card(ali, end + timedelta(hours=1))
    assert c["chip_label"] == "Gone home 6:10 pm"
    assert c["rows_label"] == "FIRST UP TOMORROW"
    assert len(c["rows"]) == 1
    assert c["note"].endswith("logged today.")


def test_cards_sorted_working_first(ali, make_item, started_day, customer):
    zed = Employee.objects.create(name="Zed Roy", phone="9000011118", daily_wage=800)
    started_day(zed)
    item = make_item(zed)
    run(item, zed, 10, timezone.now())
    cards = live.live_context(timezone.now())["cards"]
    assert [c["first"] for c in cards] == ["Zed", "Ali"]


def test_up_next_two_rows_and_moved_by_you(ali, make_item, started_day):
    started_day(ali)
    items = [
        make_item(ali, due=timezone.localdate() + timedelta(days=n))
        for n in (1, 2, 3, 4)
    ]
    items[3].queue_rank = 1
    items[3].save()
    rows = card(ali)["rows"]
    assert len(rows) == 2
    assert rows[0]["line"].endswith("moved by you")
    assert rows[0]["chip_label"] == "Next up"
    assert rows[1]["chip_label"] == "Not started"


def test_give_work_only_while_orders_wait(ali, customer, started_day):
    started_day(ali)
    assert live.live_context(timezone.now())["cards"][0]["give_url"] == ""
    later = waiting(customer, 5, 6)
    earlier = waiting(customer, 6, 2)
    url = live.live_context(timezone.now())["cards"][0]["give_url"]
    assert (
        url
        == f"/production/plan/assign/{earlier.pk}/?from=production&employee={ali.pk}"
    )
    assert later.pk != earlier.pk


def test_production_page_renders(owner, ali, customer):
    waiting(customer, 5, 3)
    html = owner.get("/production/").content.decode()
    for text in ("Right now", "Waiting for someone", "Work plan", "1 item"):
        assert text in html
    assert owner.get("/production/", headers=PARTIAL).status_code == 200


def test_production_page_empty_staff(owner):
    html = owner.get("/production/").content.decode()
    assert "Add someone in Staff to start giving out work." in html
    assert "Add employee" in html


def test_waiting_empty_text(owner, ali):
    html = owner.get("/production/").content.decode()
    assert "Every order has someone making it." in html


def test_production_now_fragment(owner, ali):
    html = owner.get("/production/now/").content.decode()
    assert 'id="right-now"' in html
    assert "<html" not in html


def test_start_day_records_day_start(owner, ali):
    url = f"/production/employees/{ali.pk}/day/start/"
    response = owner.post(url, headers=PARTIAL)
    assert response.status_code == 200
    assert "Not in yet" not in response.content.decode()
    record = DayRecord.objects.get(employee=ali, date=timezone.localdate())
    assert record.start
    owner.post(url, headers=PARTIAL)
    assert DayRecord.objects.filter(employee=ali).count() == 1


def test_start_day_unknown_employee(owner):
    assert owner.post("/production/employees/999/day/start/").status_code == 404


def test_owner_only(ali):
    for url, method in (
        ("/production/", ali.client.get),
        ("/production/now/", ali.client.get),
        (f"/production/employees/{ali.pk}/day/start/", ali.client.post),
    ):
        assert method(url).status_code != 200
    assert not DayRecord.objects.exists()


def test_assign_from_production_returns_there(owner, ali, customer):
    order = waiting(customer, 7, 4)
    response = owner.post(
        f"/production/plan/assign/{order.pk}/",
        {"from": "production", "employee": ali.pk, "place": "suggested"}
        | {f"estimate_{i.pk}": "1h" for i in order.items.all()},
        headers=PARTIAL,
    )
    assert response.status_code == 204, response.content
    assert "/production/" in response["HX-Location"]
    assert "/plan/" not in response["HX-Location"]


def test_work_plan_back_goes_to_production(owner, ali):
    html = owner.get("/production/plan/").content.decode()
    assert 'href="/production/"' in html
