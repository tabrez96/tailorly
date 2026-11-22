"""The S16 Work plan page: queues, the next suggestion and waiting orders."""

from django.urls import reverse
from django.utils import timezone

from catalog.models import Product
from core.formats import format_day, format_duration
from production.assign import waiting_orders
from production.queue import (
    due_soon,
    due_text,
    fit_text,
    late_keys,
    reason,
    time_text,
)
from production.timing import _thumb, queue_rows
from staff.attendance import first_name
from staff.models import Employee


def _decorate(rows, today) -> tuple[list[dict], int]:
    late = late_keys(rows, today)
    out = []
    for rank, row in enumerate(rows, start=1):
        started = row["started"]
        out.append(
            {
                **row,
                "rank": rank,
                "garment": row["item"].name,
                "photo": row["thumb"],
                "order_label": f"#{row['order'].number}",
                "order_url": reverse("order", args=[row["order"].pk]),
                "due_label": due_text(row["due"], today),
                "due_soon": due_soon(row["due"], today),
                "time_needed": time_text(row),
                "status": "In progress" if started else "Not started",
                "tone": "pri" if started else "warn",
                "moved": bool(row["moved_to"]),
                "late": row["key"] in late,
            }
        )
    return out, len(late)


def _section(employee, now, today) -> dict:
    rows, late = _decorate(queue_rows(employee, now), today)
    need = sum(r["need"] for r in rows)
    return {
        "employee": employee,
        "first": first_name(employee.name),
        "rows": rows,
        "count": len(rows),
        "hours": f"about {format_duration(need)} of work",
        "late": late,
    }


def _hero(sections, today) -> dict | None:
    for section in sections:
        row = next((r for r in section["rows"] if not r["started"]), None)
        if row is not None:
            return {
                "first": section["first"],
                "row": row,
                "reason": reason(row, today),
                "fit": fit_text(section["count"], section["late"]),
            }
    return None


def _unassigned() -> list[dict]:
    orders = waiting_orders()
    rows = []
    for order in orders:
        items = [i for i in order.items.all() if i.type == Product.CUSTOM]
        first = items[0]
        thumb, count = _thumb(first)
        extra = f" and {len(items) - 1} more" if len(items) > 1 else ""
        rows.append(
            {
                "garment": f"{first.name}{extra}",
                "thumb": thumb,
                "photo_count": count,
                "number": f"#{order.number}",
                "customer": order.customer,
                "due": f"due {format_day(order.due_date)}"
                if order.due_date
                else "no due date",
                "free": order.is_free,
                "pk": order.pk,
                "assign_url": reverse("assign_sheet", args=[order.pk]),
            }
        )
    return rows


def plan_context(now) -> dict:
    today = timezone.localdate(now)
    employees = Employee.objects.filter(active=True).order_by("name", "id")
    sections = [_section(e, now, today) for e in employees]
    unassigned = _unassigned()
    first = waiting_orders().first()
    return {
        "assign_next_url": reverse("assign_sheet", args=[first.pk]) if first else "",
        "hero": _hero(sections, today),
        "unassigned": unassigned,
        "sections": sections,
        "empty": not unassigned and not any(s["rows"] for s in sections),
    }
