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
from orders.models import OrderItem
from production.models import TimeSession
from production.timing import _logged
from reports import costing
from reports.models import ShopSettings


def item_input(item, assignee_wage, now) -> costing.ItemInput:
    groups = defaultdict(list)
    for session in item.sessions.all():
        groups[session.employee_id].append(session)
    work = tuple(
        costing.Work(
            minutes=_logged(group, now) // 60, daily_wage=group[0].employee.daily_wage
        )
        for group in groups.values()
    )
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


def cost_card(order, now) -> dict:
    items, oc, rate = _load(order, now)
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
        "estimated": oc.estimated,
        "cost_missing": oc.cost_missing,
        "rate_missing": rate is None,
        "settings_url": reverse("running_costs"),
    }
