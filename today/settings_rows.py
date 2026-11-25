"""S18 Settings: the rows and their live figures."""

import tomllib
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import cache

from django.conf import settings
from django.http import QueryDict
from django.urls import reverse
from django.utils import timezone

from assistants import prefs
from assistants.models import AccessKey
from core.formats import format_duration
from core.money import format_inr
from production.report import MONTH, period_range, week_so_far
from reports import payments, sales, staff_report
from reports.models import ShopSettings
from staff import pay
from staff.attendance import first_name, initials, week_start
from staff.models import Employee, Payout

ZERO = Decimal("0")


def sales_line(total: Decimal, orders: int, today: date) -> str:
    if not orders:
        return "No sales yet"
    return f"{format_inr(total)} sold in {today:%B}"


def production_line(count: int) -> str:
    if not count:
        return "Nothing finished yet"
    return f"{count} garment{'' if count == 1 else 's'} finished this week"


def payments_line(total: Decimal) -> str:
    if total <= 0:
        return "Nothing to collect"
    return f"{format_inr(total)} still to collect"


def staff_report_line(name: str | None, days: int, overtime_minutes: int) -> str:
    if name is None:
        return "No employees yet"
    overtime = (
        f"{format_duration(overtime_minutes)} overtime"
        if overtime_minutes
        else "no overtime"
    )
    days_text = f"{days} day{'' if days == 1 else 's'}"
    return f"{first_name(name)}: {days_text}, {overtime} this week"


def staff_line(names: list[str], pay_day: date) -> str:
    if not names:
        return "Add your first employee"
    who = names[0] if len(names) == 1 else f"{names[0]} and {len(names) - 1} more"
    return f"{who} · pay day {pay_day:%A}"


def running_line(total: Decimal, rate: Decimal | None) -> str:
    if rate is None:
        return "Not set yet"
    return f"{format_inr(total)} a month · {format_inr(rate)} an hour"


def phone_text(digits: str) -> str:
    if len(digits) == 10 and digits.isdigit():
        return f"{digits[:5]} {digits[5:]}"
    return digits


@cache
def app_version() -> str:
    with open(settings.BASE_DIR / "pyproject.toml", "rb") as f:
        return f"Tailorly {tomllib.load(f)['project']['version']}"


def _row(row_id: str, title: str, icon: str, line: str, url: str) -> dict:
    return {"id": row_id, "title": title, "icon": icon, "line": line, "url": url}


def report_rows(now: datetime) -> list[dict]:
    today = timezone.localdate(now)
    month = sales.summary(sales.load_sales(*period_range(MONTH, today)))
    week = week_so_far(now)
    owing = payments.collect(payments.load_owing())
    cards = staff_report.staff_context(QueryDict("period=week"), now)["cards"]
    first = cards[0] if cards else None
    return [
        _row(
            "settings-sales",
            "Sales and profit",
            "bars",
            sales_line(month["total"], month["orders"], today),
            reverse("sales_report"),
        ),
        _row(
            "settings-production",
            "Production",
            "spool",
            production_line(week["count"]),
            reverse("production_report") + "?from=settings",
        ),
        _row(
            "settings-payments",
            "Payments",
            "rupee",
            payments_line(owing["total"]),
            reverse("payments_report"),
        ),
        _row(
            "settings-staff-report",
            "Staff report",
            "clock",
            staff_report_line(
                first["name"] if first else None,
                first["worked"] if first else 0,
                first["overtime_minutes"] if first else 0,
            ),
            reverse("staff_report") + "?period=week",
        ),
    ]


def staff_row(today: date) -> dict:
    employees = list(Employee.objects.filter(active=True).order_by("name", "id"))
    monday = week_start(today)
    paid = set(
        Payout.objects.filter(week_start=monday).values_list("employee_id", flat=True)
    )
    due = sum(
        (
            pay.week_pay(
                monday,
                staff_report._records(e, monday, monday + timedelta(days=6)),
                e.daily_wage,
                e.overtime_multiplier,
                today,
            ).total
            for e in employees
            if e.pk not in paid
        ),
        ZERO,
    )
    row = _row(
        "settings-staff",
        "Staff",
        "badge",
        staff_line([e.name for e in employees], pay.pay_day(monday)),
        reverse("staff") if employees else reverse("employee_add"),
    )
    row["chip"] = f"{format_inr(due)} to pay" if due > 0 else ""
    return row


def running_row() -> dict:
    s = ShopSettings.current()
    return _row(
        "settings-running",
        "Running costs",
        "house",
        running_line(s.monthly_total(), s.running_rate()),
        reverse("running_costs"),
    )


def mcp_row() -> dict:
    s = ShopSettings.current()
    line = prefs.settings_line(s.mcp_on, AccessKey.active().count(), s.mcp_can_change)
    return _row("settings-mcp", "MCP server", "plug", line, reverse("assistants"))


def account(user) -> dict:
    name = user.first_name or user.username
    return {
        "name": name,
        "initials": initials(name),
        "line": f"Owner · {phone_text(user.username)}",
    }
