from datetime import UTC, datetime, timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from orders.models import Order, OrderItem
from production import timing
from production.models import TimeSession

pytestmark = pytest.mark.django_db

T0 = datetime(2026, 11, 20, 9, 0, tzinfo=UTC)


def at(minutes):
    return T0 + timedelta(minutes=minutes)


@pytest.mark.parametrize(
    "seconds,text",
    [(0, "0:00:00"), (59, "0:00:59"), (5110, "1:25:10"), (36000, "10:00:00")],
)
def test_timer_text(seconds, text):
    assert timing.timer_text(seconds) == text


def test_session_seconds_running_and_closed():
    assert timing.session_seconds(at(0), at(10), at(99)) == 600
    assert timing.session_seconds(at(0), None, at(5)) == 300
    assert timing.session_seconds(at(5), None, at(0)) == 0


def test_logged_minutes_across_pause_and_resume(ali, make_item):
    item = make_item(ali)
    timing.start_item(ali, item, at(0))
    timing.stop(ali, at(40))
    timing.start_item(ali, item, at(60))
    timing.stop(ali, at(85))
    sessions = list(item.sessions.all())
    assert len(sessions) == 2
    assert timing.logged_minutes(sessions, at(90)) == 65
    assert (
        sum(int((s.ended_at - s.started_at).total_seconds()) for s in sessions)
        == 65 * 60
    )


def test_stale_end():
    assert timing.stale_end(at(0), at(60)) == at(60)
    assert timing.stale_end(at(60), at(0)) == at(60)
    assert timing.stale_end(at(0), None) == at(0)


def test_switch_closes_a_and_opens_b(ali, make_item):
    a, b = make_item(ali), make_item(ali, name="Suit")
    timing.start_item(ali, a, at(0))
    timing.start_item(ali, b, at(30))
    first = a.sessions.get()
    assert first.ended_at == at(30)
    assert b.sessions.get().ended_at is None
    assert TimeSession.objects.filter(ended_at__isnull=True).count() == 1


def test_two_open_sessions_impossible(ali, make_item):
    a, b = make_item(ali), make_item(ali)
    TimeSession.objects.create(employee=ali, item=a, started_at=at(0))
    with pytest.raises(IntegrityError), transaction.atomic():
        TimeSession.objects.create(employee=ali, item=b, started_at=at(1))


def test_session_needs_exactly_one_of_item_or_rework(ali, make_item):
    item = make_item(ali)
    with pytest.raises(IntegrityError), transaction.atomic():
        TimeSession.objects.create(employee=ali, started_at=at(0))
    from orders.models import Rework

    rework = Rework.objects.create(item=item, reason="fit")
    with pytest.raises(IntegrityError), transaction.atomic():
        TimeSession.objects.create(
            employee=ali, item=item, rework=rework, started_at=at(0)
        )


def test_first_session_fixes_estimate_and_starts_item_and_order(ali, make_item):
    item, owned = make_item(ali), make_item(ali, estimate=45)
    timing.start_item(ali, item, at(0))
    timing.start_item(ali, owned, at(5))
    item.refresh_from_db()
    owned.refresh_from_db()
    assert (item.estimate_minutes, item.status) == (120, OrderItem.IN_PROGRESS)
    assert owned.estimate_minutes == 45
    assert item.order.status == Order.IN_PROGRESS


def test_second_session_keeps_estimate(ali, make_item, monkeypatch):
    item = make_item(ali)
    timing.start_item(ali, item, at(0))
    timing.stop(ali, at(1))
    monkeypatch.setattr(timing, "usual_minutes", lambda product: 999)
    timing.start_item(ali, item, at(2))
    item.refresh_from_db()
    assert item.estimate_minutes == 120


def test_start_same_item_twice_is_noop(ali, make_item):
    item = make_item(ali)
    first = timing.start_item(ali, item, at(0))
    assert timing.start_item(ali, item, at(1)) == first
    assert item.sessions.count() == 1


def test_finish_closes_session_and_sets_finished(ali, make_item):
    item = make_item(ali)
    timing.start_item(ali, item, at(0))
    timing.finish_item(ali, item, at(20))
    item.refresh_from_db()
    assert item.status == OrderItem.FINISHED
    assert item.finished_at == at(20)
    assert timing.open_session(ali) is None
    assert item.sessions.get().ended_at == at(20)


def test_finish_unstarted_item_moves_order_in_progress(ali, make_item):
    item = make_item(ali)
    timing.finish_item(ali, item, at(0))
    item.order.refresh_from_db()
    assert item.order.status == Order.IN_PROGRESS


def test_close_stale_uses_yesterdays_day_end(ali, make_item, started_day):
    item = make_item(ali)
    now = timezone.make_aware(datetime(2026, 11, 21, 9, 0))
    yesterday = now.date() - timedelta(days=1)
    end = timezone.make_aware(datetime(2026, 11, 20, 18, 0))
    started_day(ali, yesterday, end=end)
    start = timezone.make_aware(datetime(2026, 11, 20, 10, 0))
    TimeSession.objects.create(employee=ali, item=item, started_at=start)
    timing.close_stale(ali, now)
    assert item.sessions.get().ended_at == end


def test_close_stale_without_day_end_counts_zero(ali, make_item):
    item = make_item(ali)
    now = timezone.now()
    start = now - timedelta(days=1)
    TimeSession.objects.create(employee=ali, item=item, started_at=start)
    timing.close_stale(ali, now)
    assert item.sessions.get().ended_at == start


def test_close_stale_leaves_todays_session(ali, make_item):
    item = make_item(ali)
    now = timezone.now()
    TimeSession.objects.create(employee=ali, item=item, started_at=now)
    timing.close_stale(ali, now)
    assert item.sessions.get().ended_at is None


def test_my_items_filters_and_orders(ali, make_item, customer):
    from datetime import date

    other = Order.objects.create(customer=customer, number=900, status="open")
    late = make_item(ali, date(2026, 12, 5), name="Late")
    soon = make_item(ali, date(2026, 12, 1), name="Soon")
    undated = make_item(ali, None, name="Undated")
    make_item(ali, date(2026, 12, 1), name="Ready", status="ready")
    make_item(ali, date(2026, 12, 1), name="Delivered", status="delivered")
    make_item(ali, date(2026, 12, 1), name="Made", kind="ready_made")
    done = make_item(ali, date(2026, 12, 1), name="Done")
    done.status = OrderItem.FINISHED
    done.save()
    elsewhere = make_item(None, date(2026, 12, 1), name="Other")
    assert other.assignee is None and elsewhere.order.assignee is None
    assert list(timing.my_items(ali)) == [soon, late, undated]


def test_panel_hero_running_then_paused(ali, make_item, started_day):
    now = timezone.make_aware(datetime(2026, 11, 20, 12, 0))
    started_day(ali, now.date())
    a, b = make_item(ali), make_item(ali, name="Suit")
    timing.start_item(ali, a, now - timedelta(minutes=10))
    data = timing.panel(ali, now)
    assert data["hero"]["state"] == "running"
    assert data["hero"]["seconds"] == 600
    assert [r["item"] for r in data["up_next"]] == [b]
    timing.stop(ali, now)
    data = timing.panel(ali, now)
    assert data["hero"]["state"] == "paused"
    assert data["hero"]["seconds"] == 600
    assert data["hero"]["started_at"] is None
    assert [r["item"] for r in data["up_next"]] == [b]


def test_panel_no_hero_when_day_not_started(ali, make_item):
    make_item(ali)
    data = timing.panel(ali, timezone.now())
    assert data["hero"] is None
    assert not data["can_time"]
    assert len(data["up_next"]) == 1


def test_stop_on_a_later_day_uses_the_stale_cutoff(ali, make_item):
    item = make_item(ali)
    start = timezone.make_aware(datetime(2026, 11, 20, 10, 0))
    TimeSession.objects.create(employee=ali, item=item, started_at=start)
    timing.stop(ali, timezone.make_aware(datetime(2026, 11, 21, 9, 0)))
    assert item.sessions.get().ended_at == start


def test_start_refuses_an_item_finished_meanwhile(ali, make_item):
    a, b = make_item(ali), make_item(ali, name="Suit")
    timing.start_item(ali, a, at(0))
    stale_copy = OrderItem.objects.get(pk=b.pk)
    timing.finish_item(ali, b, at(5))
    with pytest.raises(timing.TimingError):
        timing.start_item(ali, stale_copy, at(10))
    assert timing.open_session(ali).item_id == a.pk


def test_missing_estimate_filled_on_in_progress_item(ali, make_item):
    item = make_item(ali)
    item.status = OrderItem.IN_PROGRESS
    item.save()
    timing.start_item(ali, item, at(0))
    item.refresh_from_db()
    assert item.estimate_minutes == 120


def test_switch_never_starts_before_the_latest_session(ali, make_item):
    a, b = make_item(ali), make_item(ali, name="Suit")
    timing.start_item(ali, a, at(0))
    timing.stop(ali, at(1))
    session = timing.start_item(ali, b, at(0))
    assert session.started_at == at(1)


def test_panel_keeps_timer_stoppable_when_order_goes_ready(ali, make_item, started_day):
    now = timezone.make_aware(datetime(2026, 11, 20, 12, 0))
    started_day(ali, now.date())
    item = make_item(ali)
    timing.start_item(ali, item, now - timedelta(minutes=5))
    item.order.status = Order.READY
    item.order.save()
    data = timing.panel(ali, now)
    assert data["hero"]["state"] == "running"
    assert not data["hero"]["finishable"]
    assert data["up_next"] == []


def test_panel_ignores_yesterdays_open_session(ali, make_item, started_day):
    now = timezone.make_aware(datetime(2026, 11, 21, 8, 0))
    item = make_item(ali)
    start = timezone.make_aware(datetime(2026, 11, 20, 10, 0))
    TimeSession.objects.create(employee=ali, item=item, started_at=start)
    data = timing.panel(ali, now)
    assert data["hero"] is None
    assert not data["running"]
    assert data["up_next"][0]["minutes"] == 0


def test_panel_hero_includes_session_started_after_the_prefetch(
    ali, make_item, started_day, monkeypatch
):
    now = timezone.make_aware(datetime(2026, 11, 20, 12, 0))
    started_day(ali, now.date())
    item = make_item(ali)
    real = timing.open_session

    def racing(employee):
        TimeSession.objects.create(
            employee=employee, item=item, started_at=now - timedelta(minutes=2)
        )
        return real(employee)

    monkeypatch.setattr(timing, "open_session", racing)
    hero = timing.panel(ali, now)["hero"]
    assert hero["state"] == "running"
    assert hero["started_at"] == now - timedelta(minutes=2)
