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
class ReworkInput:
    finished: bool
    estimate_minutes: int
    work: tuple[Work, ...]  # per employee, from the rework's sessions
    assignee_wage: Decimal | None  # daily wage of the rework's assignee
    material_cost: Decimal  # sum of known material cost totals
    cost_missing: bool = False


@dataclass(frozen=True)
class ReworkCost:
    logged: int  # minutes actually logged
    minutes: int  # minutes counted (the estimate while open, if more)
    staff: Decimal
    materials: Decimal
    cost: Decimal  # staff + materials; never a running-cost share
    estimated: bool  # not finished
    cost_missing: bool


@dataclass(frozen=True)
class ReworkTotal:
    count: int
    logged: int
    minutes: int
    staff: Decimal
    materials: Decimal
    cost: Decimal
    estimated: bool
    cost_missing: bool


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


def _timed_staff(
    work, finished: bool, estimate: int | None, assignee_wage: Decimal | None
) -> tuple[int, int, Decimal, frozenset]:
    """(logged, minutes counted, staff cost unrounded, hourly rates used)."""
    logged = sum(w.minutes for w in work)
    staff_raw = sum((w.minutes * hourly_rate(w.daily_wage) / 60 for w in work), ZERO)
    rates = {hourly_rate(w.daily_wage) for w in work if w.minutes}
    minutes = logged
    if not finished and estimate and estimate > logged:
        minutes = estimate
        if assignee_wage is not None:
            extra_rate = hourly_rate(assignee_wage)
            staff_raw += (estimate - logged) * extra_rate / 60
            rates.add(extra_rate)
    return logged, minutes, staff_raw, frozenset(rates)


def item_cost(item: ItemInput, rate: Decimal | None) -> ItemCost:
    materials = rupees(item.material_cost)
    sale = item.price + item.billed_selling
    if item.ready_made:
        minutes, staff, running, estimated, rates = 0, ZERO, ZERO, False, frozenset()
    else:
        logged, minutes, staff_raw, rates = _timed_staff(
            item.work, item.finished, item.estimate_minutes, item.assignee_wage
        )
        estimated = not item.finished
        staff = rupees(staff_raw)
        running = rupees(minutes * rate / 60) if rate else ZERO
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


def rework_cost(r: ReworkInput) -> ReworkCost:
    logged, minutes, staff_raw, _ = _timed_staff(
        r.work, r.finished, r.estimate_minutes, r.assignee_wage
    )
    staff = rupees(staff_raw)
    materials = rupees(r.material_cost)
    return ReworkCost(
        logged=logged,
        minutes=minutes,
        staff=staff,
        materials=materials,
        cost=staff + materials,
        estimated=not r.finished,
        cost_missing=r.cost_missing,
    )


def rework_total(costs: list[ReworkCost]) -> ReworkTotal:
    """Sums of the rounded rework figures."""
    return ReworkTotal(
        count=len(costs),
        logged=sum(c.logged for c in costs),
        minutes=sum(c.minutes for c in costs),
        staff=sum((c.staff for c in costs), ZERO),
        materials=sum((c.materials for c in costs), ZERO),
        cost=sum((c.cost for c in costs), ZERO),
        estimated=any(c.estimated for c in costs),
        cost_missing=any(c.cost_missing for c in costs),
    )


def gain_after(
    gain: Decimal, price: Decimal, reworks: ReworkTotal
) -> tuple[Decimal, int | None]:
    after = gain - reworks.cost
    return after, pct(after, price)


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
