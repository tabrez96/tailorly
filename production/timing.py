"""Timing items on S08: pure helpers plus the session writes."""

from datetime import datetime

from django.db import transaction
from django.db.models import F
from django.urls import reverse
from django.utils import timezone

from catalog.models import Product
from orders.models import Order, OrderItem, Rework
from production.estimates import usual_minutes
from production.models import TimeSession
from production.queue import ordered
from staff.attendance import day_card
from staff.models import DayRecord, Employee


class TimingError(ValueError):
    """A timing action the current state doesn't allow."""


def session_seconds(started_at, ended_at, now) -> int:
    return max(0, int(((ended_at or now) - started_at).total_seconds()))


def logged_seconds(sessions, now) -> int:
    return sum(session_seconds(s.started_at, s.ended_at, now) for s in sessions)


def logged_minutes(sessions, now) -> int:
    return logged_seconds(sessions, now) // 60


def timer_text(seconds: int) -> str:
    minutes, secs = divmod(max(0, seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}"


def stale_end(started_at: datetime, day_end: datetime | None) -> datetime:
    """When a session left open on an earlier day stops: never later than the
    day's end, and never invented hours when the day was never ended."""
    return max(started_at, day_end) if day_end else started_at


def my_items(employee):
    return (
        OrderItem.objects.filter(
            order__assignee=employee,
            order__status__in=[Order.OPEN, Order.IN_PROGRESS],
            type=Product.CUSTOM,
        )
        .exclude(status=OrderItem.FINISHED)
        .select_related("order__customer", "product")
        .prefetch_related("photos", "sessions")
        .order_by(
            F("order__due_date").asc(nulls_last=True), "order__number", "position", "id"
        )
    )


def open_session(employee) -> TimeSession | None:
    return TimeSession.objects.filter(employee=employee, ended_at__isnull=True).first()


def _lock(employee) -> None:
    """Serialise two taps from the same employee."""
    Employee.objects.select_for_update().get(pk=employee.pk)


def _stale_cutoff(session, now) -> datetime | None:
    """Where a session left open on an earlier day stops, or None if it is today's."""
    day = timezone.localdate(session.started_at)
    if day >= timezone.localdate(now):
        return None
    record = DayRecord.objects.filter(employee_id=session.employee_id, date=day).first()
    return stale_end(session.started_at, record.end if record else None)


def _logged(sessions, now) -> int:
    """Logged seconds, counting a stale open session only up to its cutoff."""
    return sum(
        session_seconds(s.started_at, s.ended_at or _stale_cutoff(s, now), now)
        for s in sessions
    )


def stop(employee, now) -> TimeSession | None:
    with transaction.atomic():
        _lock(employee)
        session = open_session(employee)
        if session is None:
            return None
        session.ended_at = _stale_cutoff(session, now) or max(now, session.started_at)
        session.save(update_fields=["ended_at"])
        return session


def _locked_item(item) -> OrderItem:
    return (
        OrderItem.objects.select_for_update(of=("self",))
        .select_related("order")
        .get(pk=item.pk)
    )


def _workable(employee, item) -> bool:
    """Whether `item` (freshly locked) is still on the employee's My work list."""
    return (
        item.order.assignee_id == employee.pk
        and item.order.status in (Order.OPEN, Order.IN_PROGRESS)
        and item.type == Product.CUSTOM
        and item.status != OrderItem.FINISHED
    )


def _begin(item) -> None:
    """Fix a missing estimate; the first time, start the item and its order."""
    if not item.estimate_minutes:
        item.estimate_minutes = usual_minutes(item.product)
        item.estimate_from_usual = True
        item.estimate_set_at = timezone.now()
        item.save(
            update_fields=[
                "estimate_minutes",
                "estimate_from_usual",
                "estimate_set_at",
            ]
        )
    if item.status == OrderItem.NOT_STARTED:
        item.status = OrderItem.IN_PROGRESS
        item.save(update_fields=["status"])
        item.order.start_work()


def _boundary(employee, now) -> datetime:
    """The time a switch happens: never before the employee's latest session."""
    last = TimeSession.objects.filter(employee=employee).order_by("-started_at").first()
    if last is None:
        return now
    return max(now, last.ended_at or last.started_at)


def _close_for_switch(employee, now) -> datetime:
    """Close any open session; return when the next one starts."""
    at = _boundary(employee, now)
    closed = stop(employee, at)
    if closed is not None:
        at = max(at, closed.ended_at)
    return at


def start_item(employee, item, now) -> TimeSession:
    """Start, Resume and Switch: close any open session and open one on `item`."""
    with transaction.atomic():
        _lock(employee)
        current = open_session(employee)
        if current is not None and current.item_id == item.pk:
            return current
        item = _locked_item(item)
        if not _workable(employee, item):
            raise TimingError("This item is no longer on your list.")
        at = _close_for_switch(employee, now)
        _begin(item)
        return TimeSession.objects.create(employee=employee, item=item, started_at=at)


def finish_item(employee, item, now) -> None:
    with transaction.atomic():
        _lock(employee)
        item = _locked_item(item)
        if not _workable(employee, item):
            raise TimingError("This item is no longer on your list.")
        current = open_session(employee)
        if current is not None and current.item_id == item.pk:
            stop(employee, now)
        _begin(item)
        item.status = OrderItem.FINISHED
        item.finished_at = now
        item.save(update_fields=["status", "finished_at"])


def my_reworks(employee):
    return (
        Rework.objects.filter(assignee=employee, finished_at__isnull=True)
        .select_related("item__order__customer", "item__product")
        .prefetch_related("item__photos", "sessions")
    )


def _locked_rework(rework) -> Rework:
    return (
        Rework.objects.select_for_update(of=("self",))
        .select_related("item__order")
        .get(pk=rework.pk)
    )


def _rework_workable(employee, rework) -> bool:
    return rework.assignee_id == employee.pk and rework.finished_at is None


def start_rework(employee, rework, now) -> TimeSession:
    """Start, Resume and Switch for a rework; never touches the item."""
    with transaction.atomic():
        _lock(employee)
        current = open_session(employee)
        if current is not None and current.rework_id == rework.pk:
            return current
        rework = _locked_rework(rework)
        if not _rework_workable(employee, rework):
            raise TimingError("This rework is no longer on your list.")
        at = _close_for_switch(employee, now)
        return TimeSession.objects.create(
            employee=employee, rework=rework, started_at=at
        )


def finish_rework(employee, rework, now) -> None:
    with transaction.atomic():
        _lock(employee)
        rework = _locked_rework(rework)
        if not _rework_workable(employee, rework):
            raise TimingError("This rework is no longer on your list.")
        current = open_session(employee)
        if current is not None and current.rework_id == rework.pk:
            stop(employee, now)
        rework.finished_at = now
        rework.save(update_fields=["finished_at"])


def close_stale(employee, now) -> None:
    """Close a session left open from an earlier day."""
    with transaction.atomic():
        _lock(employee)
        session = open_session(employee)
        if session is None:
            return
        cutoff = _stale_cutoff(session, now)
        if cutoff is None:
            return
        session.ended_at = cutoff
        session.save(update_fields=["ended_at"])


def _thumb(item) -> tuple[str | None, int]:
    photos = list(item.photos.all())
    thumb = reverse("item_photo_thumb", args=[photos[0].pk]) if photos else None
    return thumb, len(photos)


def _row(item, now) -> dict:
    thumb, count = _thumb(item)
    sessions = list(item.sessions.all())
    minutes = _logged(sessions, now) // 60
    estimate = item.estimate_minutes or usual_minutes(item.product)
    return {
        "key": ("item", item.pk),
        "item": item,
        "rework": None,
        "order": item.order,
        "customer": item.order.customer,
        "due": item.order.due_date,
        "thumb": thumb,
        "photo_count": count,
        "sessions": sessions,
        "minutes": minutes,
        "estimate": estimate,
        "need": max(estimate - minutes, 0),
        "started": item.status == OrderItem.IN_PROGRESS,
        "moved_to": item.queue_rank,
        "finished_at": item.finished_at,
        "start_url": reverse("work_start", args=[item.pk]),
        "finish_url": reverse("work_finish", args=[item.pk]),
        "details_url": reverse("work_item_details", args=[item.pk]),
    }


def _rework_row(rework, now) -> dict:
    item = rework.item
    thumb, count = _thumb(item)
    sessions = list(rework.sessions.all())
    minutes = _logged(sessions, now) // 60
    estimate = rework.estimate_minutes
    return {
        "key": ("rework", rework.pk),
        "item": item,
        "rework": rework,
        "order": item.order,
        "customer": item.order.customer,
        "due": rework.due_date,
        "thumb": thumb,
        "photo_count": count,
        "sessions": sessions,
        "minutes": minutes,
        "estimate": estimate,
        "need": max(estimate - minutes, 0),
        "started": bool(sessions),
        "moved_to": rework.queue_rank,
        "finished_at": rework.finished_at,
        "start_url": reverse("work_rework_start", args=[rework.pk]),
        "finish_url": reverse("work_rework_finish", args=[rework.pk]),
        "details_url": reverse("work_rework_details", args=[rework.pk]),
    }


def queue_rows(employee, now) -> list[dict]:
    """The employee's open work in queue order; S08 Up next and S16 both show this."""
    return ordered(
        [_row(i, now) for i in my_items(employee)]
        + [_rework_row(r, now) for r in my_reworks(employee)]
    )


def _hero(row, state, now, finishable, running) -> dict:
    sessions = list(row["sessions"])
    if running is not None and running not in sessions:
        sessions.append(running)
    open_ = next((s for s in sessions if s.ended_at is None), None)
    return {
        **row,
        "state": state,
        "finishable": finishable,
        "seconds": logged_seconds(sessions, now),
        "closed_seconds": logged_seconds([s for s in sessions if s.ended_at], now),
        "started_at": open_.started_at if open_ else None,
    }


def _session_key(session) -> tuple:
    if session.item_id:
        return ("item", session.item_id)
    return ("rework", session.rework_id)


def _session_row(session, now) -> dict:
    if session.item_id:
        item = (
            OrderItem.objects.select_related("order__customer")
            .prefetch_related("photos", "sessions")
            .get(pk=session.item_id)
        )
        return _row(item, now)
    rework = (
        Rework.objects.select_related("item__order__customer")
        .prefetch_related("item__photos", "sessions")
        .get(pk=session.rework_id)
    )
    return _rework_row(rework, now)


def panel(employee, now) -> dict:
    day = day_card(employee, now)
    can_time = day["state"] == "started"
    queue = queue_rows(employee, now)
    by_key = {r["key"]: r for r in queue}
    current = open_session(employee)
    running = (
        current if current is not None and _stale_cutoff(current, now) is None else None
    )
    hero_row, state = None, None
    if running is not None:
        # The work may have left My work mid-timer; the timer must stay stoppable.
        hero_row = by_key.get(_session_key(running)) or _session_row(running, now)
        state = "running"
    elif can_time:
        last = (
            TimeSession.objects.filter(
                employee=employee, ended_at__date=timezone.localdate(now)
            )
            .order_by("-ended_at", "-id")
            .first()
        )
        if last is not None:
            hero_row = by_key.get(_session_key(last))
            state = "paused"
    hero = (
        _hero(hero_row, state, now, hero_row["key"] in by_key, running)
        if hero_row is not None
        else None
    )
    if hero is not None and state == "paused":
        # From the query that picked the session, not from the queue snapshot.
        hero["paused_at"] = last.ended_at
    today = timezone.localdate(now)
    finished_items = (
        OrderItem.objects.filter(
            order__assignee=employee,
            status=OrderItem.FINISHED,
            finished_at__date=today,
        )
        .select_related("order__customer")
        .prefetch_related("photos", "sessions")
    )
    finished_reworks = (
        Rework.objects.filter(assignee=employee, finished_at__date=today)
        .select_related("item__order__customer")
        .prefetch_related("item__photos", "sessions")
    )
    finished = sorted(
        [_row(i, now) for i in finished_items]
        + [_rework_row(r, now) for r in finished_reworks],
        key=lambda r: r["finished_at"],
    )
    return {
        "day": day,
        "can_time": can_time,
        "running": running is not None,
        "hero": hero,
        "up_next": [
            r for r in queue if hero_row is None or r["key"] != hero_row["key"]
        ],
        "finished": finished,
        "now": now,
    }
