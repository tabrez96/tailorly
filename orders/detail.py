"""Pure helpers for the order detail page (S04)."""

from datetime import date

from core.formats import format_day, format_duration
from orders.making import ordinal
from staff.attendance import first_name

STEPS = [
    ("open", "Open"),
    ("in_progress", "In progress"),
    ("ready", "Ready"),
    ("delivered", "Delivered"),
]


def status_steps(status: str) -> list[dict]:
    """The four steps, each `done`, `current` or `todo` for the order's status."""
    keys = [key for key, _ in STEPS]
    current = keys.index(status)
    return [
        {
            "label": label,
            "state": "done" if i < current else "current" if i == current else "todo",
        }
        for i, (_, label) in enumerate(STEPS)
    ]


def assigned_line(name: str, place: int | None) -> str:
    """'Ali Khan · 2nd in Ali's queue', or just the name when there is no place."""
    if place is None:
        return name
    return f"{name} · {ordinal(place)} in {first_name(name)}'s queue"


def measurement_summary(tiles: list[dict], shown: int = 3) -> str:
    """'Bust 36 · Waist 30 · Shoulder 14.5 · +6' from the tiles that have values."""
    filled = [t for t in tiles if t["value"] != "—"]
    parts = [f"{t['label']} {t['value']}" for t in filled[:shown]]
    if len(filled) > shown:
        parts.append(f"+{len(filled) - shown}")
    return " · ".join(parts)


def queue_rank(others: list[tuple[int, date | None]], pk: int, due: date | None) -> int:
    """Place of an existing order in its queue: by due date (undated last), then pk."""
    key = (due is None, due or date.min, pk)
    return 1 + sum(1 for p, d in others if (d is None, d or date.min, p) < key)


def item_overline(number: int, customer: str, position: int, count: int) -> str:
    """'ORD-1042 · MEERA IYER · ITEM 1 OF 2' for the item page header."""
    return f"ORD-{number} · {customer} · item {position} of {count}".upper()


def item_meta(maker: str, logged: int, estimate: int | None, due: date | None) -> str:
    """'Ali · 2h 40m of 3h est. · due Fri 13 Nov'; times are in minutes."""
    parts = [maker]
    if estimate:
        parts.append(f"{format_duration(logged)} of {format_duration(estimate)} est.")
    elif logged > 0:
        parts.append(format_duration(logged))
    if due:
        parts.append(f"due {format_day(due)}")
    return " · ".join(p for p in parts if p)


def option_rows(answers: list[dict], when_done: set[str]) -> list[dict]:
    """The option answers of an item, each marked when it is asked at the end."""
    return [
        {"name": a["name"], "answer": a["answer"], "when_done": a["name"] in when_done}
        for a in answers
    ]


def photo_badge(count: int) -> str:
    """'1/3' for the first photo of several, else nothing."""
    return f"1/{count}" if count > 1 else ""
