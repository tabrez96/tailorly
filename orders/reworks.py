"""Add rework sheet (S04): defaults, items, staged materials."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from catalog.models import Product
from core.money import format_inr
from orders.finishing import clean_answer
from orders.materials import format_qty
from staff.attendance import first_name

DUE_DAYS = 2


def default_due(today: date) -> date:
    return today + timedelta(days=DUE_DAYS)


def item_maker(item, order_assignee):
    """Who made the item: its latest timed session, else the order's assignee."""
    sessions = sorted(item.sessions.all(), key=lambda s: s.started_at)
    if sessions:
        return sessions[-1].employee
    return order_assignee


def item_rows(order) -> list[dict]:
    rows = []
    items = order.items.prefetch_related("sessions__employee")
    for number, item in enumerate(items, start=1):
        maker = item_maker(item, order.assignee)
        rows.append(
            {
                "pk": item.pk,
                "number": number,
                "name": item.name,
                "maker_pk": maker.pk if maker else "",
                "made_by": f"made by {first_name(maker.name)}" if maker else "",
            }
        )
    return rows


@dataclass(frozen=True)
class Staged:
    product: Product
    qty: Decimal
    cost: Decimal | None  # totals for the quantity, as typed in the picker
    sell: Decimal


def read_staged(data) -> list[Staged]:
    """The materials carried in hidden fields; a bad row is dropped, not reported."""
    rows = list(
        zip(
            data.getlist("m_product"),
            data.getlist("m_qty"),
            data.getlist("m_cost"),
            data.getlist("m_sell"),
            strict=False,
        )
    )
    ids = [pk for pk, *_ in rows if pk.isdecimal()]
    products = {
        str(p.pk): p
        for p in Product.objects.filter(kind=Product.SECONDARY, active=True, pk__in=ids)
    }
    staged = []
    for pk, qty_raw, cost_raw, sell_raw in rows:
        product = products.get(pk)
        if product is None:
            continue
        answer, errors = clean_answer(qty_raw, cost_raw, sell_raw, cost_optional=True)
        if errors:
            continue
        staged.append(Staged(product, *answer))
    return staged


def staged_rows(staged) -> list[dict]:
    return [
        {
            "index": i,
            "product_pk": s.product.pk,
            "qty": str(s.qty),
            "cost": "" if s.cost is None else str(s.cost),
            "sell": str(s.sell),
            "name": s.product.name,
            "line": f"{format_qty(s.qty)} {s.product.unit} · never billed for rework",
            "amount": format_inr(s.cost) if s.cost is not None else "No cost yet",
        }
        for i, s in enumerate(staged)
    ]
