"""The running-costs form: rows to show and posted rows to validate. Pure."""

from dataclasses import dataclass
from decimal import Decimal

from staff.attendance import parse_decimal

DEFAULT_NAMES = ("Rent", "Electricity", "Thread, needles and buttons")
NAME_MAX = 60
MAX_HOURS = 744
NAME_ERROR = "Name this cost."
AMOUNT_ERROR = "Enter an amount of 0 or more, like 1800."
HOURS_ERROR = "Enter the hours you work in a month, like 208."


@dataclass(frozen=True)
class Row:
    name: str
    amount: str
    fixed: bool  # a named line, shown as a label
    error: str = ""
    name_error: bool = False  # the error belongs to the name input


def _amount_text(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01')).normalize():f}"


def rows_for(lines: list[dict]) -> list[Row]:
    """The three default names first (saved amount, else blank), then the others."""
    # Each default takes the first saved line with its name; every other line,
    # duplicates included, keeps its own row so re-saving never drops an amount.
    first = {}
    for index, line in enumerate(lines):
        if line["name"] in DEFAULT_NAMES:
            first.setdefault(line["name"], index)
    rows = [
        Row(
            name,
            _amount_text(Decimal(lines[first[name]]["amount"]))
            if name in first
            else "",
            True,
        )
        for name in DEFAULT_NAMES
    ]
    taken = set(first.values())
    rows += [
        Row(line["name"], _amount_text(Decimal(line["amount"])), True)
        for index, line in enumerate(lines)
        if index not in taken
    ]
    return rows


def parse(
    names: list[str], amounts: list[str], fixed: list[str]
) -> tuple[list[dict], list[Row]]:
    """Posted rows -> (lines to save, rows to redisplay with errors)."""
    lines, rows = [], []
    for raw_name, raw_amount, flag in zip(names, amounts, fixed, strict=False):
        name = raw_name.strip()[:NAME_MAX]
        text = raw_amount.strip()
        for junk in (",", "₹", " "):
            text = text.replace(junk, "")
        error = ""
        value = None
        if text:
            value = parse_decimal(text)
            if value is None or value < 0 or value >= 10**10:
                error = AMOUNT_ERROR
            elif value != value.quantize(Decimal("0.01")):
                error = AMOUNT_ERROR
            elif not name:
                error = NAME_ERROR
        rows.append(Row(name, text, flag == "1", error, error == NAME_ERROR))
        if text and not error:
            lines.append({"name": name, "amount": _amount_text(value)})
    return lines, rows


def parse_hours(raw: str) -> tuple[int | None, str]:
    text = raw.strip()
    if text.isascii() and text.isdigit() and 1 <= int(text) <= MAX_HOURS:
        return int(text), ""
    return None, HOURS_ERROR
