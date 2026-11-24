"""S11 profit report: shop profit, free work, reworks and profit rows. Pure: no ORM."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from core.money import format_inr
from reports.costing import ReworkTotal
from reports.sales import LAST_MONTH, MONTH, ZERO, Period, _percent, _plural, range_text


@dataclass(frozen=True)
class OrderFigures:
    order_id: int
    number: int
    customer_id: int
    customer: str
    created: date  # local date the order was placed
    free: bool
    sale: Decimal  # invoice total (the usual billed total on a free order)
    materials: Decimal  # known material cost totals
    staff: Decimal  # costing of logged time plus the estimate left, no running rate
    logged_staff: Decimal  # costing of logged time alone
    running: Decimal  # running costs at the current rate
    shop_cost: Decimal  # the S04 cost card total, with running costs
    estimated: bool

    @property
    def profit(self) -> Decimal:
        return self.sale - self.materials - self.logged_staff  # never running costs


@dataclass(frozen=True)
class ShopProfit:
    sales: Decimal
    materials: Decimal
    staff_pay: Decimal
    bills: Decimal
    profit: Decimal
    unlogged: Decimal  # staff pay not logged to an order, floored at 0


def shop_profit(
    sales: Decimal,
    materials: Decimal,
    staff_pay: Decimal,
    bills: Decimal,
    logged_staff: Decimal,
) -> ShopProfit:
    return ShopProfit(
        sales=sales,
        materials=materials,
        staff_pay=staff_pay,
        bills=bills,
        profit=sales - materials - staff_pay - bills,
        unlogged=max(staff_pay - logged_staff, ZERO),
    )


def note(shop: ShopProfit) -> str:
    text = "Staff pay is split by time logged on each order."
    if shop.unlogged > 0:
        text += (
            f" {format_inr(shop.unlogged)} of pay wasn't logged to an order"
            " and counts with shop costs."
        )
    return text


def none_text(period: Period) -> str:
    if period.key in (MONTH, LAST_MONTH):
        return f"None in {period.first:%B} {period.first.year}"
    return f"None in {range_text(period.first, period.last)}"


def free_work(orders: list[OrderFigures]) -> dict | None:
    free = [o for o in orders if o.free]
    if not free:
        return None
    not_charged = sum((o.sale for o in free), ZERO)
    return {
        "count": len(free),
        "not_charged": not_charged,
        "cost": sum((o.shop_cost for o in free), ZERO),
        "materials": sum((o.materials for o in free), ZERO),
        "staff": sum((o.staff for o in free), ZERO),
        "running": sum((o.running for o in free), ZERO),
        "estimated": any(o.estimated for o in free),
        "text": f"{_plural(len(free), 'order', 'orders')}"
        f" · usual price {format_inr(not_charged)} not charged",
    }


def reworks_line(total: ReworkTotal) -> dict | None:
    if total.count == 0:
        return None
    return {
        "count": total.count,
        "minutes": total.minutes,
        "cost": total.cost,
        "staff": total.staff,
        "materials": total.materials,
        "estimated": total.estimated,
        "text": f"{_plural(total.count, 'rework', 'reworks')} · {total.minutes} min",
    }


def caption(free: dict | None, reworks: dict | None) -> str:
    parts = []
    if free:
        running = (
            f", running costs {format_inr(free['running'])}" if free["running"] else ""
        )
        estimated = " (estimated)" if free["estimated"] else ""
        parts.append(
            f"Free work: materials {format_inr(free['materials'])},"
            f" staff {format_inr(free['staff'])}{running}{estimated}."
        )
    if reworks:
        parts.append(
            f"Reworks: staff {format_inr(reworks['staff'])},"
            f" materials {format_inr(reworks['materials'])}, never invoiced."
        )
    if not parts:
        return ""
    parts.append(
        "Materials are already inside the totals above;"
        " staff pay counts what was actually paid."
    )
    return " ".join(parts)


def _ranked(rows: list[dict], order) -> list[dict]:
    rows = sorted(rows, key=order)
    top = rows[0]["profit"] if rows else ZERO
    return [r | {"percent": max(0, min(100, _percent(r["profit"], top)))} for r in rows]


def by_customer(orders: list[OrderFigures]) -> list[dict]:
    groups: dict[int, dict] = {}
    for o in orders:
        if o.free:
            continue
        row = groups.setdefault(
            o.customer_id,
            {
                "customer_id": o.customer_id,
                "name": o.customer,
                "profit": ZERO,
                "sales": ZERO,
                "orders": 0,
            },
        )
        row["profit"] += o.profit
        row["sales"] += o.sale
        row["orders"] += 1
    rows = [
        r
        | {
            "sub": f"{_plural(r['orders'], 'order', 'orders')}"
            f" · sales {format_inr(r['sales'])}"
        }
        for r in groups.values()
    ]
    return _ranked(rows, lambda r: (-r["profit"], r["name"]))


def by_sale(orders: list[OrderFigures]) -> list[dict]:
    numbers = {o.order_id: o.number for o in orders}
    rows = [
        {
            "order_id": o.order_id,
            "name": f"#{o.number} {o.customer}",
            "profit": o.profit,
            "sales": o.sale,
            "sub": f"sales {format_inr(o.sale)} · {o.created.day} {o.created:%b}",
        }
        for o in orders
        if not o.free
    ]
    return _ranked(rows, lambda r: (-r["profit"], -numbers[r["order_id"]]))
