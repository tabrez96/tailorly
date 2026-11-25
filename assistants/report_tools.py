"""The MCP money and staff read tools. Same figures as the reports; scopes that
are off leave their fields out."""

from datetime import date, timedelta

from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from orders.models import Order, Payment
from reports import order_costs, payments, staff_report
from staff import pay
from staff.attendance import week_start
from staff.models import DayRecord, Employee, Payout

from .tools import ToolFailure, _access, _iso

MAX_PAYMENT_DAYS = 366
MAX_PAYMENT_ROWS = 200


def _date(raw: str, name: str) -> date:
    try:
        return date.fromisoformat(raw)
    except TypeError, ValueError:
        raise ToolFailure(f"{name} is a date like 2026-12-01.") from None


def money_to_collect() -> dict:
    owing = payments.load_owing()
    c = payments.collect(owing)
    out = {
        "total": str(c["total"]),
        "not_delivered": str(c["not_delivered"]),
        "delivered": str(c["delivered"]),
        "orders": c["orders"],
    }
    if "orders" in _access().scopes:
        ranked = sorted(
            owing,
            key=lambda o: (
                o.status != Order.DELIVERED,
                o.delivered or date.min,
                o.number,
            ),
        )
        out["owing"] = [
            {
                "number": o.number,
                "customer": o.customer,
                "status": o.status,
                "balance": str(o.balance),
                "delivered": _iso(o.delivered),
            }
            for o in ranked
        ]
    return out


def list_payments(start: str, end: str) -> dict:
    first, last = _date(start, "start"), _date(end, "end")
    if last < first:
        raise ToolFailure("end is before start.")
    if (last - first).days >= MAX_PAYMENT_DAYS:
        raise ToolFailure("Ask for at most 366 days at a time.")
    rows = list(
        payments.payments_in(first, last)
        .select_related("order__customer")
        .order_by("-date", "-pk")
    )
    pairs = [(p.method, p.amount) for p in rows]
    orders_on = "orders" in _access().scopes
    labels = dict(Payment.METHODS)
    listed = []
    for p in rows[:MAX_PAYMENT_ROWS]:
        row = {
            "date": p.date.isoformat(),
            "method": labels[p.method],
            "amount": str(p.amount),
        }
        if orders_on:
            row["order"] = p.order.number
            row["customer"] = p.order.customer.name
        listed.append(row)
    return {
        "start": first.isoformat(),
        "end": last.isoformat(),
        "received": str(sum((a for _, a in pairs), payments.ZERO)),
        "count": len(rows),
        "by_method": [
            {"method": m["label"], "count": m["count"], "total": str(m["total"])}
            for m in payments.by_method(pairs)
        ],
        "payments": listed,
        "more": len(rows) > MAX_PAYMENT_ROWS,
    }


def order_cost_and_gain(number: int) -> dict:
    order = (
        Order.objects.exclude(status=Order.DRAFT)
        .select_related("customer", "assignee")
        .filter(number=number)
        .first()
    )
    if order is None:
        raise ToolFailure(f"No order #{number}.")
    card = order_costs.cost_card(order, timezone.now())
    staff_on = "staff" in _access().scopes
    oc = card["total"]
    items = []
    for row, ic in zip(card["items"], oc.items, strict=True):
        item = {
            "name": row["name"],
            "price": str(row["price"]),
            "materials": str(ic.materials),
            "running": str(ic.running),
            "cost": str(row["cost"]),
            "gain": str(row["gain"]),
            "gain_pct": row["pct"],
            "estimated": row["estimated"],
        }
        if staff_on:
            item["staff"] = str(ic.staff)
        items.append(item)
    out = {
        "number": order.number,
        "customer": order.customer.name,
        "free": card["free"],
        "price": str(oc.price),
        "sale": str(oc.sale),
        "materials": str(oc.materials),
        "running": str(oc.running),
        "cost": str(oc.cost),
        "gain": str(oc.gain),
        "gain_pct": oc.gain_pct,
        "estimated": card["estimated"],
        "cost_missing": card["cost_missing"],
        "rate_missing": card["rate_missing"],
        "items": items,
        "reworks": None,
    }
    if staff_on:
        out["staff"] = str(oc.staff)
        out["staff_time_minutes"] = oc.minutes
        out["staff_detail"] = card["staff_detail"]
    if card["reworks"] is not None:
        f = card["reworks"]
        t = f["total"]
        out["reworks"] = {
            "count": t.count,
            "cost": str(t.cost),
            "materials": str(t.materials),
            "gain_after": str(f["gain_after"]),
            "gain_pct_after": f["pct_after"],
            "shop_cost": str(f["shop_cost"]),
        }
        if staff_on:
            out["reworks"]["staff"] = str(t.staff)
    return out


def staff_week(week: str | None = None) -> dict:
    today = timezone.localdate()
    monday = week_start(_date(week, "week") if week else today)
    sunday = monday + timedelta(days=6)
    employees = Employee.objects.filter(
        Q(active=True)
        | Exists(
            DayRecord.objects.filter(
                employee=OuterRef("pk"), date__range=(monday, sunday)
            )
        )
        | Exists(Payout.objects.filter(employee=OuterRef("pk"), week_start=monday))
    ).order_by("name")
    paid = {p.employee_id: p for p in Payout.objects.filter(week_start=monday)}
    methods = dict(Payout.METHODS)
    rows, earned = [], payments.ZERO
    for e in employees:
        w = pay.week_pay(
            monday,
            staff_report._records(e, monday, sunday),
            e.daily_wage,
            e.overtime_multiplier,
            today,
        )
        earned += w.total
        p = paid.get(e.pk)
        rows.append(
            {
                "name": e.name,
                "daily_wage": str(e.daily_wage),
                "days_worked": w.days_paid,
                "overtime_minutes": w.overtime_minutes,
                "day_pay": str(w.base_total),
                "overtime_pay": str(w.overtime_total),
                "earned": str(w.total),
                "days": [
                    {
                        "date": d.date.isoformat(),
                        "worked_minutes": d.worked_minutes,
                        "overtime_minutes": d.overtime_minutes,
                        "pay": str(d.total),
                        "running": d.running,
                    }
                    for d in w.days
                    if d.paid
                ],
                "payout": None
                if p is None
                else {
                    "paid_on": p.paid_on.isoformat(),
                    "method": methods[p.method],
                    "amount": str(p.amount),
                },
            }
        )
    return {
        "week_start": monday.isoformat(),
        "week_end": sunday.isoformat(),
        "pay_day": pay.pay_day(monday).isoformat(),
        "employees": rows,
        "earned": str(earned),
        "paid_out": str(sum((p.amount for p in paid.values()), payments.ZERO)),
    }
