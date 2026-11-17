"""Rupee formatting. Amounts are in rupees (INR) and there is no tax."""

from decimal import ROUND_HALF_UP, Decimal


def group_indian(digits: str) -> str:
    """Group digits the Indian way: last 3, then pairs (1234567 -> 12,34,567)."""
    head, tail = digits[:-3], digits[-3:]
    groups = []
    while head:
        groups.append(head[-2:])
        head = head[:-2]
    return ",".join([*reversed(groups), tail])


def format_inr(amount: Decimal | int | float | str | None) -> str:
    """Show an amount as whole rupees with Indian grouping, e.g. ₹1,42,600."""
    if amount is None or amount == "":
        return ""
    rounded = Decimal(str(amount)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    sign = "-" if rounded < 0 else ""
    return f"{sign}₹{group_indian(str(abs(rounded)))}"
