"""The suggested work queue, owner moves and Late risk, as pure functions on row dicts.

A row has `key` (("item" | "rework", pk)), `started`, `due` (date | None),
`need` (minutes still needed) and `moved_to` (1-based place the owner chose, or None).
"""

from datetime import date, timedelta
from heapq import heappop, heappush

from core.formats import format_day, format_duration

DAY_MINUTES = 8 * 60


def best_key(row) -> tuple:
    """Due date (none last), then the shorter job, then items before reworks."""
    return (row["due"] is None, row["due"] or date.max, row["need"], row["key"])


def suggested_key(row) -> tuple:
    """Started first, then due date, then the shorter estimate (not time left)."""
    estimate = row.get("estimate", row["need"])
    return (
        not row["started"],
        row["due"] is None,
        row["due"] or date.max,
        estimate,
        row["key"],
    )


def suggested(rows) -> list:
    return sorted(rows, key=suggested_key)


def ordered(rows) -> list:
    """Owner moves keep their place; everything else follows the suggestion."""
    n = len(rows)
    slots = [None] * n
    moved = sorted(
        (r for r in rows if r["moved_to"]),
        key=lambda r: (r["moved_to"], suggested_key(r)),
    )
    for row in moved:
        at = min(row["moved_to"], n) - 1
        free = [i for i in range(n) if slots[i] is None]
        at = next((i for i in free if i >= at), free[-1])
        slots[at] = row
    rest = iter(suggested([r for r in rows if not r["moved_to"]]))
    return [s if s is not None else next(rest) for s in slots]


def clear_moves(rows) -> list:
    """Back to suggested."""
    return [{**r, "moved_to": None} for r in rows]


def late_keys(rows, today: date) -> set:
    """Keys that miss their due date even in the best order (DAY_MINUTES a day)."""
    late, total, kept = set(), 0, []
    dated = [r for r in rows if r["due"] is not None]
    late.update(r["key"] for r in dated if r["due"] < today)
    # Moore-Hodgson: on overshooting a due date, drop the longest job (fewest late).
    live = sorted((r for r in dated if r["due"] >= today), key=best_key)
    for at, row in enumerate(live):
        total += row["need"]
        heappush(kept, (-row["need"], -at, row["key"]))
        if total > ((row["due"] - today).days + 1) * DAY_MINUTES:
            need, _, key = heappop(kept)
            total += need
            late.add(key)
    return late


def due_text(due: date | None, today: date) -> str:
    if due is None:
        return "No due date"
    if due == today:
        return "Due today"
    if due == today + timedelta(days=1):
        return "Due tomorrow"
    return f"Due {format_day(due)}"


def due_soon(due: date | None, today: date) -> bool:
    return due is not None and due <= today + timedelta(days=2)


def time_text(row) -> str:
    return f"about {format_duration(row['need'])}" + (" left" if row["started"] else "")


def reason(row, today: date) -> str:
    need = format_duration(row["need"])
    if row["due"] is None:
        return f"No due date yet, and it needs about {need}."
    return f"{due_text(row['due'], today)} and needs about {need}."


def fit_text(total: int, late: int) -> str:
    if late == 0:
        if total == 1:
            return "It fits before its due date."
        return f"All {total} items fit before their due dates."
    if late == 1:
        return "1 item won't make its due date. Move it up or talk to the customer."
    return (
        f"{late} items won't make their due dates. "
        "Move them up or talk to the customers."
    )
