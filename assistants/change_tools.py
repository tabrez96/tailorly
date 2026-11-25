"""The MCP change tools. Never delete, never record a payout."""

from datetime import date as Date

from django.db import transaction
from django.utils import timezone

from catalog.models import Product
from customers.measurements import INCHES, format_value, parse_value
from customers.models import Customer
from orders.models import Order, OrderError, OrderItem, Payment
from staff.attendance import parse_decimal

from . import tools
from .tools import ToolFailure

MAX_ITEMS = 20
AMOUNT_INVALID = "Enter an amount above zero, like 500 or 499.50."


def _order(number: int, *, lock: bool = True) -> Order:
    orders = Order.objects.exclude(status=Order.DRAFT).filter(number=number)
    order = (orders.select_for_update() if lock else orders).first()
    if order is None:
        raise ToolFailure(f"No order #{number}.")
    return order


def _day(raw: str, label: str) -> Date:
    try:
        return Date.fromisoformat(raw)
    except TypeError, ValueError:
        raise ToolFailure(f"{label} is a date like 2026-12-01.") from None


def create_order(customer_id: int, products: list[str], due_date: str) -> dict:
    with transaction.atomic():
        customer = Customer.objects.filter(pk=customer_id).first()
        if customer is None:
            raise ToolFailure(f"No customer {customer_id}.")
        names = [n.strip() for n in products if n and n.strip()]
        if not names:
            raise ToolFailure("Name at least one product.")
        if len(names) > MAX_ITEMS:
            raise ToolFailure(f"Up to {MAX_ITEMS} items per order.")
        due = _day(due_date, "due_date")
        if due < timezone.localdate():
            raise ToolFailure("Pick today or a later due date.")
        found = []
        for name in names:
            matches = list(
                Product.objects.filter(
                    kind=Product.PRIMARY, active=True, name__iexact=name
                )[:2]
            )
            if not matches:
                raise ToolFailure(f"No product named {name}.")
            if len(matches) > 1:
                raise ToolFailure(f"More than one product is named {name}.")
            found.append(matches[0])
        order = Order.objects.create(customer=customer, due_date=due)
        for product in found:
            OrderItem.from_product(order, product)
        try:
            order.place()
        except OrderError as e:
            raise ToolFailure(str(e)) from None
        number = order.number
        return tools.get_order(number)


def record_payment(
    number: int, amount: str, method: str = "cash", date: str | None = None
) -> dict:
    with transaction.atomic():
        order = _order(number)
        value = parse_decimal(str(amount).replace(",", ""))
        if (
            value is None
            or value <= 0
            or value.adjusted() >= 10
            or value.as_tuple().exponent < -2
        ):
            raise ToolFailure(AMOUNT_INVALID)
        if method not in dict(Payment.METHODS):
            raise ToolFailure("method is one of: cash, upi, card, bank.")
        today = timezone.localdate()
        day = today if date is None else _day(date, "date")
        if day > today:
            raise ToolFailure("Pick today or an earlier date.")
        try:
            payment = order.record_payment(value, day, method)
        except OrderError as e:
            raise ToolFailure(str(e)) from None
        inv = order.invoice()
    return {
        "number": order.number,
        "payment": {
            "amount": str(payment.amount),
            "date": payment.date.isoformat(),
            "method": payment.method,
        },
        "total": str(inv.total),
        "received": str(inv.received),
        "balance": str(inv.balance),
    }


def update_item_measurements(number: int, item_id: int, values: dict[str, str]) -> dict:
    with transaction.atomic():
        order = _order(number)
        item = order.items.select_for_update().filter(pk=item_id).first()
        if item is None:
            raise ToolFailure(f"No item {item_id} on order #{number}.")
        if item.type != Product.CUSTOM:
            raise ToolFailure("Only custom items have measurements.")
        if not values:
            raise ToolFailure("Give at least one measurement.")
        index = {m["name"].casefold(): i for i, m in enumerate(item.measurements)}
        new = {}
        for name, raw in values.items():
            i = index.get(name.strip().casefold())
            if i is None:
                have = ", ".join(m["name"] for m in item.measurements)
                raise ToolFailure(
                    f"{item.name} has no measurement named {name}. It has: {have}."
                )
            try:
                inches = parse_value(str(raw), INCHES)
            except ValueError as e:
                raise ToolFailure(f"{name}: {e}") from None
            new[i] = "" if inches is None else format_value(inches)
        item.measurements = [
            {**m, "value": new.get(i, m["value"])}
            for i, m in enumerate(item.measurements)
        ]
        item.save(update_fields=["measurements"])
    return {
        "number": order.number,
        "item": {
            "id": item.id,
            "name": item.name,
            "measurements": item.measurements,
        },
    }
