"""The S12 Production tab: who is working on what right now."""

from django.urls import reverse
from django.utils import timezone

from core.formats import format_clock, format_day, format_duration
from production.assign import waiting_orders
from production.models import TimeSession
from production.plan import _decorate, _unassigned
from production.timing import logged_minutes, panel
from staff.attendance import first_name, initials
from staff.models import Employee

WORKING, PAUSED, IDLE, NOT_IN, GONE = "working", "paused", "idle", "not_in", "gone"
ORDER = {WORKING: 0, PAUSED: 1, IDLE: 2, NOT_IN: 3, GONE: 4}
CHIPS = {  # (label, chip tone)
    WORKING: ("Working", "ok"),
    PAUSED: ("Paused", "warn"),
    IDLE: ("Not timing anything", "warn"),
    NOT_IN: ("Not in yet", "grey"),
    GONE: ("Gone home", "grey"),  # the card appends the day end time
}


def card_state(day_state: str, hero_state: str | None) -> str:
    if hero_state == "running":
        return WORKING
    if day_state == "not_started":
        return NOT_IN
    if day_state == "ended":
        return GONE
    return PAUSED if hero_state == "paused" else IDLE


def minutes_left_text(minutes: int, estimate: int) -> tuple[str, bool]:
    """('1h 33m left', False) or ('20m over', True); on the estimate is '0m left'."""
    if minutes > estimate:
        return f"{format_duration(minutes - estimate)} over", True
    return f"{format_duration(estimate - minutes)} left", False


def bar_percent(minutes: int, estimate: int) -> int:
    """0-100; 100 when over or when there is no estimate."""
    if estimate <= 0:
        return 100
    return min(100, minutes * 100 // estimate)


def item_position(item) -> tuple[int, int]:
    """(n, of) of the item among its order's items, by position then id."""
    pks = list(item.order.items.order_by("position", "id").values_list("pk", flat=True))
    return pks.index(item.pk) + 1, len(pks)


def item_url(item) -> str:
    return reverse("order", args=[item.order_id]) + f"#item-{item.pk}"


def _due_part(due, n: int, of: int) -> str:
    if of > 1:
        return (
            f"Item {n} of {of} · due {format_day(due)}"
            if due
            else (f"Item {n} of {of} · no due date")
        )
    return f"Due {format_day(due)}" if due else "No due date"


def _row(row) -> dict:
    n, of = item_position(row["item"])
    line = _due_part(row["due"], n, of)
    if row["moved"]:
        line += " · moved by you"
    chip = ("Next up", "pri") if row["moved"] else (row["status"], row["tone"])
    return {
        "rank": row["rank"],
        "garment": row["garment"],
        "order_label": row["order_label"],
        "line": line,
        "chip_label": chip[0],
        "chip_tone": chip[1],
    }


def _sub(state: str, hero: dict, n: int, of: int, minutes_text, estimate_text) -> str:
    if state == PAUSED:
        paused = f"Paused at {format_clock(hero['paused_at'])}"
        return f"{paused} · {minutes_text} logged of est. {estimate_text}"
    parts = [hero["customer"].name]
    if of > 1:
        parts.append(f"item {n} of {of}")
    if hero["due"]:
        parts.append(f"due {format_day(hero['due'])}")
    return " · ".join(parts)


def _item_block(state: str, hero: dict) -> dict:
    item = hero["item"]
    title = f"{item.name} · #{hero['order'].number}"
    if hero["rework"]:
        title = f"Rework · {title}"
    minutes = hero["seconds"] // 60
    estimate = hero["estimate"]
    left_text, over = minutes_left_text(minutes, estimate)
    minutes_text = format_duration(minutes)
    estimate_text = format_duration(estimate)
    n, of = item_position(item)
    block = {
        "title": title,
        "minutes": minutes,
        "estimate": estimate,
        "left_text": left_text,
        "over": over,
        "percent": bar_percent(minutes, estimate),
        "minutes_text": minutes_text,
        "estimate_text": estimate_text,
        "sub": _sub(state, hero, n, of, minutes_text, estimate_text),
        "url": item_url(item),
        "thumb": hero["thumb"],
        "photo_count": hero["photo_count"],
        "name": item.name,
        "order_number": hero["order"].number,
        "customer": hero["customer"].name,
        "rework": bool(hero["rework"]),
    }
    if state == WORKING:
        block["base_seconds"] = hero["closed_seconds"]
        block["started_at"] = hero["started_at"]
        block["since"] = (
            f"on this {item.name.lower()} since {format_clock(hero['started_at'])}"
        )
    return block


def _day_line(state: str, day: dict) -> str:
    if state == NOT_IN:
        return "Not started the day yet"
    if state == GONE:
        return f"Day {format_clock(day['start'])} – {format_clock(day['end'])}"
    return (
        f"Day started {format_clock(day['start'])} · "
        f"{format_duration(day['so_far'])} in"
    )


def _note(state: str, employee, first: str, has_rows: bool, now) -> str:
    if state == NOT_IN:
        if has_rows:
            return (
                f"{first}'s queue is ready. The timer starts when {first} taps "
                f"Start my day on My work, or you can start the day for {first} here."
            )
        return (
            f"Nothing in {first}'s queue yet. You can start the day for {first} here."
        )
    if state == IDLE:
        return f"{first} started the day but isn't timing an item."
    if state == GONE:
        today = timezone.localdate(now)
        sessions = TimeSession.objects.filter(employee=employee, started_at__date=today)
        return f"{format_duration(logged_minutes(sessions, now))} logged today."
    return ""


def employee_card(employee, now, give_url: str) -> dict:
    data = panel(employee, now)
    day, hero = data["day"], data["hero"]
    state = card_state(day["state"], hero["state"] if hero else None)
    rows, _ = _decorate(data["up_next"], timezone.localdate(now))
    first = first_name(employee.name)
    chip_label, chip_tone = CHIPS[state]
    if state == GONE:
        chip_label = f"Gone home {format_clock(day['end'])}"
    rows = [_row(r) for r in rows[: 1 if state == GONE else 2]]
    if state == NOT_IN:
        rows_label = f"FIRST UP FOR {first.upper()}"
    elif state == GONE:
        rows_label = "FIRST UP TOMORROW"
    else:
        rows_label = f"UP NEXT FOR {first.upper()}"
    start_day_url = ""
    if state == NOT_IN:
        start_day_url = reverse("production_start_day", args=[employee.pk])
        give_url = ""
    elif give_url:
        give_url += f"?from=production&employee={employee.pk}"
    return {
        "employee": employee,
        "initials": initials(employee.name),
        "photo_url": reverse("employee_photo", args=[employee.pk])
        if employee.photo
        else "",
        "name": employee.name,
        "first": first,
        "state": state,
        "chip_label": chip_label,
        "chip_tone": chip_tone,
        "day": day,
        "day_line": _day_line(state, day),
        "item": _item_block(state, hero)
        if hero and state in (WORKING, PAUSED)
        else None,
        "rows": rows,
        "rows_label": rows_label,
        "note": _note(state, employee, first, bool(rows), now),
        "queue_url": reverse("work_plan") + f"#queue-{employee.pk}",
        "start_day_url": start_day_url,
        "give_url": give_url,
        "now": now,
    }


def live_context(now) -> dict:
    first = waiting_orders().first()
    give = reverse("assign_sheet", args=[first.pk]) if first else ""
    employees = Employee.objects.filter(active=True).order_by("name", "id")
    # sorted() is stable, so name order holds within a state
    cards = sorted(
        (employee_card(e, now, give) for e in employees),
        key=lambda c: ORDER[c["state"]],
    )
    waiting = [
        {**r, "assign_url": r["assign_url"] + "?from=production"} for r in _unassigned()
    ]
    return {
        "cards": cards,
        "waiting": waiting,
        "now": now,
        "has_employees": bool(cards),
    }
