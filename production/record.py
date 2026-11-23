"""S17 Production record: pure helpers plus the page context for an item or a rework."""

from django.db.models import F
from django.urls import reverse
from django.utils import timezone

from core.formats import format_clock, format_day, format_duration
from orders.models import OrderItem
from production import estimates, timing
from production.live import item_position, item_url
from staff.attendance import first_name

TONES = {"not_started": "warn", "in_progress": "pri", "finished": "ok"}
WITHIN = 0.10  # "within 10% of the estimate"
PATTERN_SAMPLE = 5
MINUS = "\N{MINUS SIGN}"


def difference_text(took: int, estimate: int | None) -> str:
    if not estimate:
        return ""
    diff = took - estimate
    if diff == 0:
        return "right on the estimate"
    pct = round(abs(diff) * 100 / estimate)
    if diff > 0:
        return f"{format_duration(diff)} over (+{pct}%)"
    return f"{format_duration(-diff)} under ({MINUS}{pct}%)"


def left_text(logged: int, estimate: int) -> str:
    if estimate - logged > 0:
        return f"about {format_duration(estimate - logged)} left"
    return f"{format_duration(logged - estimate)} over"


def progress_percent(logged: int, estimate: int) -> int:
    if estimate <= 0:
        return 100
    return min(100, round(logged * 100 / estimate))


def bar_rows(
    estimate: int | None, took: int, usual: int | None, garment: str
) -> list[dict]:
    rows = []
    if estimate:
        rows.append(("Estimate", estimate, "estimate"))
    rows.append(("Took", took, "took"))
    if usual:
        rows.append((f"Usual {garment.lower()}", usual, "usual"))
    longest = max(minutes for _, minutes, _ in rows) or 1
    return [
        {
            "label": label,
            "minutes_text": format_duration(minutes),
            "percent": max(2, round(minutes * 100 / longest)) if minutes else 0,
            "tone": tone,
        }
        for label, minutes, tone in rows
    ]


def plural(garment: str) -> str:
    word = garment.lower()
    return word + ("es" if word.endswith("s") else "s")


def pattern_line(first: str, garment: str, results: list[tuple[int, int]]) -> str:
    if len(results) < 2:
        return ""
    count = len(results)
    within = sum(1 for took, est in results if abs(took - est) <= est * WITHIN)
    tail = f"{plural(garment)} within 10% of the estimate."
    if within == count:
        return f"{first} has finished the last {count} {tail}"
    return f"{first} has finished {within} of the last {count} {tail}"


def working_days(sessions) -> int:
    return len({timezone.localdate(s.started_at) for s in sessions})


def due_state(due, finished_at, today) -> tuple[str, str]:
    if due is None:
        return "No due date", ""
    if finished_at is not None:
        on_time = timezone.localdate(finished_at) <= due
        return format_day(due), "On time" if on_time else "Late"
    if today <= due:
        return f"{format_day(due)} · on track", ""
    return format_day(due), "Late"


def _count(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def production_line(
    minutes: int, estimate: int | None, sessions: int, started: bool
) -> str:
    if not started and sessions == 0:
        if estimate:
            return f"Not started · est. {format_duration(estimate)}"
        return "Not started"
    took = format_duration(minutes)
    count = _count(sessions, "session")
    if estimate:
        return f"{took} of {format_duration(estimate)} est. · {count}"
    return f"{took} · {count}"


def session_rows(sessions, now) -> tuple[list[dict], int]:
    rows = []
    for s in sessions:
        end = s.ended_at or timing._stale_cutoff(s, now)
        start_text = format_clock(s.started_at)
        times = (
            f"{start_text} to {format_clock(end)}"
            if end
            else f"{start_text}, still running"
        )
        seconds = timing.session_seconds(s.started_at, end, now)
        rows.append(
            {
                "day": format_day(s.started_at),
                "times": times,
                "minutes_text": format_duration(seconds // 60),
            }
        )
    return rows, timing._logged(sessions, now) // 60


def _hero(state, estimate, took, running) -> dict:
    hero = {
        "state": state,
        "label": "",
        "big": "",
        "sub": "",
        "sub_strong": "",
        "chip": "",
        "percent": None,
    }
    est_text = format_duration(estimate) if estimate else ""
    if state == "finished":
        hero["label"] = "Time taken"
        hero["big"] = format_duration(took)
        if estimate:
            hero["sub"] = f"Your estimate {est_text} · "
            hero["sub_strong"] = difference_text(took, estimate)
    elif state == "in_progress":
        hero["label"] = "Logged so far"
        hero["big"] = format_duration(took)
        hero["chip"] = "Running" if running else "Paused"
        if estimate:
            hero["sub"] = f"Your estimate {est_text} · {left_text(took, estimate)}"
            hero["percent"] = progress_percent(took, estimate)
    else:
        hero["label"] = "Estimate"
        hero["big"] = est_text or "—"
        hero["sub"] = "Not started"
    return hero


def _card(item, status, due, order) -> dict:
    pos, count = item_position(item)
    photos = list(item.photos.all())
    sub = order.customer.name + (f" · due {format_day(due)}" if due else "")
    label, tone = status
    return {
        "url": item_url(item),
        "thumb": timing._thumb(item)[0],
        "photo_count": len(photos),
        "name": item.name,
        "title": f"#{order.number} · item {pos} of {count}",
        "sub": sub,
        "status_label": label,
        "status_tone": tone,
    }


def _pattern(item, maker_first, now) -> tuple[list[dict], str, str]:
    order = item.order
    usual_m, samples = estimates.usual(item.product)
    word = plural(item.name)
    bars = bar_rows(
        item.estimate_minutes,
        timing._logged(list(item.sessions.all()), now) // 60,
        usual_m if samples else None,
        item.name,
    )
    caption = (
        f"Usual = average of the last {samples} {word}."
        if samples
        else f"No usual time yet: fewer than {estimates.MIN_FINISHED} finished {word}."
    )
    results: list[tuple[int, int]] = []
    if item.product_id and order.assignee_id:
        peers = (
            OrderItem.objects.filter(
                product=item.product,
                order__assignee=order.assignee,
                status=OrderItem.FINISHED,
                estimate_minutes__isnull=False,
            )
            .order_by(F("finished_at").desc(nulls_last=True), "-id")
            .prefetch_related("sessions")[: estimates.FETCH]
        )
        for peer in peers:
            logged = timing._logged(list(peer.sessions.all()), now) // 60
            if logged > 0:
                results.append((logged, peer.estimate_minutes))
        results = results[:PATTERN_SAMPLE]
    return bars, caption, pattern_line(maker_first, item.name, results)


def _details(maker, estimate_row, sessions, finished_at, rows_due, now) -> list[dict]:
    details = [{"label": "Made by", "value": maker, "chip": ""}]
    if estimate_row:
        details.append({"label": "Estimate set", "value": estimate_row, "chip": ""})
    if sessions:
        first = sessions[0].started_at
        value = f"{format_day(first)}, {format_clock(first)}"
        details.append({"label": "Started", "value": value, "chip": ""})
    if finished_at:
        value = f"{format_day(finished_at)}, {format_clock(finished_at)}"
        details.append({"label": "Finished", "value": value, "chip": ""})
        days = working_days(sessions)
        elapsed = f"{_count(days, 'working day')} · {_count(len(sessions), 'session')}"
        details.append({"label": "Elapsed", "value": elapsed, "chip": ""})
    text, chip = due_state(rows_due, finished_at, timezone.localdate(now))
    details.append(
        {
            "label": "Due",
            "value": text,
            "chip": chip,
            "chip_tone": "ok" if chip == "On time" else "bad",
        }
    )
    return details


def _estimate_row(item) -> str:
    if not item.estimate_minutes:
        return ""
    if not item.estimate_set_at:
        return "Not recorded"
    day = format_day(item.estimate_set_at)
    return f"{day}, " + (
        "usual time at start" if item.estimate_from_usual else "when assigned"
    )


def _maker(assignee, sessions) -> str:
    if assignee:
        return assignee.name
    if sessions:
        return sessions[-1].employee.name
    return "Not assigned"


def _running(sessions, now) -> bool:
    return any(
        s.ended_at is None and timing._stale_cutoff(s, now) is None for s in sessions
    )


def _shared(title, back_item, sessions, now, maker_name) -> dict:
    rows, total = session_rows(sessions, now)
    first = first_name(maker_name) or "the employee"
    return {
        "title": title,
        "overline": "PRODUCTION RECORD",
        "subpage": True,
        "tab": "orders",
        "back_url": item_url(back_item),
        "sessions": rows,
        "total_text": format_duration(total),
        "session_count": len(rows),
        "footnote": (
            f"From {first}'s Start, Pause and Finish on My work. "
            "Pauses and other items are not counted."
        ),
        "reason": "",
        "bars": [],
        "bars_caption": "",
        "pattern": "",
        "note": None,
        "reworks": [],
    }


def item_record(item, now) -> dict:
    order = item.order
    sessions = list(item.sessions.all())
    maker = _maker(order.assignee, sessions)
    ctx = _shared(item.name, item, sessions, now, maker)
    took = timing._logged(sessions, now) // 60
    state = item.status
    status = (item.get_status_display(), TONES[state])
    ctx["hero"] = _hero(state, item.estimate_minutes, took, _running(sessions, now))
    ctx["card"] = _card(item, status, order.due_date, order)
    if state == OrderItem.FINISHED:
        ctx["bars"], ctx["bars_caption"], ctx["pattern"] = _pattern(
            item, first_name(maker), now
        )
        ctx["note"] = _note(item)
    ctx["details"] = _details(
        maker,
        _estimate_row(item),
        sessions,
        item.finished_at if state == OrderItem.FINISHED else None,
        order.due_date,
        now,
    )
    for n, rework in enumerate(item.reworks.all(), start=1):
        minutes = timing._logged(list(rework.sessions.all()), now) // 60
        ctx["reworks"].append(
            {
                "url": reverse("rework_record", args=[rework.pk]),
                "label": f"R{n} · {rework.get_reason_display()}",
                "time": format_duration(minutes),
            }
        )
    return ctx


def _note(item) -> dict:
    return {
        "url": reverse("production_record_note", args=[item.pk]),
        "value": item.delay_note,
    }


def rework_record(rework, now) -> dict:
    item = rework.item
    order = item.order
    sessions = list(rework.sessions.all())
    maker = _maker(rework.assignee, sessions)
    ctx = _shared(f"Rework · {item.name}", item, sessions, now, maker)
    took = timing._logged(sessions, now) // 60
    if rework.finished_at:
        state = "finished"
    elif sessions:
        state = "in_progress"
    else:
        state = "not_started"
    ctx["reason"] = rework.get_reason_display()
    ctx["hero"] = _hero(state, rework.estimate_minutes, took, _running(sessions, now))
    labels = {"finished": "Finished", "in_progress": "In progress"}
    ctx["card"] = _card(
        item, (labels.get(state, "Not started"), TONES[state]), rework.due_date, order
    )
    ctx["details"] = _details(
        maker, "", sessions, rework.finished_at, rework.due_date, now
    )
    return ctx
