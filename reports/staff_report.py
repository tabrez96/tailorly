"""S14 staff report: days worked, overtime, time logged and pay earned per employee."""

from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db.models import Exists, OuterRef, Q
from django.urls import reverse
from django.utils import timezone

from core.formats import format_clock, format_day, format_duration
from core.money import format_inr
from core.reports import report_row
from production import timing
from production.models import TimeSession
from production.report import MONTH, WEEK
from reports import periods, sales
from staff import pay
from staff.attendance import first_name, hourly_rate, week_start
from staff.models import DayRecord, Employee, Payout

KEYS = (WEEK, MONTH)
OVERTIME_ROWS = 5
ZERO = sales.ZERO


def employee_days(
    first: date,
    last: date,
    records: dict[date, tuple[datetime, datetime | None]],
    daily_wage: Decimal,
    multiplier: Decimal,
    today: date,
) -> list[pay.DayPay]:
    """One DayPay per day; the only place pay is worked out (staff.pay rules)."""
    count = (last - first).days + 1
    return [
        pay.day_pay(d, *records.get(d, (None, None)), daily_wage, multiplier, today)
        for d in (first + timedelta(days=i) for i in range(count))
    ]


def card(
    name: str,
    days: list[pay.DayPay],
    records: dict[date, tuple[datetime, datetime | None]],
    daily_wage: Decimal,
    multiplier: Decimal,
    logged_minutes: int,
    today: date,
    limit: int | None = None,
) -> dict:
    worked = sum(d.paid for d in days)
    day_pay = sum((d.base for d in days), ZERO)
    ot_minutes = sum(d.overtime_minutes for d in days)
    ot_pay = sum((d.overtime for d in days), ZERO)
    off = [d.date for d in days if not d.paid and d.date < today]
    off_text = (
        f"{len(off)} · " + ", ".join(f"{d:%a} {d.day}" for d in off) if off else "0"
    )
    present = sum(d.worked_minutes for d in days)
    share = round(logged_minutes * 100 / present) if present else None
    logged_text = format_duration(logged_minutes)
    overtime_text = format_duration(ot_minutes)
    rows = [
        {
            "date_text": format_day(d.date),
            "times": (
                f"{format_clock(records[d.date][0])} to "
                f"{format_clock(records[d.date][1])}"
            ),
            "overtime_text": format_duration(d.overtime_minutes),
        }
        for d in reversed(days)
        if d.overtime_minutes
    ]
    return {
        "name": name,
        "worked": worked,
        "overtime_minutes": ot_minutes,
        "off_text": off_text,
        "present_text": format_duration(present),
        "overtime_text": overtime_text,
        "logged_text": logged_text,
        "logged_line": f"{logged_text} · {share}%"
        if share is not None
        else logged_text,
        "bar": min(share or 0, 100),
        "day_pay": day_pay,
        "ot_pay": ot_pay,
        "earned": day_pay + ot_pay,
        "day_pay_label": f"Day pay {worked} × {format_inr(daily_wage)}",
        "ot_label": (
            f"Overtime pay {overtime_text} × {format_inr(hourly_rate(daily_wage))}"
            f" × {multiplier.normalize():f}"
        ),
        "overtime_rows": rows[:limit],
        "overtime_more": limit is not None and len(rows) > limit,
        "has_days": any(d.date in records for d in days),
        "empty_text": f"No days recorded for {first_name(name)} in this period.",
    }


def headline(cards: list[dict], payouts: list[Payout], due: Decimal, due_day: date):
    parts = []
    if payouts:
        paid = sum((p.amount for p in payouts), ZERO)
        paid_day = max(p.paid_on for p in payouts)
        last = "" if len({p.paid_on for p in payouts}) == 1 else ", last"
        parts.append(f"Paid {format_inr(paid)}{last} on {format_day(paid_day)}")
    if due > 0:
        parts.append(f"{format_inr(due)} due {format_day(due_day)}")
    return {
        "earned": sum((c["earned"] for c in cards), ZERO),
        "line": " · ".join(parts),
    }


def _records(employee, first: date, last: date) -> dict:
    return {
        r.date: (r.start, r.end)
        for r in employee.days.filter(date__range=(first, last))
    }


def staff_context(params, now: datetime) -> dict:
    today = timezone.localdate(now)
    nav = periods.parse(params, today, KEYS)
    all_days = params.get("days") == "all"
    lo, hi = sales._bounds(nav.first, nav.last)
    monday = week_start(today)
    paid_weeks = set(
        Payout.objects.filter(week_start=monday).values_list("employee_id", flat=True)
    )
    cards, due = [], ZERO
    in_period = (
        Q(active=True)
        | Exists(
            DayRecord.objects.filter(
                employee=OuterRef("pk"), date__range=(nav.first, nav.last)
            )
        )
        | Exists(
            Payout.objects.filter(
                employee=OuterRef("pk"), paid_on__range=(nav.first, nav.last)
            )
        )
        | Exists(
            TimeSession.objects.filter(
                employee=OuterRef("pk"), started_at__gte=lo, started_at__lt=hi
            )
        )
    )
    for e in Employee.objects.filter(in_period):
        records = _records(e, nav.first, nav.last)
        days = employee_days(
            nav.first, nav.last, records, e.daily_wage, e.overtime_multiplier, today
        )
        sessions = TimeSession.objects.filter(
            employee=e, started_at__gte=lo, started_at__lt=hi
        )
        logged = timing._logged(sessions, now) // 60
        cards.append(
            card(
                e.name,
                days,
                records,
                e.daily_wage,
                e.overtime_multiplier,
                logged,
                today,
                None if all_days else OVERTIME_ROWS,
            )
        )
        if e.pk not in paid_weeks:
            week = pay.week_pay(
                monday,
                _records(e, monday, monday + timedelta(days=6)),
                e.daily_wage,
                e.overtime_multiplier,
                today,
            )
            due += week.total
    payouts = list(Payout.objects.filter(paid_on__range=(nav.first, nav.last)))
    nav_ctx = periods.nav_context("staff_report", nav, today, KEYS)
    query = "&".join(q for q in (nav_ctx["report_query"], "days=all") if q)
    return {
        "title": "Staff",
        "overline": "REPORTS",
        "subpage": True,
        "back_url": sales.back_url(),
        "report_row": report_row("staff_report", nav_ctx["report_query"]),
        **nav_ctx,
        "hero_label": f"Earned, {periods.hero_range(nav, today)}",
        "headline": headline(cards, payouts, due, pay.pay_day(monday)),
        "cards": cards,
        "staff_url": reverse("staff"),
        "no_staff_text": "No employees yet. Add one in Staff.",
        "all_days": all_days,
        "all_days_url": f"{reverse('staff_report')}?{query}",
    }
