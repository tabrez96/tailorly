"""Pure helpers for the order detail page (S04)."""

from datetime import date

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
