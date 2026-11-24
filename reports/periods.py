"""Day, week and month periods with previous and next, for the S13 and S14 reports."""

from dataclasses import dataclass
from datetime import date
from urllib.parse import urlencode

from django.urls import reverse

from core.formats import format_day
from production.report import DAY, MONTH, WEEK, period_range, step
from reports import sales

LABELS = {DAY: "Day", WEEK: "Week", MONTH: "Month"}


@dataclass(frozen=True)
class Nav:
    key: str  # DAY | WEEK | MONTH
    day: date  # any day inside the period, never after today
    first: date
    last: date


def parse(params, today: date, keys: tuple[str, ...]) -> Nav:
    key = params.get("period", "")
    if key not in keys:
        key = MONTH
    day = sales._date_or(params.get("date", ""), today)
    day = min(max(day, sales.EARLIEST), today)
    first, last = period_range(key, day)
    return Nav(key, day, first, last)


def label(nav: Nav) -> str:
    if nav.key == MONTH:
        return f"{nav.first:%B} {nav.first.year}"
    if nav.key == WEEK:
        return sales.range_text(nav.first, nav.last)
    return format_day(nav.first)


def query(key: str, day: date, today: date) -> str:
    params = {}
    if key != MONTH:
        params["period"] = key
    first, last = period_range(key, today)
    if not first <= day <= last:
        params["date"] = day.isoformat()
    return urlencode(params)


def url(name: str, key: str, day: date, today: date) -> str:
    base = reverse(name)
    q = query(key, day, today)
    return f"{base}?{q}" if q else base


def nav_context(name: str, nav: Nav, today: date, keys) -> dict:
    after = step(nav.key, nav.day, 1)
    return {
        "segments": [
            {
                "id": f"period-{k}",
                "label": LABELS[k],
                "url": url(name, k, today, today),
                "selected": k == nav.key,
            }
            for k in keys
        ],
        "label": label(nav),
        "prev_url": url(name, nav.key, step(nav.key, nav.day, -1), today),
        "next_url": "" if after > today else url(name, nav.key, after, today),
        "report_query": query(nav.key, nav.day, today),
    }


def hero_range(nav: Nav, today: date) -> str:
    return sales.range_text(nav.first, min(nav.last, today))
