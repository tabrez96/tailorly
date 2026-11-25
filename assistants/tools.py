"""The MCP read tools. Plain sync functions returning dicts; scopes that are off
leave their fields out of the result entirely."""

from datetime import date

from django.db.models import Count, F, Q
from mcp.server.mcpserver.exceptions import ToolError

from catalog.models import Product
from customers.models import Customer
from orders.models import Order
from reports.models import ShopSettings

from .scopes import Access

OPEN_STATUSES = [Order.OPEN, Order.IN_PROGRESS, Order.READY]
LIST_STATUSES = [Order.OPEN, Order.IN_PROGRESS, Order.READY, Order.DELIVERED]


class ToolFailure(ToolError):
    """Bad input or not found; the message is shown to the assistant."""


def _access() -> Access:
    return Access.of(ShopSettings.current())


def _clamp(n: int, low: int, high: int) -> int:
    return max(low, min(high, n))


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def find_customers(query: str, limit: int = 10) -> list[dict]:
    query = (query or "").strip()
    if not query:
        raise ToolFailure("Enter a name or phone number.")
    digits = query.replace(" ", "")
    match = Q(phone__contains=digits) if digits.isdigit() else Q(name__icontains=query)
    customers = (
        Customer.objects.filter(match)
        .annotate(
            open_orders=Count("orders", filter=Q(orders__status__in=OPEN_STATUSES))
        )
        .order_by("name")[: _clamp(limit, 1, 25)]
    )
    return [
        {"id": c.id, "name": c.name, "phone": c.phone, "open_orders": c.open_orders}
        for c in customers
    ]


def get_order(number: int) -> dict:
    order = (
        Order.objects.exclude(status=Order.DRAFT)
        .select_related("customer", "assignee")
        .prefetch_related("items")
        .filter(number=number)
        .first()
    )
    if order is None:
        raise ToolFailure(f"No order #{number}.")
    return _order(order, _access(), detail=True)


def list_orders(
    status: str | None = None, due_by: str | None = None, limit: int = 50
) -> list[dict]:
    orders = Order.objects.exclude(status=Order.DRAFT)
    if status is not None:
        if status not in LIST_STATUSES:
            raise ToolFailure("Status is one of: open, in_progress, ready, delivered.")
        orders = orders.filter(status=status)
    if due_by is not None:
        try:
            orders = orders.filter(due_date__lte=date.fromisoformat(due_by))
        except ValueError:
            raise ToolFailure("due_by is a date like 2026-12-01.") from None
    orders = (
        orders.select_related("customer")
        .prefetch_related("items")
        .order_by(F("due_date").asc(nulls_last=True), "number")[: _clamp(limit, 1, 100)]
    )
    access = _access()
    return [_order(o, access, detail=False) for o in orders]


def get_measurements(customer_id: int) -> dict:
    customer = Customer.objects.filter(pk=customer_id).first()
    if customer is None:
        raise ToolFailure(f"No customer {customer_id}.")
    sets = customer.measurement_sets.select_related("product").order_by("product__name")
    return {
        "customer": {"id": customer.id, "name": customer.name},
        "garments": [
            {
                "garment": ms.product.name,
                "values": ms.values,
                "updated_at": _iso(ms.updated_at),
            }
            for ms in sets
        ],
    }


def _order(order: Order, access: Access, *, detail: bool) -> dict:
    """The one place order fields are filtered by scope."""
    money = "money" in access.scopes
    customer = {"id": order.customer_id, "name": order.customer.name}
    out = {
        "number": order.number,
        "status": order.status,
        "due_date": _iso(order.due_date),
        "customer": customer,
    }
    if money:
        out["paid_by"] = order.paid_by
        invoice = order.invoice()
        if invoice is not None:
            out["total"] = str(invoice.total)
            out["received"] = str(invoice.received)
            out["balance"] = str(invoice.balance)
    if not detail:
        out["item_count"] = len(order.items.all())
        return out
    customer["phone"] = order.customer.phone
    out["assignee"] = order.assignee.name if order.assignee else None
    out["delivered_at"] = _iso(order.delivered_at)
    items = []
    for item in order.items.all():
        row = {
            "name": item.name,
            "type": item.type,
            "status": item.status,
            "options": item.options,
            "notes": item.notes,
        }
        if money:
            row["price"] = str(item.price)
        if "measurements" in access.scopes and item.type == Product.CUSTOM:
            row["measurements"] = item.measurements
        items.append(row)
    out["items"] = items
    return out
