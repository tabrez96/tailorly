"""S12 production report: periods, bars and summaries, plus the page context."""

import calendar
from datetime import date, datetime, time, timedelta
from urllib.parse import urlencode

from django.urls import reverse
from django.utils import timezone

from catalog.models import Product
from core.formats import format_clock, format_day, format_duration, format_month
from core.reports import report_row
from orders.listing import LATE, SOON, STATUS_CHIPS, show_filter
from orders.models import Order, OrderItem
from production import timing
from production.models import TimeSession
from production.record import MINUS, difference_text
from staff.attendance import first_name, week_start
from staff.models import DayRecord
from staff.pay import overtime_minutes, worked_minutes

DAY, WEEK, MONTH = "day", "week", "month"
PERIODS = [(DAY, "Day"), (WEEK, "Week"), (MONTH, "Month")]
FROMS = {"production": "production", "today": "today"}
FURTHEST = 3
SOON_DAYS = 7
DASH = "\N{EN DASH}"


def parse_period(params, today: date) -> tuple[str, date]:
    period = params.get("period", "")
    if period not in dict(PERIODS):
        period = WEEK
    try:
        day = date.fromisoformat(params.get("date", ""))
    except ValueError:
        day = today
    return period, min(day, today)


def period_range(period: str, day: date) -> tuple[date, date]:
    if period == DAY:
        return day, day
    if period == WEEK:
        first = week_start(day)
        return first, first + timedelta(days=6)
    last = calendar.monthrange(day.year, day.month)[1]
    return day.replace(day=1), day.replace(day=last)


def step(period: str, day: date, n: int) -> date:
    """First day of the previous (n=-1) or next (n=1) period."""
    if period == DAY:
        return day + timedelta(days=n)
    if period == WEEK:
        return week_start(day) + timedelta(days=7 * n)
    month = day.month - 1 + n
    return date(day.year + month // 12, month % 12 + 1, 1)


def period_label(period: str, first: date, last: date, today: date) -> str:
    current = first <= today <= last
    if period == DAY:
        return format_day(first)
    if period == WEEK:
        if first.month == last.month:
            text = f"{first.day}{DASH}{last.day} {last:%b}"
        else:
            text = f"{first.day} {first:%b}{DASH}{last.day} {last:%b}"
        return f"This week · {text}" if current else text
    text = format_month(first)
    return f"This month · {text}" if current else text


def _span(a: date, b: date) -> str:
    return f"{a.day}{DASH}{b.day}" if a != b else f"{a.day}"


def bars(
    period: str, first: date, last: date, finished: list[date], today: date
) -> list[dict]:
    spans = []
    if period == WEEK:
        for i in range(7):
            d = first + timedelta(days=i)
            spans.append((f"{d:%a}", d, d))
    else:
        monday = week_start(first)
        while monday <= last:
            a, b = max(monday, first), min(monday + timedelta(days=6), last)
            spans.append((_span(a, b), a, b))
            monday += timedelta(days=7)
    counts = [sum(1 for d in finished if a <= d <= b) for _, a, b in spans]
    biggest = max(counts, default=0)
    return [
        {
            "label": label,
            "count": count,
            "percent": round(count * 100 / biggest) if biggest else 0,
            "future": a > today,
        }
        for (label, a, _), count in zip(spans, counts, strict=True)
    ]


def week_caption(first: date, today: date) -> str:
    """Which days of the current week are counted so far, and which are to come."""
    if not first <= today < first + timedelta(days=6):
        return ""
    past = (today - first).days
    start, end = first, today
    came = f"{start:%a}" if past == 0 else f"{start:%a} to {end:%a}"
    nxt, sunday = today + timedelta(days=1), first + timedelta(days=6)
    to_come = f"{sunday:%a}" if nxt == sunday else f"{nxt:%a} to {sunday:%a}"
    return f"{came} so far. {to_come} still to come."


def on_time(delivered: list[tuple[date, date]]) -> tuple[int, int]:
    """(delivered on or before the due date, delivered) from (day, due) pairs."""
    return sum(1 for day, due in delivered if day <= due), len(delivered)


def _diff_text(diff: int) -> str:
    if diff == 0:
        return "on time"
    return (
        f"+{format_duration(diff)}" if diff > 0 else f"{MINUS}{format_duration(-diff)}"
    )


def estimate_summary(rows: list[dict]) -> dict | None:
    """Totals and the garments furthest from their estimate; None without estimates."""
    rated = [r for r in rows if r["estimate"] is not None]
    if not rated:
        return None
    took = sum(r["took"] for r in rated)
    estimated = sum(r["estimate"] for r in rated)
    longer = sum(1 for r in rated if r["took"] > r["estimate"])
    ranked = sorted(rated, key=lambda r: (-abs(r["took"] - r["estimate"]), r["name"]))
    furthest = []
    for r in ranked:
        diff = r["took"] - r["estimate"]
        furthest.append(
            r
            | {"diff_text": _diff_text(diff), "diff_tone": "warn" if diff > 0 else "ok"}
        )
    line = (
        f"{difference_text(took, estimated)} · "
        f"{longer} of {len(rated)} took longer than estimated"
    )
    return {
        "estimated_text": format_duration(estimated),
        "took_text": format_duration(took),
        "line": line,
        "longer": longer,
        "with_estimate": len(rated),
        "furthest": furthest,
        "has_more": len(furthest) > FURTHEST,
    }


def by_garment(rows: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(r["name"], []).append(r)
    result = []
    for name, group in groups.items():
        rated = [r["estimate"] for r in group if r["estimate"] is not None]
        result.append(
            {
                "name": name,
                "count": len(group),
                "avg_took_text": format_duration(
                    round(sum(r["took"] for r in group) / len(group))
                ),
                "avg_estimate_text": format_duration(round(sum(rated) / len(rated)))
                if rated
                else "—",
            }
        )
    return sorted(result, key=lambda g: (-g["count"], g["name"]))


def day_line(
    first: str, start: datetime, end: datetime | None, logged: int, overtime: int
) -> str:
    work = f"{format_duration(logged)} on garments"
    if end is None:
        return f"{first}: {format_clock(start)}, still in · {work}"
    line = f"{first}: {format_clock(start)} to {format_clock(end)} · {work}"
    if overtime > 0:
        line += f" · {format_duration(overtime)} overtime"
    return line


def _bounds(first: date, last: date) -> tuple[datetime, datetime]:
    lo = timezone.make_aware(datetime.combine(first, time.min))
    hi = timezone.make_aware(datetime.combine(last + timedelta(days=1), time.min))
    return lo, hi


def finished_items(first: date, last: date):
    """Custom garments finished in the range (ready-made items aren't production)."""
    lo, hi = _bounds(first, last)
    return (
        OrderItem.objects.filter(
            type=Product.CUSTOM,
            status=OrderItem.FINISHED,
            finished_at__gte=lo,
            finished_at__lt=hi,
        )
        .exclude(order__status=Order.DRAFT)
        .select_related("order__customer", "order__assignee")
        .prefetch_related("sessions__employee")
    )


def _row(item, now) -> dict:
    sessions = list(item.sessions.all())
    return {
        "item": item,
        "name": item.name,
        "number": f"#{item.order.number}",
        "customer": item.order.customer.name,
        "finished_at": item.finished_at,
        "took": timing._logged(sessions, now) // 60,
        "estimate": item.estimate_minutes,
        "maker": sessions[-1].employee if sessions else item.order.assignee,
        "url": reverse("production_record", args=[item.pk]),
    }


def garment_sessions(lo: datetime, hi: datetime) -> list:
    """Sessions on garments that started in the range (rework has no item)."""
    return list(
        TimeSession.objects.filter(
            item__isnull=False,
            item__type=Product.CUSTOM,
            started_at__gte=lo,
            started_at__lt=hi,
        ).select_related("employee")
    )


def delivered_orders(lo: datetime, hi: datetime):
    """Orders delivered in the range that had garments made (not ready-made sales)."""
    return Order.objects.filter(
        delivered_at__gte=lo,
        delivered_at__lt=hi,
        due_date__isnull=False,
        items__type=Product.CUSTOM,
    ).distinct()


def late_now(today: date) -> int:
    return Order.objects.filter(show_filter(LATE, today)).count()


def _minutes(sessions, now) -> int:
    return timing._logged(sessions, now) // 60


def by_employee(rows, sessions, records, now) -> list[dict]:
    today = timezone.localdate(now)
    people = {}
    for r in rows:
        if r["maker"]:
            people.setdefault(r["maker"].pk, r["maker"])
    for s in sessions:
        people.setdefault(s.employee_id, s.employee)
    for rec in records:
        people.setdefault(rec.employee_id, rec.employee)
    result = []
    for pk, person in people.items():
        logged = _minutes([s for s in sessions if s.employee_id == pk], now)
        present = sum(
            worked_minutes(rec.start, rec.end or now)
            for rec in records
            if rec.employee_id == pk and (rec.end or rec.date >= today)
        )
        count = sum(1 for r in rows if r["maker"] and r["maker"].pk == pk)
        noun = "garment" if count == 1 else "garments"
        line = f"{count} {noun} · {format_duration(logged)} logged"
        if present:
            line += f" of {format_duration(present)} present"
        result.append({"name": person.name, "line": line})
    return sorted(result, key=lambda e: e["name"])


def _day_records(first: date, last: date) -> list:
    return list(
        DayRecord.objects.filter(date__gte=first, date__lte=last).select_related(
            "employee"
        )
    )


def coming_up(today: date) -> dict:
    due_by = week_start(today) + timedelta(days=6)
    soon = Order.objects.filter(show_filter(SOON, today)).count()
    items = (
        OrderItem.objects.filter(
            type=Product.CUSTOM,
            status=OrderItem.NOT_STARTED,
            order__status__in=[Order.OPEN, Order.IN_PROGRESS],
            order__due_date__gte=today,
            order__due_date__lte=due_by,
        )
        .select_related("order__customer")
        .order_by("order__due_date", "order__number", "pk")
    )
    return {
        "orders": soon,
        "url": reverse("orders") + "?show=soon",
        "not_started": [
            {
                "name": i.name,
                "number": f"#{i.order.number}",
                "customer": i.order.customer.name,
                "due_text": f"due {format_day(i.order.due_date)}",
            }
            for i in items
        ],
    }


def still_in_progress(items) -> list[dict]:
    """Unfinished garments on the orders of the day's finished garments."""
    pending = (
        OrderItem.objects.filter(
            order__in={i.order_id for i in items}, type=Product.CUSTOM
        )
        .exclude(status=OrderItem.FINISHED)
        .select_related("order__customer")
        .order_by("order__number", "pk")
    )
    rows = []
    for i in pending:
        label, tone = (
            STATUS_CHIPS[Order.OPEN]
            if i.status == OrderItem.NOT_STARTED
            else STATUS_CHIPS[Order.IN_PROGRESS]
        )
        rows.append(
            {
                "name": i.name,
                "number": f"#{i.order.number}",
                "customer": i.order.customer.name,
                "due_text": f"due {format_day(i.order.due_date)}"
                if i.order.due_date
                else "",
                "chip": label,
                "tone": tone,
            }
        )
    return rows


def _url(period: str, day: date, frm: str, extra: dict | None = None) -> str:
    today = timezone.localdate()
    query = {}
    if period != WEEK:
        query["period"] = period
    current = period_range(period, today)
    if not current[0] <= day <= current[1]:
        query["date"] = day.isoformat()
    if frm != "production":
        query["from"] = frm
    query.update(extra or {})
    base = reverse("production_report")
    return f"{base}?{urlencode(query)}" if query else base


def _day_lines(sessions, records, now) -> list[str]:
    lines = []
    for rec in sorted(records, key=lambda r: r.employee.name):
        mine = [s for s in sessions if s.employee_id == rec.employee_id]
        over = overtime_minutes(rec.start, rec.end) if rec.end else 0
        lines.append(
            day_line(
                first_name(rec.employee.name),
                rec.start,
                rec.end,
                _minutes(mine, now),
                over,
            )
        )
    return lines


def report_context(params, now: datetime) -> dict:
    today = timezone.localdate(now)
    period, day = parse_period(params, today)
    first, last = period_range(period, day)
    lo, hi = _bounds(first, last)
    frm = params.get("from", "")
    frm = frm if frm in FROMS else "production"
    items = list(finished_items(first, last))
    rows = [_row(i, now) for i in items]
    nxt = step(period, day, 1)
    this_week = _url(WEEK, today, frm)
    if period == DAY:
        empty_title = f"Nothing finished on {format_day(first)}"
    elif period == WEEK:
        empty_title = (
            "Nothing finished this week"
            if first <= today <= last
            else f"Nothing finished in {period_label(period, first, last, today)}"
        )
    else:
        empty_title = f"Nothing finished in {format_month(first)}"
    ctx = {
        "title": "Production",
        "overline": "REPORTS",
        "subpage": True,
        "tab": "production",
        "back_url": reverse(FROMS[frm]),
        "report_row": report_row("production_report", f"from={frm}"),
        "segments": [
            {
                "id": f"period-{key}",
                "label": label,
                "url": _url(key, today, frm),
                "selected": key == period,
            }
            for key, label in PERIODS
        ],
        "label": period_label(period, first, last, today),
        "prev_url": _url(period, step(period, day, -1), frm),
        "next_url": "" if nxt > today else _url(period, nxt, frm),
        "period": period,
        "is_empty": not rows,
        "empty_title": empty_title,
        "this_week_url": this_week,
    }
    sessions = garment_sessions(lo, hi)
    records = _day_records(first, last)
    if period == DAY:
        ctx |= {
            "count": len(rows),
            "finished": sorted(rows, key=lambda r: r["finished_at"]),
            "is_today": day == today,
            "day_heading": "Finished today"
            if day == today
            else f"Finished on {format_day(day)}",
            "day_lines": _day_lines(sessions, records, now),
            "still": still_in_progress(items),
        }
        return ctx
    delivered = [
        (timezone.localdate(o.delivered_at), o.due_date)
        for o in delivered_orders(lo, hi)
    ]
    on_time_count, of = on_time(delivered)
    estimates = estimate_summary(rows)
    if estimates and params.get("estimates") != "all":
        estimates = estimates | {"furthest": estimates["furthest"][:FURTHEST]}
    shown_all = params.get("estimates") == "all"
    late = late_now(today)
    ctx |= {
        "count": len(rows),
        "delivered": of,
        "logged_text": format_duration(_minutes(sessions, now)),
        "bars": bars(
            period,
            first,
            last,
            [timezone.localdate(r["finished_at"]) for r in rows],
            today,
        ),
        "caption": week_caption(first, today) if period == WEEK else "",
        "on_time": on_time_count,
        "of": of,
        "late": late,
        "estimates": estimates,
        "see_all": bool(estimates and estimates["has_more"] and not shown_all),
        "see_all_url": _url(period, day, frm, {"estimates": "all"}),
        "garments": by_garment(rows),
        "employees": by_employee(rows, sessions, records, now),
        "coming_up": coming_up(today),
    }
    return ctx


def week_so_far(now: datetime) -> dict:
    today = timezone.localdate(now)
    first, last = period_range(WEEK, today)
    lo, hi = _bounds(first, last)
    rows = [_row(i, now) for i in finished_items(first, last)]
    on_time_count, of = on_time(
        [
            (timezone.localdate(o.delivered_at), o.due_date)
            for o in delivered_orders(lo, hi)
        ]
    )
    summary = estimate_summary(rows)
    return {
        "count": len(rows),
        "on_time": on_time_count,
        "of": of,
        "late": late_now(today),
        "longer": summary["longer"] if summary else 0,
        "url": reverse("production_report"),
    }
