"""Pure helpers for adding an item to an order."""

from decimal import Decimal

from django.db.models import QuerySet
from django.db.models.functions import Lower

from catalog.models import Product, ProductOption
from core.money import format_inr
from orders.models import OrderItem

TYPE_WORDS = {Product.CUSTOM: "custom", Product.READY_MADE: "ready-made"}


def products_for(type_: str) -> QuerySet[Product]:
    return Product.objects.filter(
        kind=Product.PRIMARY, type=type_, active=True
    ).order_by(Lower("name"), "pk")


def resolve_type(raw: str | None) -> str:
    return raw if raw in dict(Product.TYPES) else Product.CUSTOM


def price_input(value: Decimal) -> str:
    """Price for a text input: 1800.00 -> '1800', 1800.50 -> '1800.5'."""
    return f"{value.quantize(Decimal('0.01')).normalize():f}"


def price_message(product: Product | None) -> str:
    if product is None:
        return "Enter a price."
    return (
        f"Enter a price. The usual price for a {product.name} "
        f"is {format_inr(product.usual_price)}."
    )


def price_hint(product: Product) -> str:
    return (
        f"Usual price {format_inr(product.usual_price)}. Change it for this order only."
    )


def material_hint(option: ProductOption) -> str:
    if option.material is None:
        return ""
    hint = f"Uses {option.material.name}."
    if option.asks_quantity:
        when = (
            "at order" if option.asked_when == ProductOption.AT_ORDER else "when done"
        )
        hint += f" Quantity is asked {when}."
    return hint


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def product_summary(product: Product) -> str:
    if product.type == Product.READY_MADE:
        return f"Ready-made · usual {format_inr(product.usual_price)}"
    parts = ["Custom"]
    options = product.options.count()
    if options:
        parts.append(_count(options, "option"))
    fields = len(product.measurement_fields)
    if fields:
        parts.append(_count(fields, "measurement"))
    return " · ".join(parts)


def item_summary(item: OrderItem) -> str:
    if item.type == Product.READY_MADE:
        return "no measurements"
    parts = []
    for o in item.options:
        if o["answer"] == "Yes":
            parts.append(o["name"])
        elif o["answer"] != "No":
            parts.append(o["answer"])
    filled = sum(1 for m in item.measurements if str(m.get("value", "")).strip())
    parts.append(_count(filled, "measurement") if filled else "no measurements")
    if item.notes.strip():
        parts.append("1 note")
    return " · ".join(parts)
