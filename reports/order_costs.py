"""Cost and gain for an order: the ORM glue around reports.costing."""

from collections import defaultdict
from decimal import Decimal

from django.db.models import Prefetch
from django.urls import reverse

from catalog.models import Product
from core.formats import format_duration
from core.money import format_inr
from orders import invoice
from orders.materials import cost_total
from orders.models import OrderItem, Rework
from orders.reworks import rework_detail
from production.models import TimeSession
from production.timing import _logged
from reports import costing
from reports.models import ShopSettings


def _work(sessions, now) -> tuple[costing.Work, ...]:
    groups = defaultdict(list)
    for session in sessions:
        groups[session.employee_id].append(session)
    return tuple(
        costing.Work(
            minutes=_logged(group, now) // 60, daily_wage=group[0].employee.daily_wage
        )
        for group in groups.values()
    )


def item_input(item, assignee_wage, now) -> costing.ItemInput:
    work = _work(item.sessions.all(), now)
    materials = list(item.materials.all())
    costs = [c for c in (cost_total(m) for m in materials) if c is not None]
    return costing.ItemInput(
        price=item.price,
        ready_made=item.type == Product.READY_MADE,
        finished=item.status == OrderItem.FINISHED,
        estimate_minutes=item.estimate_minutes,
        work=work,
        assignee_wage=assignee_wage,
        material_cost=sum(costs, Decimal(0)),
        billed_selling=sum(
            (
                invoice.material_amount(
                    invoice.Material(m.quantity, m.selling_price, True)
                )
                for m in materials
                if m.on_bill
            ),
            Decimal(0),
        ),
        cost_missing=any(m.cost_price is None for m in materials),
    )


def rework_input(rework, now) -> costing.ReworkInput:
    materials = list(rework.materials.all())
    costs = [c for c in (cost_total(m) for m in materials) if c is not None]
    return costing.ReworkInput(
        finished=rework.finished_at is not None,
        estimate_minutes=rework.estimate_minutes,
        work=_work(rework.sessions.all(), now),
        assignee_wage=rework.assignee.daily_wage if rework.assignee else None,
        material_cost=sum(costs, Decimal(0)),
        cost_missing=any(m.cost_price is None for m in materials),
    )


def order_reworks(order):
    """The order's reworks, oldest first, with what the section and costs need."""
    return list(
        Rework.objects.filter(item__order=order)
        .select_related("item", "assignee")
        .prefetch_related(
            "materials",
            "item__photos",
            Prefetch(
                "sessions", queryset=TimeSession.objects.select_related("employee")
            ),
        )
        .order_by("created_at", "pk")
    )


def rework_costs(order, now) -> list[tuple[Rework, costing.ReworkCost]]:
    return [
        (r, costing.rework_cost(rework_input(r, now))) for r in order_reworks(order)
    ]


def _rework_figures(pairs, gain, price) -> dict | None:
    """The Reworks lines of a cost card, None when there are no reworks."""
    if not pairs:
        return None
    total = costing.rework_total([cost for _, cost in pairs])
    after, after_pct = costing.gain_after(gain, price, total)
    return {
        "total": total,
        "detail": rework_detail(total),
        "gain_after": after,
        "pct_after": after_pct,
        "loss_after": after < 0,
    }


def _items(order):
    return list(
        order.items.prefetch_related(
            "materials",
            Prefetch(
                "sessions", queryset=TimeSession.objects.select_related("employee")
            ),
        )
    )


def _load(order, now):
    rate = ShopSettings.current().running_rate()
    wage = order.assignee.daily_wage if order.assignee else None
    items = _items(order)
    costs = costing.order_cost(
        [costing.item_cost(item_input(i, wage, now), rate) for i in items]
    )
    return items, costs, rate


def order_costs(order, now) -> tuple[costing.OrderCost, Decimal | None]:
    """(costs, running cost per hour) for the order's items."""
    _, costs, rate = _load(order, now)
    return costs, rate


def cost_card(order, now, reworks=None) -> dict:
    items, oc, rate = _load(order, now)
    if reworks is None:
        reworks = rework_costs(order, now)
    figures = _rework_figures(reworks, oc.gain, oc.price)
    if figures:
        figures["shop_cost"] = oc.cost + figures["total"].cost
    hours = format_duration(oc.minutes)
    only_rate = next(iter(oc.rates)) if len(oc.rates) == 1 else None
    return {
        "free": order.is_free,
        "items": [
            {
                "number": n,
                "name": item.name,
                "price": c.price,
                "cost": c.cost,
                "gain": c.gain,
                "pct": c.gain_pct,
                "loss": c.gain < 0,
                "estimated": c.estimated,
                "bar": costing.bar(c),
                "words": costing.split_words(c),
            }
            for n, (item, c) in enumerate(zip(items, oc.items, strict=True), start=1)
        ],
        "total": oc,
        "not_charged": oc.sale,
        "staff_detail": f"{hours} × {format_inr(only_rate)}"
        if only_rate is not None and oc.minutes
        else "",
        "running_detail": f"{hours} × {format_inr(rate)}"
        if rate and oc.minutes
        else "",
        "reworks": figures,
        "estimated": oc.estimated,
        "reworks_estimated": bool(figures) and figures["total"].estimated,
        "cost_missing": oc.cost_missing
        or (bool(figures) and figures["total"].cost_missing),
        "rate_missing": rate is None,
        "settings_url": reverse("running_costs"),
    }


def item_cost_card(item, now) -> dict:
    """Cost and gain for one item (S19), from the same figures as the order's card."""
    order = item.order
    items, oc, rate = _load(order, now)
    c = oc.items[[i.pk for i in items].index(item.pk)]
    hours = format_duration(c.minutes)
    only_rate = next(iter(c.rates)) if len(c.rates) == 1 else None
    figures = _rework_figures(
        [pair for pair in rework_costs(order, now) if pair[0].item_id == item.pk],
        c.gain,
        c.price,
    )
    if figures:
        figures["shop_cost"] = c.cost + figures["total"].cost
    return {
        "free": order.is_free,
        "ready_made": item.type == Product.READY_MADE,
        "item": c,
        "billed": c.sale - c.price,  # on-bill material selling, part of the sale
        "loss": c.gain < 0,
        "staff_detail": f"{hours} × {format_inr(only_rate)}"
        if only_rate is not None and c.minutes
        else "",
        "running_detail": f"{hours} × {format_inr(rate)}" if rate and c.minutes else "",
        "reworks": figures,
        "estimated": c.estimated,
        "reworks_estimated": bool(figures) and figures["total"].estimated,
        "cost_missing": c.cost_missing
        or (bool(figures) and figures["total"].cost_missing),
        "rate_missing": rate is None and item.type != Product.READY_MADE,
        "settings_url": reverse("running_costs"),
    }
