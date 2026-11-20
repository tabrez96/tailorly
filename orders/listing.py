"""Pure helpers for the orders list: filters, search, rows and totals."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from urllib.parse import urlencode

from django.db.models import F, Q
from django.urls import reverse

from accounts.phones import normalize_phone
from core.formats import format_day
from orders import invoice
from orders.models import Order
from staff.attendance import first_name

OPEN, READY, DELIVERED, FREE, LATE, ALL = (
    "open",
    "ready",
    "delivered",
    "free",
    "late",
    "all",
)
SHOWS = [
    (OPEN, "Open"),
    (READY, "Ready"),
    (DELIVERED, "Delivered"),
    (FREE, "Free"),
    (LATE, "Late"),
    (ALL, "All"),
]
MAX_LENGTH = 80
_NOT_READY = [Order.OPEN, Order.IN_PROGRESS]

STATUS_CHIPS = {
    Order.OPEN: ("Not started", "warn"),
    Order.IN_PROGRESS: ("In progress", "pri"),
    Order.READY: ("Ready", "ok"),
    Order.DELIVERED: ("Delivered", "grey"),
}


@dataclass(frozen=True)
class ListFilter:
    show: str = OPEN
    q: str = ""


def parse_filter(params: Mapping[str, str]) -> ListFilter:
    show = params.get("show", "")
    if show not in dict(SHOWS):
        show = OPEN
    return ListFilter(show, params.get("q", "").strip()[:MAX_LENGTH])


def filter_url(base: str, f: ListFilter) -> str:
    query = {}
    if f.show != OPEN:
        query["show"] = f.show
    if f.q:
        query["q"] = f.q
    return f"{base}?{urlencode(query)}" if query else base


def show_filter(show: str, today: date) -> Q:
    if show == OPEN:
        return Q(status__in=_NOT_READY)
    if show == READY:
        return Q(status=Order.READY)
    if show == DELIVERED:
        return Q(status=Order.DELIVERED)
    if show == FREE:
        return Q(paid_by=Order.FREE)
    if show == LATE:
        return Q(status__in=_NOT_READY, due_date__lt=today)
    return Q()


def search_filter(q: str) -> Q:
    """Match the customer name or phone, or the order number (12, #12, ORD-12)."""
    cond = Q(customer__name__icontains=q)
    num = q.strip().upper().removeprefix("ORD-").removeprefix("#")
    if num.isdigit():
        cond |= Q(number=int(num))
    text = q.strip()
    if text.startswith("+91"):
        # An explicit country prefix is not part of the stored number.
        text = text[3:]
    digits = normalize_phone(text)
    if digits:
        cond |= Q(customer__phone__contains=digits)
    return cond


def ordering(show: str) -> list:
    if show in (OPEN, READY, LATE):
        return [F("due_date").asc(nulls_last=True), "number"]
    return ["-number"]


def is_late(order, today: date) -> bool:
    return (
        order.status in _NOT_READY
        and order.due_date is not None
        and order.due_date < today
    )


def items_summary(names: list[str]) -> str:
    counts: dict[str, int] = {}
    for name in names:
        counts[name] = counts.get(name, 0) + 1
    return ", ".join(f"{name} ×{n}" if n > 1 else name for name, n in counts.items())


def _invoice(order) -> invoice.Invoice | None:
    """Built from prefetched items, materials and payments: no queries."""
    items = [
        invoice.Item(
            i.price,
            tuple(
                invoice.Material(m.quantity, m.selling_price, m.on_bill)
                for m in i.materials.all()
            ),
        )
        for i in order.items.all()
    ]
    return invoice.build(
        items, [p.amount for p in order.payments.all()], free=order.is_free
    )


def balance(order) -> Decimal | None:
    inv = _invoice(order)
    return None if inv is None else inv.balance


def order_row(order, today: date) -> dict:
    inv = _invoice(order)
    label, tone = STATUS_CHIPS[order.status]
    if order.due_date is None:
        due = ""
    elif order.due_date == today:
        due = "Due today"
    else:
        due = f"Due {format_day(order.due_date)}"
    return {
        "order": order,
        "url": reverse("order", args=[order.pk]),
        "items": items_summary([i.name for i in order.items.all()]),
        "assignee": first_name(order.assignee.name) if order.assignee else "",
        "due": due,
        "late": is_late(order, today),
        "status_label": label,
        "status_tone": tone,
        "free": order.is_free,
        "total": None if inv is None else inv.total,
        "balance": None if inv is None else inv.balance,
    }


def rows_queryset(qs):
    return qs.select_related("customer", "assignee").prefetch_related(
        "items__materials", "payments"
    )


def customer_totals(rows: list[dict]) -> tuple[Decimal, Decimal]:
    """(spent, to collect) over the orders that are not free."""
    paying = [r for r in rows if r["total"] is not None]
    spent = sum((r["total"] for r in paying), Decimal(0))
    owed = sum((r["balance"] for r in paying if r["balance"] > 0), Decimal(0))
    return spent, owed
