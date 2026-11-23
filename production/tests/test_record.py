from datetime import UTC, date, datetime, timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from accounts.roles import OWNER, add_to_role
from catalog.models import Product
from orders.models import OrderItem
from production import record, timing
from production.models import TimeSession

pytestmark = pytest.mark.django_db

MINUS = "\N{MINUS SIGN}"


def at(minutes):
    return timezone.localtime().replace(
        hour=9, minute=0, second=0, microsecond=0
    ) + timedelta(minutes=minutes)


@pytest.fixture
def owner(db):
    user = User.objects.create_user("owner", password="x")
    add_to_role(user, OWNER)
    client = Client()
    client.force_login(user)
    return client


def sessions_for(employee, item=None, rework=None, spans=((0, 60),)):
    return [
        TimeSession.objects.create(
            employee=employee,
            item=item,
            rework=rework,
            started_at=at(a),
            ended_at=at(b),
        )
        for a, b in spans
    ]


def finish(item, minutes=185):
    item.status = OrderItem.FINISHED
    item.finished_at = at(minutes + 5)
    item.save()


def test_difference_text_over_under_exact_and_none():
    assert record.difference_text(185, 165) == "20m over (+12%)"
    assert record.difference_text(150, 165) == f"15m under ({MINUS}9%)"
    assert record.difference_text(165, 165) == "right on the estimate"
    assert record.difference_text(165, None) == ""


def test_left_text_and_progress_percent():
    assert record.left_text(110, 165) == "about 55m left"
    assert record.progress_percent(110, 165) == 67
    assert record.left_text(200, 165) == "35m over"
    assert record.progress_percent(200, 165) == 100
    assert record.progress_percent(10, 0) == 100


def test_bar_rows_scale_to_longest_and_skip_missing():
    rows = record.bar_rows(None, 185, 190, "Kurta")
    assert [r["label"] for r in rows] == ["Took", "Usual kurta"]
    assert rows[1]["percent"] == 100
    full = record.bar_rows(165, 185, 190, "Kurta")
    assert [r["tone"] for r in full] == ["estimate", "took", "usual"]
    assert record.bar_rows(165, 1, None, "Kurta")[1]["percent"] == 2


def test_pattern_line_all_within_some_within_and_too_few():
    same = [(100, 100)] * 5
    assert (
        record.pattern_line("Ali", "Kurta", same)
        == "Ali has finished the last 5 kurtas within 10% of the estimate."
    )
    mixed = [(100, 100), (150, 100), (105, 100)]
    assert (
        record.pattern_line("Ali", "Kurta", mixed)
        == "Ali has finished 2 of the last 3 kurtas within 10% of the estimate."
    )
    assert record.pattern_line("Ali", "Kurta", [(100, 100)]) == ""


def test_plural():
    assert record.plural("Kurta") == "kurtas"
    assert record.plural("Dress") == "dresses"


def test_due_state_on_time_late_on_track_none():
    due = date(2026, 11, 14)
    done_ok = datetime(2026, 11, 14, 10, tzinfo=UTC)
    done_late = datetime(2026, 11, 16, 10, tzinfo=UTC)
    assert record.due_state(due, done_ok, date(2026, 11, 20)) == (
        "Sat 14 Nov",
        "On time",
    )
    assert record.due_state(due, done_late, date(2026, 11, 20)) == (
        "Sat 14 Nov",
        "Late",
    )
    assert record.due_state(due, None, date(2026, 11, 12)) == (
        "Sat 14 Nov · on track",
        "",
    )
    assert record.due_state(due, None, date(2026, 11, 15)) == ("Sat 14 Nov", "Late")
    assert record.due_state(None, None, date(2026, 11, 15)) == ("No due date", "")


def test_production_line_variants():
    assert record.production_line(0, 165, 0, False) == "Not started · est. 2h 45m"
    assert record.production_line(0, None, 0, False) == "Not started"
    assert (
        record.production_line(185, 165, 4, True) == "3h 5m of 2h 45m est. · 4 sessions"
    )
    assert record.production_line(185, None, 4, True) == "3h 5m · 4 sessions"
    assert record.production_line(30, 60, 1, True) == "30m of 1h est. · 1 session"


def test_session_rows_running_stale_and_total(ali, make_item):
    item = make_item(ali)
    closed = TimeSession.objects.create(
        employee=ali,
        item=item,
        started_at=at(-3 * 24 * 60),
        ended_at=at(-3 * 24 * 60 + 88),
    )
    running = TimeSession.objects.create(employee=ali, item=item, started_at=at(0))
    rows, total = record.session_rows([closed, running], at(30))
    assert rows[0]["minutes_text"] == "1h 28m"
    assert rows[1]["times"].endswith("still running")
    assert rows[1]["minutes_text"] == "30m"
    assert total == 118
    # A session left open on an earlier day stops at its cutoff.
    running.started_at = at(-2 * 24 * 60)
    running.save()
    rows, total = record.session_rows([closed, running], at(30))
    assert "still running" not in rows[1]["times"]
    assert rows[1]["minutes_text"] == "0m"
    assert total == 88


def test_rework_time_excluded_from_item_comparison(ali, make_item, make_rework):
    item = make_item(ali, estimate=165)
    sessions_for(ali, item=item, spans=((0, 60), (70, 195)))
    rework = make_rework(item, ali)
    sessions_for(ali, rework=rework, spans=((300, 340),))
    finish(item)
    ctx = record.item_record(OrderItem.objects.get(pk=item.pk), at(400))
    assert ctx["hero"]["big"] == "3h 5m"
    assert ctx["hero"]["sub_strong"] == "20m over (+12%)"
    took = next(b for b in ctx["bars"] if b["tone"] == "took")
    assert took["minutes_text"] == "3h 5m"
    assert ctx["session_count"] == 2
    assert ctx["reworks"][0]["time"] == "40m"
    assert ctx["reworks"][0]["label"] == "R1 · Fit alteration"


def test_rework_record_has_own_estimate_and_sessions(ali, make_item, make_rework):
    item = make_item(ali, estimate=165)
    rework = make_rework(item, ali, estimate_minutes=45)
    sessions_for(ali, rework=rework, spans=((0, 40),))
    ctx = record.rework_record(rework, at(60))
    assert ctx["title"] == "Rework · Blouse"
    assert ctx["reason"] == "Fit alteration"
    assert ctx["hero"]["big"] == "40m"
    assert "Your estimate 45m" in ctx["hero"]["sub"]
    assert ctx["hero"]["chip"] == "Paused"
    assert ctx["bars"] == []
    assert ctx["note"] is None
    assert ctx["session_count"] == 1


def test_in_progress_running_and_paused_chip(ali, make_item):
    item = make_item(ali, estimate=165, status="open")
    item.status = OrderItem.IN_PROGRESS
    item.save()
    other = make_item(ali, name="Suit")
    TimeSession.objects.create(
        employee=ali, item=item, started_at=at(0), ended_at=at(60)
    )
    TimeSession.objects.create(employee=ali, item=item, started_at=at(70))
    ctx = record.item_record(item, at(110))
    assert ctx["hero"]["chip"] == "Running"
    assert ctx["hero"]["big"] == "1h 40m"
    assert ctx["hero"]["percent"] == 61
    assert "left" in ctx["hero"]["sub"]
    assert ctx["bars"] == []
    # Switching to another item pauses this one.
    timing.start_item(ali, other, at(120))
    item = OrderItem.objects.get(pk=item.pk)
    assert record.item_record(item, at(130))["hero"]["chip"] == "Paused"


def test_not_started_and_no_estimate_heroes(ali, make_item):
    item = make_item(ali, estimate=165)
    ctx = record.item_record(item, at(0))
    assert ctx["hero"]["big"] == "2h 45m"
    assert ctx["hero"]["sub"] == "Not started"
    assert ctx["details"][1]["label"] == "Estimate set"
    old = make_item(ali, estimate=None)
    sessions_for(ali, item=old)
    finish(old, 60)
    ctx = record.item_record(OrderItem.objects.get(pk=old.pk), at(100))
    assert ctx["hero"]["sub"] == "" and ctx["hero"]["sub_strong"] == ""
    assert [b["tone"] for b in ctx["bars"]] == ["took"]
    assert "Estimate set" not in [d["label"] for d in ctx["details"]]


def test_estimate_set_row_variants(ali, make_item):
    item = make_item(ali, estimate=60)
    assert record._estimate_row(item) == "Not recorded"
    item.estimate_set_at = at(0)
    assert record._estimate_row(item).endswith(", when assigned")
    item.estimate_from_usual = True
    assert record._estimate_row(item).endswith(", usual time at start")


def test_pattern_for_employee_and_product(ali, make_item):
    items = []
    for i in range(3):
        item = make_item(ali, estimate=100)
        TimeSession.objects.create(
            employee=ali, item=item, started_at=at(i * 300), ended_at=at(i * 300 + 100)
        )
        finish(item, i * 300 + 100)
        items.append(item)
    ctx = record.item_record(OrderItem.objects.get(pk=items[-1].pk), at(2000))
    assert ctx["pattern"] == (
        "Ali has finished the last 3 blouses within 10% of the estimate."
    )
    assert ctx["bars_caption"] == "Usual = average of the last 3 blouses."


def test_record_lists_every_session_with_start_end_minutes(owner, ali, make_item):
    item = make_item(ali, estimate=165)
    sessions_for(ali, item=item, spans=((0, 88), (100, 130), (140, 200), (210, 237)))
    finish(item, 237)
    response = owner.get(reverse("production_record", args=[item.pk]))
    body = response.content.decode()
    assert response.status_code == 200
    assert "9:00 am to 10:28 am" in body
    assert "1h 28m" in body
    assert "11:20 am to 12:20 pm" in body
    assert "Total logged" in body
    assert "3h 25m" in body
    assert "Work sessions" in body and "(4)" in body
    assert "Why it took longer" in body


def test_note_saves_and_clears(owner, ali, make_item):
    item = make_item(ali, estimate=60)
    finish(item, 60)
    url = reverse("production_record_note", args=[item.pk])
    response = owner.post(url, {"note": "  Lining was thin  "})
    assert response.status_code == 200
    assert "Note saved" in response["HX-Trigger"]
    item.refresh_from_db()
    assert item.delay_note == "Lining was thin"
    owner.post(url, {"note": " "})
    item.refresh_from_db()
    assert item.delay_note == ""


def test_note_too_long_422(owner, ali, make_item):
    item = make_item(ali, estimate=60)
    finish(item, 60)
    response = owner.post(
        reverse("production_record_note", args=[item.pk]), {"note": "x" * 501}
    )
    assert response.status_code == 422
    body = response.content.decode()
    assert "Keep it under 500 characters." in body
    assert "x" * 501 in body
    item.refresh_from_db()
    assert item.delay_note == ""


def test_note_on_unfinished_item_404(owner, ali, make_item):
    item = make_item(ali, estimate=60)
    response = owner.post(
        reverse("production_record_note", args=[item.pk]), {"note": "hi"}
    )
    assert response.status_code == 404


def test_record_owner_only(owner, ali, make_item, blouse):
    item = make_item(ali, estimate=60)
    url = reverse("production_record", args=[item.pk])
    assert ali.client.get(url).status_code in (302, 403)
    assert ali.client.post(
        reverse("production_record_note", args=[item.pk])
    ).status_code in (302, 403)
    assert owner.get(url).status_code == 200
    ready = make_item(ali, kind=Product.READY_MADE)
    assert owner.get(reverse("production_record", args=[ready.pk])).status_code == 404
    draft = make_item(ali, status="draft")
    assert owner.get(reverse("production_record", args=[draft.pk])).status_code == 404


def test_rework_record_page(owner, ali, make_item, make_rework):
    item = make_item(ali, estimate=60)
    rework = make_rework(item, ali)
    page = owner.get(reverse("rework_record", args=[rework.pk])).content.decode()
    assert "Rework · Blouse" in page
    assert "Fit alteration" in page
    finish(item, 60)
    page = owner.get(reverse("production_record", args=[item.pk])).content.decode()
    assert "Rework after delivery" in page
    assert reverse("rework_record", args=[rework.pk]) in page


def test_assign_sets_estimate_set_at(owner, ali, make_item):
    from production.assign import SUGGESTED

    item = make_item(None, due=timezone.localdate() + timedelta(days=5))
    response = owner.post(
        reverse("assign_sheet", args=[item.order.pk]),
        {"employee": ali.pk, "place": SUGGESTED, f"estimate_{item.pk}": "3h"},
    )
    assert response.status_code == 204
    item.refresh_from_db()
    assert item.estimate_minutes == 180
    assert item.estimate_set_at is not None
    assert item.estimate_from_usual is False


def test_begin_marks_estimate_from_usual(ali, make_item):
    item = make_item(ali)
    timing.start_item(ali, item, at(0))
    item.refresh_from_db()
    assert item.estimate_from_usual is True
    assert item.estimate_set_at is not None
    set_one = make_item(ali, estimate=30)
    timing.start_item(ali, set_one, at(5))
    set_one.refresh_from_db()
    assert set_one.estimate_from_usual is False
    assert set_one.estimate_set_at is None


def test_order_page_production_row_links_to_record(owner, ali, make_item):
    item = make_item(ali, estimate=165)
    sessions_for(ali, item=item, spans=((0, 60),))
    url = reverse("order", args=[item.order.pk])
    page = owner.get(url).content.decode()
    assert reverse("production_record", args=[item.pk]) in page
    assert "1h of 2h 45m est. · 1 session" in page
    assert (
        reverse("production_record", args=[item.pk])
        not in ali.client.get(url).content.decode()
    )
    ready = make_item(ali, kind=Product.READY_MADE)
    page = owner.get(reverse("order", args=[ready.order.pk])).content.decode()
    assert "item-card__production" not in page
