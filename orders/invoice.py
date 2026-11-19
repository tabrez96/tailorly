"""Invoice maths: item prices plus billed material selling prices, payments, balance."""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

_CENT = Decimal("0.01")


@dataclass(frozen=True)
class Material:
    quantity: Decimal
    selling_price: Decimal  # per unit
    on_bill: bool


@dataclass(frozen=True)
class Item:
    price: Decimal
    materials: tuple[Material, ...] = ()


@dataclass(frozen=True)
class Invoice:
    total: Decimal
    received: Decimal
    balance: Decimal  # total - received; negative when overpaid

    @property
    def paid(self) -> bool:
        return self.balance <= 0


def material_amount(m: Material) -> Decimal:
    """What a material line adds to the bill: quantity x price, or 0 if off the bill."""
    if not m.on_bill:
        return Decimal("0.00")
    return (m.quantity * m.selling_price).quantize(_CENT, ROUND_HALF_UP)


def item_total(item: Item) -> Decimal:
    return item.price + sum(
        (material_amount(m) for m in item.materials), Decimal("0.00")
    )


def build(
    items: Iterable[Item], payments: Iterable[Decimal], *, free: bool = False
) -> Invoice | None:
    """None for a free order: it has no invoice."""
    if free:
        return None
    total = sum((item_total(i) for i in items), Decimal("0.00"))
    received = sum(payments, Decimal("0.00"))
    return Invoice(total=total, received=received, balance=total - received)
