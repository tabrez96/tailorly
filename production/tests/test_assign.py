import re
from datetime import UTC, date, datetime, timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from accounts.roles import OWNER, add_to_role
from orders.models import Order, OrderItem
from production.assign import (
    NEXT,
    SUGGESTED,
    next_up_rank,
    place_rows,
    read_estimates,
    suggested_lines,
    suggestion,
    usual_hint,
)
from production.models import TimeSession
from production.timing import queue_rows
from staff.models import Employee

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 11, 22, 6, 0, tzinfo=UTC)


def d(n):
    return date(2026, 11, 22) + timedelta(days=n)


def row(pk, due=None, need=60, started=False, moved_to=None):
    return {
        "key": ("item", pk),
        "due": due,
        "need": need,
        "estimate": need,
        "started": started,
        "moved_to": moved_to,
        "item": None,
    }


def keys(rows):
    return [r["key"][1] for r in rows]


@pytest.fixture
def owner(client):
    user = User.objects.create_user("owner", password="x")
    add_to_role(user, OWNER)
    client.force_login(user)
    return client


@pytest.fixture
def sana(db):
    return Employee.objects.create(
        name="Sana Begum", phone="9000011118", daily_wage=800
    )


def url(order, query=""):
    return f"/production/plan/assign/{order.pk}/{query}"


def test_next_up_rank():
    assert next_up_rank([]) == 1
    assert next_up_rank([row(1), row(2)]) == 1
    assert next_up_rank([row(1, started=True), row(2)]) == 2
    assert next_up_rank([row(1, started=True), row(2), row(3, started=True)]) == 4


def test_place_rows_suggested_follows_queue_rule():
    queue = [row(1, d(3)), row(2, d(9))]
    placed = place_rows(queue, [row(3, d(5))], SUGGESTED)
    assert keys(placed) == [1, 3, 2]


def test_place_rows_next_up_after_started_item():
    queue = [row(1, d(8), started=True), row(2, d(1)), row(3, d(2))]
    placed = place_rows(queue, [row(4, d(9))], NEXT)
    assert keys(placed) == [1, 4, 2, 3]


def test_place_rows_next_up_shifts_existing_moves():
    queue = [row(1, d(8), started=True), row(2, d(1)), row(3, d(2), moved_to=2)]
    placed = place_rows(queue, [row(4, d(9))], NEXT)
    assert keys(placed) == [1, 4, 3, 2]


def test_suggestion_position_before_and_ready():
    queue = [row(1, d(1), need=300), row(2, d(9), need=300)]
    found = suggestion(queue, [row(3, d(2), need=300)], d(0))
    assert found["position"] == 2
    assert found["before"]["key"] == ("item", 1)
    assert found["ready"] == d(1)  # 600 minutes needs a second day
    first = suggestion(queue, [row(3, d(0), need=60)], d(0))
    assert first["position"] == 1 and first["before"] is None
    assert first["ready"] == d(0)
    exact = suggestion([], [row(3, d(2), need=480)], d(0))
    assert exact["ready"] == d(0)


def test_suggested_lines():
    ready = date(2026, 11, 17)
    assert suggested_lines(6, "Chudidar", ready) == (
        "Suggested: 6th",
        "After the chudidar, ready by Tue 17 Nov",
    )
    assert (
        suggested_lines(1, None, ready)[1] == "First in the queue, ready by Tue 17 Nov"
    )


def test_usual_hint():
    assert usual_hint("Anarkali", 190, 10) == (
        "Usually 3h 10m for an anarkali (last 10). "
        "Used for the queue and in Production."
    )
    assert usual_hint("Blouse", 90, 4).startswith(
        "Usually 1h 30m for a blouse (last 4)"
    )
    assert usual_hint("Anarkali", 120, 2) == (
        "No finished anarkali to go by yet, so it starts at 2h. "
        "Used for the queue and in Production."
    )


def test_read_estimates(ali, make_item):
    waiting = make_item(None)
    started = make_item(None)
    started.status = OrderItem.IN_PROGRESS
    started.save()
    items = [waiting, started]
    assert read_estimates(items, {f"estimate_{waiting.pk}": "3h 30m"}) == (
        {waiting.pk: 210},
        {},
    )
    _, errors = read_estimates(items, {f"estimate_{waiting.pk}": " "})
    assert errors[waiting.pk] == "Enter how long it takes, like 2h 30m."
    _, errors = read_estimates(items, {f"estimate_{waiting.pk}": "soon"})
    assert waiting.pk in errors
    estimates, errors = read_estimates([started], {f"estimate_{started.pk}": "9h"})
    assert estimates == errors == {}


def test_sheet_get_prefills_usual_time(owner, ali, sana, make_item):
    item = make_item(None, due=d(5), name="Blouse")
    html = owner.get(url(item.order)).content.decode()
    assert "Who makes it" in html
    assert "Ali Khan" in html and "Sana Begum" in html
    assert 'value="2h"' in html
    assert 'id="assign-place-suggested"' in html
    assert "Assign to Ali" in html
    assert "Nothing in the queue yet" in html
    assert "Next up" in html


def test_sheet_started_item_estimate_fixed(owner, ali, make_item):
    item = make_item(None, estimate=90)
    item.status = OrderItem.IN_PROGRESS
    item.save()
    html = owner.get(url(item.order)).content.decode()
    assert "fixed once started" in html
    assert f'name="estimate_{item.pk}"' not in html
    response = owner.post(
        url(item.order),
        {"employee": ali.pk, "place": SUGGESTED, f"estimate_{item.pk}": "5h"},
    )
    assert response.status_code == 204
    item.refresh_from_db()
    assert item.estimate_minutes == 90


def test_assign_suggested_saves_assignee_and_estimate(owner, ali, make_item):
    item = make_item(None, due=d(5))
    item.queue_rank = 3
    item.save()
    response = owner.post(
        url(item.order),
        {"employee": ali.pk, "place": SUGGESTED, f"estimate_{item.pk}": "3h 30m"},
    )
    assert response.status_code == 204
    assert "/production/plan/" in response["HX-Location"]
    item.refresh_from_db()
    assert item.order.assignee == ali
    assert item.estimate_minutes == 210
    assert item.queue_rank is None
    assert "assigned to Ali" in response["HX-Trigger"]


def test_assign_next_up_after_started_item(owner, ali, make_item):
    running = make_item(ali, due=d(1), estimate=60)
    running.status = OrderItem.IN_PROGRESS
    running.save()
    other = make_item(ali, due=d(2), estimate=60)
    other.queue_rank = 2
    other.save()
    item = make_item(None, due=d(9))
    owner.post(
        url(item.order),
        {"employee": ali.pk, "place": NEXT, f"estimate_{item.pk}": "1h"},
    )
    item.refresh_from_db()
    other.refresh_from_db()
    assert item.queue_rank == 2
    assert other.queue_rank == 3
    rows = queue_rows(ali, timezone.now())
    assert [r["item"].pk for r in rows] == [running.pk, item.pk, other.pk]


def test_reassign_from_order_stops_old_timer(owner, ali, sana, make_item):
    item = make_item(ali, estimate=60)
    item.status = OrderItem.IN_PROGRESS
    item.save()
    session = TimeSession.objects.create(
        employee=ali, item=item, started_at=timezone.now() - timedelta(minutes=5)
    )
    response = owner.post(
        url(item.order),
        {"employee": sana.pk, "place": SUGGESTED, "from": "order"},
    )
    assert response.status_code == 204
    session.refresh_from_db()
    assert session.ended_at is not None
    item.order.refresh_from_db()
    assert item.order.assignee == sana
    assert f"/orders/{item.order.pk}/" in response["HX-Location"]


def test_sheet_maker_param_preselects(owner, ali, sana, make_item):
    item = make_item(None)
    html = owner.get(url(item.order, f"?employee={sana.pk}")).content.decode()
    assert "Assign to Sana" in html
    assert re.search(rf'id="assign-maker-{sana.pk}"[^>]*\bchecked', html)
    assert not re.search(rf'id="assign-maker-{ali.pk}"[^>]*\bchecked', html)


def test_sheet_change_defaults_to_current_maker_and_next(owner, ali, sana, make_item):
    item = make_item(sana)
    item.queue_rank = 1
    item.save()
    html = owner.get(url(item.order, "?from=order")).content.decode()
    assert "Assign to Sana" in html
    assert 'value="from"' not in html and 'value="order"' in html
    assert 'id="assign-place-next"' in html


def test_sheet_404_for_draft_or_ready_made_order(owner, ali, customer, make_item):
    ready_made = make_item(None, kind="ready_made")
    delivered = make_item(None, status="delivered")
    draft = Order.objects.create(customer=customer)
    for order in (draft, ready_made.order, delivered.order):
        assert owner.get(url(order)).status_code == 404
        assert owner.post(url(order), {"employee": ali.pk}).status_code == 404


def test_order_with_only_finished_custom_items_is_not_assignable(owner, ali, make_item):
    item = make_item(None)
    OrderItem.objects.filter(pk=item.pk).update(status=OrderItem.FINISHED)
    assert owner.get(url(item.order)).status_code == 404
    assert owner.post(url(item.order), {"employee": ali.pk}).status_code == 404
    html = owner.get("/production/plan/?assign=next").content.decode()
    assert url(item.order) not in html


def test_assign_reassigned_meanwhile_rerenders_422(owner, ali, make_item, monkeypatch):
    import production.views as views

    item = make_item(None)
    sana = Employee.objects.create(name="Sana", active=True)
    real = views.assign

    def racing(order, *args):
        Order.objects.filter(pk=order.pk).update(assignee=sana)
        return real(order, *args)

    monkeypatch.setattr(views, "assign", racing)
    response = owner.post(
        url(item.order), {"employee": ali.pk, f"estimate_{item.pk}": "2h"}
    )
    assert response.status_code == 422
    assert "This order just changed" in response.content.decode()
    item.order.refresh_from_db()
    assert item.order.assignee == sana


def test_sheet_invalid_estimate_422(owner, ali, make_item):
    item = make_item(None)
    response = owner.post(
        url(item.order), {"employee": ali.pk, f"estimate_{item.pk}": ""}
    )
    assert response.status_code == 422
    html = response.content.decode()
    assert "Enter how long it takes" in html
    assert 'aria-invalid="true"' in html
    item.order.refresh_from_db()
    assert item.order.assignee is None


def test_sheet_requires_a_maker(owner, ali, make_item):
    item = make_item(None)
    response = owner.post(url(item.order), {"employee": "999999"})
    assert response.status_code == 422
    assert "Choose who makes it." in response.content.decode()


def test_sheet_without_employees(owner, make_item):
    item = make_item(None)
    html = owner.get(url(item.order)).content.decode()
    assert "Add an employee in Settings first." in html
    assert "Assign to" not in html


def test_work_plan_assign_next_opens_earliest_waiting(owner, ali, make_item):
    late = make_item(None, due=d(9))
    early = make_item(None, due=d(2))
    html = owner.get("/production/plan/?assign=next").content.decode()
    assert f'hx-get="{url(early.order)}"' in html
    assert f'hx-get="{url(late.order)}"' in html  # its own Assign button
    assert 'hx-trigger="load"' in html
    html = owner.get(
        f"/production/plan/?assign=next&employee={ali.pk}"
    ).content.decode()
    assert f"{url(early.order)}?employee={ali.pk}" in html
    early.order.assignee = ali
    late.order.assignee = ali
    early.order.save()
    late.order.save()
    html = owner.get("/production/plan/?assign=next").content.decode()
    assert 'hx-trigger="load"' not in html
    assert 'id="plan-assign"' not in html


def test_order_detail_change_opens_sheet(owner, ali, client, make_item):
    item = make_item(ali, due=d(3))
    html = owner.get(f"/orders/{item.order.pk}/").content.decode()
    assert f'hx-get="{url(item.order, "?from=order")}"' in html
    item.order.status = Order.DELIVERED
    item.order.save()
    html = owner.get(f"/orders/{item.order.pk}/").content.decode()
    assert 'id="assign-change"' not in html
    owner.logout()
    owner.force_login(ali.user)
    html = owner.get(f"/orders/{item.order.pk}/").content.decode()
    assert 'id="assign-change"' not in html


def test_assign_error_when_last_item_finished_rerenders_422(
    owner, ali, make_item, monkeypatch
):
    import production.views as views

    item = make_item(None)
    real = views.assign

    def racing(order, *args):
        OrderItem.objects.filter(pk=item.pk).update(status=OrderItem.FINISHED)
        return real(order, *args)

    monkeypatch.setattr(views, "assign", racing)
    response = owner.post(
        url(item.order), {"employee": ali.pk, f"estimate_{item.pk}": "2h"}
    )
    assert response.status_code == 422
    html = response.content.decode()
    assert "can&#x27;t be assigned any more" in html or "can't be assigned" in html
    assert "Assign to" not in html
