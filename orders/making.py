"""Pure helpers for the "Making it" section of a new order."""

import re
from datetime import date

USUAL_MINUTES = 120  # until the work-plan ticket averages the last 10 of each product
MAX_MINUTES = 5999
DURATION_INVALID = "Enter a time like 2h 30m."

_HOURS_MINUTES = re.compile(r"^(?:(\d{1,2})\s*h)?\s*(?:(\d{1,3})\s*m)?$")
_CLOCK = re.compile(r"^(\d{1,2}):(\d{2})$")
_HOURS = re.compile(r"^(\d{1,2})$")


def usual_minutes(product) -> int:
    return USUAL_MINUTES


def parse_duration(text: str) -> int | None:
    """Minutes for "2h 30m", "2h", "45m", "2:30" or "2" (hours); None when blank."""
    text = text.strip().lower()
    if not text:
        return None
    hours = minutes = None
    if match := _HOURS_MINUTES.match(text):
        hours, minutes = match.groups()
        if hours is None and minutes is None:
            raise ValueError(DURATION_INVALID)
    elif match := _CLOCK.match(text):
        hours, minutes = match.groups()
    elif match := _HOURS.match(text):
        hours = match.group(1)
    else:
        raise ValueError(DURATION_INVALID)
    if hours is not None and minutes is not None and int(minutes) >= 60:
        raise ValueError(DURATION_INVALID)
    total = int(hours or 0) * 60 + int(minutes or 0)
    if not 1 <= total <= MAX_MINUTES:
        raise ValueError(DURATION_INVALID)
    return total


def queue_place(due_dates: list[date | None], due: date | None) -> int:
    """Where a new order lands in a queue: by due date, undated orders last."""
    if due is None:
        return len(due_dates) + 1
    return 1 + sum(1 for d in due_dates if d is not None and d <= due)


def ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"
