"""S11 sales report: periods, totals and grouping, plus the page context."""

import calendar
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from urllib.parse import urlencode

from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from core.reports import report_row
from orders import invoice
from orders.models import Order
from staff.attendance import week_start

MONTH, LAST_MONTH, WEEK, CUSTOM = "month", "last_month", "week", "custom"
PERIODS = [MONTH, LAST_MONTH, WEEK, CUSTOM]
CUSTOMER, GARMENT = "customer", "garment"
DASH = "\N{EN DASH}"
ZERO = Decimal("0.00")
EARLIEST = date(2000, 1, 1)


@dataclass(frozen=True)
class Period:
    key: str
    first: date
    last: date


@dataclass(frozen=True)
class Line:
    name: str  # OrderItem.name
    total: Decimal  # invoice.item_total: price + on-bill materials


@dataclass(frozen=True)
class Sale:
    customer_id: int
    customer: str
    total: Decimal  # the order's invoice total
    balance: Decimal  # the order's invoice balance (may be negative)
    lines: tuple[Line, ...]


def month_range(day: date) -> tuple[date, date]:
    last = calendar.monthrange(day.year, day.month)[1]
    return day.replace(day=1), day.replace(day=last)


def period_range(key: str, today: date) -> tuple[date, date]:
    if key == LAST_MONTH:
        return month_range(today.replace(day=1) - timedelta(days=1))
    if key == WEEK:
        first = week_start(today)
        return first, first + timedelta(days=6)
    return month_range(today)


def _date_or(value: str, fallback: date) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return fallback


def parse_period(params, today: date) -> Period:
    key = params.get("period", "")
    if key not in PERIODS:
        key = MONTH
    if key != CUSTOM:
        return Period(key, *period_range(key, today))
    first = _date_or(params.get("from", ""), today.replace(day=1))
    last = _date_or(params.get("to", ""), today)
    if first > last:
        first, last = last, first
    # Orders can't be dated in the future; the floor keeps the day-after bound in range.
    first = min(max(first, EARLIEST), today)
    last = min(max(last, EARLIEST), today)
    return Period(CUSTOM, first, last)


def _day(d: date) -> str:
    return f"{d.day} {d:%b}"


def range_text(first: date, last: date) -> str:
    if first == last:
        return _day(first)
    if (first.year, first.month) == (last.year, last.month):
        return f"{first.day}{DASH}{_day(last)}"
    if first.year == last.year:
        return f"{_day(first)}{DASH}{_day(last)}"
    return f"{_day(first)} {first.year}{DASH}{_day(last)} {last.year}"


def hero_label(period: Period, today: date) -> str:
    end = period.last if today < period.first else min(period.last, today)
    return f"Sales, {range_text(period.first, end)}"


def empty_text(period: Period) -> str:
    if period.key in (MONTH, LAST_MONTH):
        return f"No sales in {period.first:%B} {period.first.year}."
    return f"No sales in {range_text(period.first, period.last)}."


def option_label(key: str, today: date) -> str:
    if key == MONTH:
        return f"{today:%B} {today.year}"
    if key == LAST_MONTH:
        last = today.replace(day=1) - timedelta(days=1)
        return f"{last:%B} {last.year}"
    return "This week" if key == WEEK else "Custom range"


def period_query(period: Period) -> str:
    query = {"period": period.key}
    if period.key == CUSTOM:
        query |= {"from": period.first.isoformat(), "to": period.last.isoformat()}
    return urlencode(query)


def page_url(period: Period, group: str) -> str:
    url = f"{reverse('sales_report')}?{period_query(period)}"
    return f"{url}&group={GARMENT}" if group == GARMENT else url


def summary(sales: list[Sale]) -> dict:
    return {
        "total": sum((s.total for s in sales), ZERO),
        "orders": len(sales),
        "customers": len({s.customer_id for s in sales}),
        "to_collect": sum((max(s.balance, ZERO) for s in sales), ZERO),
    }


def _percent(value: Decimal, top: Decimal) -> int:
    return round(value * 100 / top) if top > 0 else 0


def _ranked(rows: list[dict]) -> list[dict]:
    rows = sorted(rows, key=lambda r: (-r["total"], r["name"]))
    top = rows[0]["total"] if rows else ZERO
    return [r | {"percent": _percent(r["total"], top)} for r in rows]


def _plural(count: int, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"


def by_customer(sales: list[Sale]) -> list[dict]:
    groups: dict[int, dict] = {}
    for s in sales:
        row = groups.setdefault(
            s.customer_id,
            {
                "customer_id": s.customer_id,
                "name": s.customer,
                "total": ZERO,
                "orders": 0,
            },
        )
        row["total"] += s.total
        row["orders"] += 1
    rows = [
        r | {"orders_text": _plural(r["orders"], "order", "orders")}
        for r in groups.values()
    ]
    return _ranked(rows)


def by_garment(sales: list[Sale]) -> list[dict]:
    groups: dict[str, dict] = {}
    for s in sales:
        for line in s.lines:
            row = groups.setdefault(
                line.name, {"name": line.name, "count": 0, "total": ZERO}
            )
            row["count"] += 1
            row["total"] += line.total
    rows = [
        r | {"count_text": _plural(r["count"], "piece", "pieces")}
        for r in groups.values()
    ]
    return _ranked(rows)


def _bounds(first: date, last: date) -> tuple[datetime, datetime]:
    lo = timezone.make_aware(datetime.combine(first, time.min))
    hi = timezone.make_aware(datetime.combine(last + timedelta(days=1), time.min))
    return lo, hi


def load_sales(first: date, last: date) -> list[Sale]:
    """Placed, non-free orders created in the range (local dates)."""
    lo, hi = _bounds(first, last)
    orders = (
        Order.objects.filter(created_at__gte=lo, created_at__lt=hi)
        .exclude(status=Order.DRAFT)
        .exclude(paid_by=Order.FREE)
        .select_related("customer")
        .prefetch_related("payments", "items__materials")
    )
    sales = []
    for o in orders:
        db_items = list(o.items.all())
        items = [
            invoice.Item(
                i.price,
                tuple(
                    invoice.Material(m.quantity, m.selling_price, m.on_bill)
                    for m in i.materials.all()
                ),
            )
            for i in db_items
        ]
        inv = invoice.build(items, [p.amount for p in o.payments.all()])
        lines = tuple(
            Line(i.name, invoice.item_total(it))
            for i, it in zip(db_items, items, strict=True)
        )
        sales.append(
            Sale(o.customer_id, o.customer.name, inv.total, inv.balance, lines)
        )
    return sales


def back_url() -> str:
    try:
        return reverse("settings")
    except NoReverseMatch:
        return reverse("today")


def sales_context(params, today: date) -> dict:
    period = parse_period(params, today)
    group = GARMENT if params.get("group") == GARMENT else CUSTOMER
    sales = load_sales(period.first, period.last)
    if group == CUSTOMER:
        rows = [
            r | {"url": reverse("customer", args=[r["customer_id"]])}
            for r in by_customer(sales)
        ]
    else:
        rows = by_garment(sales)
    return {
        "title": "Reports",
        "subpage": True,
        "back_url": back_url(),
        "report_row": report_row("sales_report", period_query(period)),
        "period": period,
        "options": [
            {
                "value": k,
                "label": option_label(k, today),
                "selected": k == period.key,
            }
            for k in PERIODS
        ],
        "is_custom": period.key == CUSTOM,
        "group": group,
        "segments": [
            {
                "id": f"group-{g}",
                "label": f"By {g}",
                "url": page_url(period, g),
                "selected": group == g,
            }
            for g in (CUSTOMER, GARMENT)
        ],
        "hero_label": hero_label(period, today),
        "summary": summary(sales),
        "rows": rows,
        "is_empty": not sales,
        "empty_text": empty_text(period),
    }
