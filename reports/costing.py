"""Cost and gain per item and order (S04, later S11 and S19). Pure: no ORM."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from core.money import format_inr

DEFAULT_HOURS = 208  # 26 days x 8 hours
HOURS_A_DAY = 8
ZERO = Decimal(0)


def rupees(amount: Decimal) -> Decimal:
    """Round to the whole rupee, half up."""
    return Decimal(amount).quantize(Decimal(1), rounding=ROUND_HALF_UP)


def hourly_rate(daily_wage: Decimal) -> Decimal:
    return Decimal(daily_wage) / HOURS_A_DAY  # not rounded; amounts are


def monthly_total(lines: list[dict]) -> Decimal:
    """Sum of [{"name": ..., "amount": "7000"}, ...]."""
    return sum((Decimal(line["amount"]) for line in lines), ZERO)


def running_rate(total: Decimal, hours: int) -> Decimal | None:
    """Running cost per hour, rounded to the rupee; None when not set."""
    if total <= 0 or hours <= 0:
        return None
    return rupees(total / hours)


def pct(part: Decimal, whole: Decimal) -> int | None:
    if whole <= 0:
        return None
    return int(rupees(part * 100 / whole))


@dataclass(frozen=True)
class Work:
    """One employee's logged minutes on an item."""

    minutes: int
    daily_wage: Decimal


@dataclass(frozen=True)
class ItemInput:
    price: Decimal
    ready_made: bool
    finished: bool
    estimate_minutes: int | None
    work: tuple[Work, ...]  # per employee, from that employee's sessions
    assignee_wage: Decimal | None  # daily wage of the order's assignee
    material_cost: Decimal  # sum of known material cost totals
    billed_selling: Decimal  # sum of selling totals of on-bill materials
    cost_missing: bool = False  # some material has no cost price yet


@dataclass(frozen=True)
class ItemCost:
    price: Decimal
    minutes: int
    staff: Decimal
    materials: Decimal
    running: Decimal
    cost: Decimal
    sale: Decimal  # price + billed material selling
    gain: Decimal
    gain_pct: int | None  # gain / price, None when price is 0
    estimated: bool
    cost_missing: bool
    rates: frozenset  # hourly rates used for staff time


@dataclass(frozen=True)
class OrderCost:
    items: tuple[ItemCost, ...]
    price: Decimal
    sale: Decimal
    minutes: int
    staff: Decimal
    materials: Decimal
    running: Decimal
    cost: Decimal
    gain: Decimal
    gain_pct: int | None
    estimated: bool
    cost_missing: bool
    rates: frozenset


def item_cost(item: ItemInput, rate: Decimal | None) -> ItemCost:
    materials = rupees(item.material_cost)
    sale = item.price + item.billed_selling
    if item.ready_made:
        minutes, staff, running, estimated, rates = 0, ZERO, ZERO, False, frozenset()
    else:
        logged = sum(w.minutes for w in item.work)
        staff_raw = sum(
            (w.minutes * hourly_rate(w.daily_wage) / 60 for w in item.work), ZERO
        )
        rates = {hourly_rate(w.daily_wage) for w in item.work if w.minutes}
        minutes = logged
        estimate = item.estimate_minutes
        if not item.finished and estimate and estimate > logged:
            minutes = estimate
            if item.assignee_wage is not None:
                extra_rate = hourly_rate(item.assignee_wage)
                staff_raw += (estimate - logged) * extra_rate / 60
                rates.add(extra_rate)
        estimated = not item.finished
        staff = rupees(staff_raw)
        running = rupees(minutes * rate / 60) if rate else ZERO
        rates = frozenset(rates)
    cost = staff + materials + running
    gain = sale - cost
    return ItemCost(
        price=item.price,
        minutes=minutes,
        staff=staff,
        materials=materials,
        running=running,
        cost=cost,
        sale=sale,
        gain=gain,
        gain_pct=pct(gain, item.price),
        estimated=estimated,
        cost_missing=item.cost_missing,
        rates=rates,
    )


def order_cost(items: list[ItemCost]) -> OrderCost:
    """Sums of the rounded item figures, so the totals add up on screen."""
    price = sum((i.price for i in items), ZERO)
    gain = sum((i.gain for i in items), ZERO)
    return OrderCost(
        items=tuple(items),
        price=price,
        sale=sum((i.sale for i in items), ZERO),
        minutes=sum(i.minutes for i in items),
        staff=sum((i.staff for i in items), ZERO),
        materials=sum((i.materials for i in items), ZERO),
        running=sum((i.running for i in items), ZERO),
        cost=sum((i.cost for i in items), ZERO),
        gain=gain,
        gain_pct=pct(gain, price),
        estimated=any(i.estimated for i in items),
        cost_missing=any(i.cost_missing for i in items),
        rates=frozenset().union(*(i.rates for i in items)),
    )


SEGMENTS = (
    ("staff", "Staff"),
    ("materials", "Materials"),
    ("running", "Running costs"),
    ("gain", "Gain"),
)


def _amount(c: ItemCost | OrderCost, key: str) -> Decimal:
    value = getattr(c, key)
    return max(value, ZERO) if key == "gain" else value


def bar(c: ItemCost | OrderCost) -> list[dict]:
    """Stacked bar segments (staff, materials, running costs, gain)."""
    total = sum((_amount(c, key) for key, _ in SEGMENTS), ZERO)
    return [
        {
            "key": key,
            "label": label,
            "amount": _amount(c, key),
            "pct": round(float(_amount(c, key) * 100 / total), 1) if total else 0,
        }
        for key, label in SEGMENTS
    ]


def split_words(c: ItemCost | OrderCost) -> str:
    return " · ".join(
        f"{label} {format_inr(getattr(c, key))}" for key, label in SEGMENTS
    )
