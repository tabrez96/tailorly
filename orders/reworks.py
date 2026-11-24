"""Add rework sheet (S04): defaults, items, staged materials."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.urls import reverse

from catalog.models import Product
from core.formats import format_day, format_duration
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


STATUS = {
    "not_started": ("Not started", "warn"),
    "in_progress": ("In progress", "pri"),
    "finished": ("Finished", "ok"),
}


def _duration(minutes: int) -> str:
    """Like format_duration, but minutes are padded next to hours: 3h 05m."""
    hours, rest = divmod(minutes, 60)
    return f"{hours}h {rest:02d}m" if hours and rest else format_duration(minutes)


def rework_state(finished: bool, logged: int, has_sessions: bool) -> str:
    if finished:
        return "finished"
    return "in_progress" if has_sessions else "not_started"


def minutes_text(logged: int, estimate: int, finished: bool) -> str:
    return f"{logged} min" if finished else f"{logged} of {estimate} min"


def materials_text(lines) -> str:
    if not lines:
        return "No materials"
    return " · ".join(
        f"{line.name} {format_qty(line.quantity)} {line.unit}" for line in lines
    )


def minus_inr(amount: Decimal) -> str:
    return f"−{format_inr(amount)}" if amount else format_inr(amount)


def time_with_rework(logged: int, rework: int) -> str:
    text = _duration(logged)
    return f"{text} + {_duration(rework)} rework" if rework else text


def ready_made_with_rework(rework: int) -> str:
    return f"Ready-made + {_duration(rework)} rework" if rework else "Ready-made"


def rework_detail(t) -> str:
    noun = "rework" if t.count == 1 else "reworks"
    return (
        f"{t.count} {noun} · {_duration(t.minutes)} · staff {format_inr(t.staff)}"
        f" · materials {format_inr(t.materials)}"
    )


def rework_section(pairs) -> dict:
    rows = []
    for number, (rework, cost) in enumerate(pairs, start=1):
        finished = rework.finished_at is not None
        sessions = list(rework.sessions.all())
        label, tone = STATUS[rework_state(finished, cost.logged, bool(sessions))]
        photos = list(rework.item.photos.all())
        rows.append(
            {
                "pk": rework.pk,
                "label": f"R{number}",
                "name": rework.item.name,
                "thumb": reverse("item_photo_thumb", args=[photos[0].pk])
                if photos
                else None,
                "reason": rework.get_reason_display(),
                "status_label": label,
                "status_tone": tone,
                "added": format_day(rework.created_at),
                "who": first_name(rework.assignee.name)
                if rework.assignee
                else "Not assigned",
                "minutes": minutes_text(cost.logged, rework.estimate_minutes, finished),
                "materials": materials_text(list(rework.materials.all())),
                "cost": minus_inr(cost.cost),
                "cost_label": "estimated" if cost.estimated else "cost",
                "url": reverse("rework_record", args=[rework.pk]),
            }
        )
    return {
        "rows": rows,
        "total": minus_inr(sum((c.cost for _, c in pairs), Decimal(0))),
        "open": any(r.finished_at is None for r, _ in pairs),
    }
