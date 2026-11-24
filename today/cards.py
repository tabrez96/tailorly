"""S02 Today: the blocks on the owner's home page."""

from datetime import timedelta
from decimal import Decimal

from django.db.models import Q
from django.urls import NoReverseMatch, reverse

from core.formats import format_clock, format_day, format_duration
from orders.listing import order_row, rows_queryset
from orders.models import Order
from production.live import GONE, IDLE, NOT_IN, ORDER, PAUSED, WORKING, employee_card
from production.plan import plan_context
from production.queue import due_text
from reports.payments import collect, load_owing, load_payments
from staff.attendance import first_name, week_start
from staff.models import Employee
from staff.pay import week_pay

DUE_DAYS = 2


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def overline(now, first: str) -> str:
    text = format_day(now)
    if first.strip():
        text += f" · Hi {first_name(first)}"
    return text.upper()


def hero_day_line(state: str, day: dict) -> str:
    if state == NOT_IN:
        return "Not started yet"
    if state == GONE:
        return f"Day {format_clock(day['start'])} – {format_clock(day['end'])}"
    return (
        f"Day started {format_clock(day['start'])} · "
        f"{format_duration(day['so_far'])} so far"
    )


def hero_now(card: dict) -> dict | None:
    item = card["item"]
    if item is None:
        return None
    working = card["state"] == WORKING
    what = f"#{item['order_number']} {item['name']}"
    if item["rework"]:
        what = f"Rework · {what}"
    now = {
        "label": "Now" if working else "Paused",
        "what": what,
        "customer": item["customer"],
        "minutes_text": item["minutes_text"],
        "timer": working,
    }
    if working:
        for key in ("base_seconds", "started_at", "estimate"):
            now[key] = item[key]
    return now


def hero_cards(now) -> list[dict]:
    employees = Employee.objects.filter(active=True).order_by("name", "id")
    cards = sorted(
        (employee_card(e, now, "") for e in employees),
        key=lambda c: ORDER[c["state"]],
    )
    for card in cards:
        pk, state = card["employee"].pk, card["state"]
        card["day_line"] = hero_day_line(state, card["day"])
        card["now_line"] = hero_now(card)
        card["start_url"] = (
            reverse("today_start_day", args=[pk]) if state == NOT_IN else ""
        )
        card["end_url"] = (
            reverse("today_end_day", args=[pk])
            if state in (WORKING, PAUSED, IDLE)
            else ""
        )
    return cards


def work_plan_card(now) -> dict:
    ctx = plan_context(now)
    n = len(ctx["unassigned"])
    hero = ctx["hero"]
    line = f"{_plural(n, 'order')} not assigned" if n else "Every order is assigned"
    if hero:
        line += f" · {hero['first']}'s next: {hero['row']['garment']}"
    return {
        "line": line,
        "chip": f"Assign {n}" if n else "",
        "url": reverse("work_plan"),
    }


def due_rows(today) -> list[dict]:
    last = today + timedelta(days=DUE_DAYS)
    orders = Order.objects.filter(
        Q(status__in=[Order.OPEN, Order.IN_PROGRESS], due_date__lte=last)
        | Q(status=Order.READY, due_date__range=(today, last))
    ).order_by("due_date", "number")
    rows = []
    for o in rows_queryset(orders):
        row = order_row(o, today)
        when = (
            f"Late · was due {format_day(o.due_date)}"
            if row["late"]
            else due_text(o.due_date, today)
        )
        rows.append({**row, "line": f"{row['items']} · {when}"})
    return rows


def money(today) -> dict:
    c = collect(load_owing())
    monday = week_start(today)
    received = sum(
        (amount for _, amount in load_payments(monday, today)), Decimal("0.00")
    )
    return {
        "collect_total": c["total"],
        "collect_count_text": _plural(c["orders"], "order"),
        "collect_url": reverse("orders") + "?show=owing",
        "received": received,
        "received_range": "Today" if monday == today else f"Mon {monday.day} – today",
        "received_url": reverse("payments_report") + "?period=week",
    }


def staff_pay(today) -> list[dict]:
    monday = week_start(today)
    rows = []
    for e in Employee.objects.filter(active=True).order_by("name", "id"):
        records = {
            r.date: (r.start, r.end) for r in e.days.filter(date__range=(monday, today))
        }
        week = week_pay(monday, records, e.daily_wage, e.overtime_multiplier, today)
        rows.append(
            {
                "name": e.name,
                "total": week.total,
                "line": f"This week so far · {_plural(week.days_paid, 'day')}",
                "url": reverse("staff") + f"?e={e.pk}",
            }
        )
    return rows


def settings_url() -> str:
    try:
        return reverse("settings")
    except NoReverseMatch:
        return ""
