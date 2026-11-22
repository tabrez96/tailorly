"""The S16 assign sheet: who makes an order, its estimates and its queue place."""

from datetime import date, timedelta

from django.db import transaction
from django.db.models import F
from django.urls import reverse
from django.utils import timezone

from catalog.models import Product
from core.formats import format_day, format_duration
from orders.making import ordinal, parse_duration
from orders.models import Order, OrderItem
from production.estimates import usual
from production.queue import DAY_MINUTES, ordered, suggested, suggested_key
from production.timing import _row, open_session, queue_rows, stop
from staff.attendance import first_name, initials
from staff.models import Employee

SUGGESTED = "suggested"
NEXT = "next"
BLANK_ESTIMATE = "Enter how long it takes, like 2h 30m."


class AssignError(Exception):
    """The order can't be assigned any more."""


def waiting_orders():
    """Open orders with a custom item and no one assigned, earliest due first."""
    return (
        Order.objects.filter(
            assignee__isnull=True,
            status__in=[Order.OPEN, Order.IN_PROGRESS],
            items__type=Product.CUSTOM,
            items__status__in=[OrderItem.NOT_STARTED, OrderItem.IN_PROGRESS],
        )
        .distinct()
        .select_related("customer")
        .prefetch_related("items__photos")
        .order_by(F("due_date").asc(nulls_last=True), "number")
    )


def assignable(order) -> bool:
    return (
        order.status in (Order.OPEN, Order.IN_PROGRESS)
        and order.items.filter(type=Product.CUSTOM)
        .exclude(status=OrderItem.FINISHED)
        .exists()
    )


def next_up_rank(queue: list[dict]) -> int:
    """1-based place right after the last started row; 1 when nothing is started."""
    return max((i for i, r in enumerate(queue, 1) if r["started"]), default=0) + 1


def place_rows(queue: list[dict], new: list[dict], place: str) -> list[dict]:
    """The ordered queue once the order's `new` rows join `queue` (without them)."""
    if place == NEXT:
        at = next_up_rank(queue)
        shifted = [
            {**r, "moved_to": r["moved_to"] + len(new)}
            if r["moved_to"] and r["moved_to"] >= at
            else r
            for r in queue
        ]
        placed = [
            {**r, "moved_to": at + i}
            for i, r in enumerate(sorted(new, key=suggested_key))
        ]
        return ordered(shifted + placed)
    return ordered(queue + [{**r, "moved_to": None} for r in new])


def suggestion(queue, new, today) -> dict:
    """Where Suggested would put the order's rows, and when they would be ready."""
    rows = place_rows(queue, new, SUGGESTED)
    keys = {r["key"] for r in new}
    at = [i for i, r in enumerate(rows) if r["key"] in keys]
    first, last = at[0], at[-1]
    total = sum(r["need"] for r in rows[: last + 1])
    ready = today + timedelta(days=max(total - 1, 0) // DAY_MINUTES)
    return {
        "position": first + 1,
        "before": rows[first - 1] if first else None,
        "ready": ready,
    }


def suggested_lines(position: int, before: str | None, ready: date) -> tuple[str, str]:
    when = f"ready by {format_day(ready)}"
    second = (
        f"After the {before.lower()}, {when}"
        if before
        else f"First in the queue, {when}"
    )
    return f"Suggested: {ordinal(position)}", second


def usual_hint(name: str, minutes: int, samples: int) -> str:
    tail = "Used for the queue and in Production."
    garment = name.lower()
    if samples >= 3:
        article = "an" if garment[:1] in "aeiou" else "a"
        return (
            f"Usually {format_duration(minutes)} for {article} {garment} "
            f"(last {samples}). {tail}"
        )
    return (
        f"No finished {garment} to go by yet, so it starts at "
        f"{format_duration(minutes)}. {tail}"
    )


def read_estimates(items, data) -> tuple[dict[int, int], dict[int, str]]:
    """Parse `estimate_<pk>` for each not-started item; started items are never read."""
    estimates, errors = {}, {}
    for item in items:
        if item.status != OrderItem.NOT_STARTED:
            continue
        try:
            minutes = parse_duration(data.get(f"estimate_{item.pk}", ""))
        except ValueError as error:
            errors[item.pk] = str(error)
            continue
        if minutes is None:
            errors[item.pk] = BLANK_ESTIMATE
        else:
            estimates[item.pk] = minutes
    return estimates, errors


def _items(order):
    return (
        order.items.filter(type=Product.CUSTOM)
        .exclude(status=OrderItem.FINISHED)
        .select_related("order__customer", "product")
        .prefetch_related("photos", "sessions")
        .order_by("position", "id")
    )


def _queue_without(employee, order, now) -> list[dict]:
    return [
        r
        for r in queue_rows(employee, now)
        if not (r["rework"] is None and r["order"].pk == order.pk)
    ]


def _new_rows(items, estimates, now) -> list[dict]:
    rows = []
    for item in items:
        row = _row(item, now)
        if item.status == OrderItem.NOT_STARTED and item.pk in estimates:
            row["estimate"] = estimates[item.pk]
            row["need"] = max(estimates[item.pk] - row["minutes"], 0)
        rows.append(row)
    return rows


def _chosen_maker(order, data, employees):
    by_pk = {str(e.pk): e for e in employees}
    chosen = by_pk.get(data.get("employee", ""))
    if chosen is None and order.assignee_id:
        chosen = by_pk.get(str(order.assignee_id))
    return chosen or (employees[0] if employees else None)


def sheet_context(order, data, now, *, back: str, errors=None, error="") -> dict:
    """Everything the sheet shows; `data` is request.GET or request.POST."""
    errors = errors or {}
    employees = list(Employee.objects.filter(active=True).order_by("name", "id"))
    maker = _chosen_maker(order, data, employees)
    items = list(_items(order))
    first = items[0] if items else None
    place = data.get("place")
    if place not in (SUGGESTED, NEXT):
        had_move = any(i.queue_rank for i in items)
        place = (
            NEXT
            if maker is not None and maker.pk == order.assignee_id and had_move
            else SUGGESTED
        )

    posted, _ = read_estimates(items, data)
    estimates, fields = {}, []
    for item in items:
        minutes, samples = usual(item.product)
        stored = item.estimate_minutes or minutes
        fixed = item.status != OrderItem.NOT_STARTED
        fixed_text = f"{format_duration(item.estimate_minutes or stored)}"
        estimates[item.pk] = stored if fixed else posted.get(item.pk, stored)
        key = f"estimate_{item.pk}"
        fields.append(
            {
                "pk": item.pk,
                "name": item.name,
                "label": item.name if len(items) > 1 else "",
                "value": data[key] if key in data else format_duration(stored),
                "hint": usual_hint(item.name, minutes, samples),
                "fixed": fixed,
                "fixed_text": f"{fixed_text} · fixed once started",
                "error": errors.get(item.pk, ""),
            }
        )

    makers = []
    for e in employees:
        rows = _queue_without(e, order, now)
        need = sum(r["need"] for r in rows)
        makers.append(
            {
                "pk": e.pk,
                "name": e.name,
                "initials": initials(e.name),
                "line": f"{len(rows)} in queue · about {format_duration(need)} of work"
                if rows
                else "Nothing in the queue yet",
                "checked": e == maker,
            }
        )

    ctx = {
        "order": order,
        "title": (
            f"Assign {first.name}"
            + (f" and {len(items) - 1} more" if len(items) > 1 else "")
            if first
            else f"Assign #{order.number}"
        ),
        "sub": f"#{order.number} · {order.customer.name} · "
        + (f"due {format_day(order.due_date)}" if order.due_date else "no due date"),
        "makers": makers,
        "estimates": fields,
        "place": place,
        "sheet_url": reverse("assign_sheet", args=[order.pk]),
        "back": back,
        "no_employees": maker is None,
        "no_items": not items,
        "error": error,
    }
    if maker is not None and items:
        queue = _queue_without(maker, order, now)
        new = _new_rows(items, estimates, now)
        found = suggestion(queue, new, timezone.localdate(now))
        before = found["before"]
        ctx["suggested_title"], ctx["suggested_sub"] = suggested_lines(
            found["position"],
            before["item"].name if before else None,
            found["ready"],
        )
        who = first_name(maker.name)
        ctx["next_sub"] = (
            f"Right after the item {who}'s on"
            if any(r["started"] for r in queue)
            else f"At the top of {who}'s queue"
        )
        ctx["submit_label"] = f"Assign to {who}"
    return ctx


def assign(order, employee, estimates: dict[int, int], place: str, now) -> Order:
    """Save the assignee, the estimates of not-started items and the queue places."""
    with transaction.atomic():
        # Lock order: employees, then the order, then its items (as start_item does).
        current = Order.objects.values_list("assignee_id", flat=True).get(pk=order.pk)
        list(
            Employee.objects.select_for_update()
            .filter(pk__in={employee.pk, current} - {None})
            .order_by("pk")
        )
        previous = order.assignee_id
        order = Order.objects.select_for_update().get(pk=order.pk)
        if previous != current or order.assignee_id != current:
            raise AssignError("This order just changed. Open it again.")
        if not assignable(order):
            raise AssignError("This order can't be assigned any more.")
        if order.assignee_id and order.assignee_id != employee.pk:
            session = open_session(order.assignee)
            if session and session.item_id and session.item.order_id == order.pk:
                stop(order.assignee, now)
        items = list(_items(order).select_for_update(of=("self",)))
        for item in items:
            if item.status == OrderItem.NOT_STARTED and item.pk in estimates:
                item.estimate_minutes = estimates[item.pk]
        order.assignee = employee
        order.save(update_fields=["assignee", "updated_at"])
        queue = _queue_without(employee, order, now)
        new = _new_rows(items, estimates, now)
        by_key = {r["key"]: r["item"] for r in new}
        for item in items:
            item.queue_rank = None
        if place == NEXT:
            at = next_up_rank(queue)
            for row in queue:
                if row["moved_to"] and row["moved_to"] >= at:
                    obj = row["rework"] or row["item"]
                    obj.queue_rank = row["moved_to"] + len(new)
                    obj.save(update_fields=["queue_rank"])
            for i, row in enumerate(suggested(new)):
                by_key[row["key"]].queue_rank = at + i
        for item in items:
            item.save(update_fields=["estimate_minutes", "queue_rank"])
        return order
