"""S13 payments report: received by method, still to collect, owing longest."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

from core.reports import report_row
from orders import invoice
from orders.models import Order, Payment
from production.report import DAY, MONTH, WEEK
from reports import periods, sales

TO_COLLECT = (Order.OPEN, Order.IN_PROGRESS, Order.READY, Order.DELIVERED)
METHOD_ORDER = [m for m, _ in Payment.METHODS]
KEYS = (DAY, WEEK, MONTH)
ZERO = sales.ZERO


@dataclass(frozen=True)
class Owing:
    order_id: int
    number: int
    customer: str
    status: str
    balance: Decimal  # already > 0
    delivered: date | None  # local date of delivered_at


def by_method(payments: list[tuple[str, Decimal]]) -> list[dict]:
    groups: dict[str, dict] = {}
    for method, amount in payments:
        row = groups.setdefault(method, {"count": 0, "total": ZERO})
        row["count"] += 1
        row["total"] += amount
    ranked = sorted(groups, key=lambda m: (-groups[m]["total"], METHOD_ORDER.index(m)))
    top = groups[ranked[0]]["total"] if ranked else ZERO
    labels = dict(Payment.METHODS)
    return [
        {
            "label": labels[m],
            "count": groups[m]["count"],
            "count_text": sales._plural(groups[m]["count"], "payment", "payments"),
            "total": groups[m]["total"],
            "percent": sales._percent(groups[m]["total"], top),
        }
        for m in ranked
    ]


def collect(owing: list[Owing]) -> dict:
    delivered = sum((o.balance for o in owing if o.status == Order.DELIVERED), ZERO)
    not_delivered = sum((o.balance for o in owing if o.status != Order.DELIVERED), ZERO)
    return {
        "not_delivered": not_delivered,
        "delivered": delivered,
        "total": not_delivered + delivered,
        "orders": len(owing),
    }


def _days_text(days: int | None) -> str:
    if days is None:
        return "Delivered"
    if days == 0:
        return "Delivered today"
    return f"{days} day{'' if days == 1 else 's'} since delivery"


def owing_longest(owing: list[Owing], today: date) -> list[dict]:
    delivered = [o for o in owing if o.status == Order.DELIVERED]
    delivered.sort(key=lambda o: (o.delivered or date.min, o.number))
    return [
        {
            "order_id": o.order_id,
            "customer": o.customer,
            "number_text": f"#{o.number}",
            "balance": o.balance,
            "days_text": _days_text(
                (today - o.delivered).days if o.delivered else None
            ),
        }
        for o in delivered
    ]


def load_payments(first: date, last: date) -> list[tuple[str, Decimal]]:
    return list(
        Payment.objects.filter(date__range=(first, last)).values_list(
            "method", "amount"
        )
    )


def load_owing() -> list[Owing]:
    orders = (
        Order.objects.filter(status__in=TO_COLLECT, paid_by=Order.CUSTOMER)
        .select_related("customer")
        .prefetch_related("payments", "items__materials")
    )
    owing = []
    for o in orders:
        items = [
            invoice.Item(
                i.price,
                tuple(
                    invoice.Material(m.quantity, m.selling_price, m.on_bill)
                    for m in i.materials.all()
                ),
            )
            for i in o.items.all()
        ]
        balance = invoice.build(items, [p.amount for p in o.payments.all()]).balance
        if balance <= 0:
            continue
        delivered = timezone.localdate(o.delivered_at) if o.delivered_at else None
        owing.append(
            Owing(o.pk, o.number, o.customer.name, o.status, balance, delivered)
        )
    return owing


def payments_context(params, today: date) -> dict:
    nav = periods.parse(params, today, KEYS)
    payments = load_payments(nav.first, nav.last)
    owing = load_owing()
    nav_ctx = periods.nav_context("payments_report", nav, today, KEYS)
    return {
        "title": "Payments",
        "overline": "REPORTS",
        "subpage": True,
        "back_url": sales.back_url(),
        "report_row": report_row("payments_report", nav_ctx["report_query"]),
        **nav_ctx,
        "hero_label": f"Received, {periods.hero_range(nav, today)}",
        "received": sum((a for _, a in payments), ZERO),
        "count": len(payments),
        "methods": by_method(payments),
        "collect": collect(owing),
        "owing": [
            r | {"url": reverse("order", args=[r["order_id"]])}
            for r in owing_longest(owing, today)
        ],
        "none_text": "No payments received in this period.",
        "paid_up_text": "Everyone has paid.",
    }
