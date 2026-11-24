"""S11 profit by garment and the running costs card. Pure: no ORM."""

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from core.money import format_inr
from reports import costing
from reports.sales import LAST_MONTH, MONTH, Period, range_text

NO_RATE_NOTE = "Gains leave running costs out until you add them."
NOT_SET_TEXT = "Add your monthly running costs to see the full cost of each garment."


@dataclass(frozen=True)
class Piece:
    name: str  # OrderItem.name
    free: bool  # the order is free: nothing was charged
    cost: costing.ItemCost


@dataclass(frozen=True)
class GarmentAverage:  # duck-types ItemCost for costing.bar()
    name: str
    count: int
    price: Decimal  # average price charged, whole rupees
    staff: Decimal
    materials: Decimal
    running: Decimal
    cost: Decimal  # staff + materials + running (the rounded averages)
    gain: Decimal  # average gain, whole rupees
    gain_pct: int | None


def average(name: str, pieces: list[Piece]) -> GarmentAverage:
    n = len(pieces)
    zero = Decimal(0)
    price = sum((zero if p.free else p.cost.price for p in pieces), zero)
    gain = sum((zero if p.free else p.cost.sale) - p.cost.cost for p in pieces)
    staff = costing.rupees(sum((p.cost.staff for p in pieces), zero) / n)
    materials = costing.rupees(sum((p.cost.materials for p in pieces), zero) / n)
    running = costing.rupees(sum((p.cost.running for p in pieces), zero) / n)
    return GarmentAverage(
        name=name,
        count=n,
        price=costing.rupees(price / n),
        staff=staff,
        materials=materials,
        running=running,
        cost=staff + materials + running,
        gain=costing.rupees(gain / n),
        gain_pct=costing.pct(gain, price),
    )


def by_garment(pieces: list[Piece]) -> list[GarmentAverage]:
    groups: dict[str, list[Piece]] = {}
    for p in pieces:
        groups.setdefault(p.name, []).append(p)
    averages = [average(name, group) for name, group in groups.items()]
    return sorted(averages, key=lambda a: (-a.count, a.name))


def rows(averages: list[GarmentAverage]) -> list[dict]:
    return [
        {
            "name": a.name,
            "count": a.count,
            "gain": a.gain,
            "pct": a.gain_pct,
            "loss": a.gain < 0,
            "bar": costing.bar(a),
            "words": f"Average price {format_inr(a.price)}"
            f" · cost {format_inr(a.cost)}: "
            f"staff {format_inr(a.staff)}, materials {format_inr(a.materials)}, "
            f"running {format_inr(a.running)}",
        }
        for a in averages
    ]


def caption(period: Period) -> str:
    when = (
        f"{period.first:%B}"
        if period.key in (MONTH, LAST_MONTH)
        else range_text(period.first, period.last)
    )
    return (
        f"Gain per piece, average of garments sold in {when}. "
        "Tap a garment for its orders."
    )


def rate_card(total: Decimal, hours: int, rate: Decimal | None) -> dict:
    if rate is None:
        return {"set": False, "text": NOT_SET_TEXT}
    days = (
        f" ({hours // costing.HOURS_A_DAY} days × {costing.HOURS_A_DAY}h)"
        if hours % costing.HOURS_A_DAY == 0
        else ""
    )
    return {
        "set": True,
        "title": f"{format_inr(rate)} an hour of work",
        "text": f"{format_inr(total)} a month over {hours} working hours{days}. "
        "Added to each item by its time.",
    }


def bills_average(months: list[Decimal]) -> Decimal | None:
    """Average of the monthly bill totals (months that had bills); None when 0."""
    total = sum(months, Decimal(0))
    if not months or total == 0:
        return None
    return costing.rupees(total / len(months))


def last_three_months(today: date) -> tuple[date, date]:
    """First day of the month 3 back to the last day of last month."""
    index = today.year * 12 + today.month - 1 - 3
    first = date(index // 12, index % 12 + 1, 1)
    end = today.year * 12 + today.month - 2
    year, month = end // 12, end % 12 + 1
    return first, date(year, month, calendar.monthrange(year, month)[1])


def prefill_lines(average: Decimal | None) -> list[dict]:
    if average is None:
        return []
    return [{"name": "Other", "amount": str(average)}]
