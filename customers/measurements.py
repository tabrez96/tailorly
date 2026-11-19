"""Parse, convert and merge saved measurement values (stored in inches)."""

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

INCHES, CM = "in", "cm"
CM_PER_INCH = Decimal("2.54")
MAX_INCHES = Decimal(120)
MAX_NAME = 40
NUMBER_INVALID = "Enter a number, like 34 or 11.5."
NUMBER_RANGE = "Enter a size above 0 and up to 120 inches."
NAME_REQUIRED = "Enter a name for this measurement."
NAME_TOO_LONG = "Use 40 characters or fewer."
NAME_DUPLICATE = "Each measurement needs a different name."
_NUMBER = re.compile(r"^\d+(\.\d+)?$", re.ASCII)
_CENT = Decimal("0.01")


@dataclass
class Row:
    name: str
    value: str  # as shown in the input ("" when empty)
    new: bool = False  # added with + Add measurement in this edit (name is an input)
    error: str = ""
    field: str = "value"  # which input the error belongs to: "name" or "value"


def to_inches(value: Decimal, unit: str) -> Decimal:
    if unit == CM:
        value = value / CM_PER_INCH
    return value.quantize(_CENT, ROUND_HALF_UP)


def format_value(value: Decimal) -> str:
    return f"{value.quantize(_CENT).normalize():f}"


def parse_value(raw: str, unit: str) -> Decimal | None:
    raw = raw.strip()
    if not raw:
        return None
    if not _NUMBER.match(raw):
        raise ValueError(NUMBER_INVALID)
    try:
        inches = to_inches(Decimal(raw), unit)
    except InvalidOperation:  # too many digits for the decimal context
        raise ValueError(NUMBER_RANGE) from None
    if inches <= 0 or inches > MAX_INCHES:
        raise ValueError(NUMBER_RANGE)
    return inches


def merge_fields(product_fields: list[str], saved: list[dict]) -> list[Row]:
    """Product fields in order with saved values, then the saved fields it lacks."""
    by_name = {s["name"].casefold(): s["value"] for s in saved}
    rows = [Row(f, by_name.get(f.casefold(), "")) for f in product_fields]
    known = {f.casefold() for f in product_fields}
    rows += [
        Row(s["name"], s["value"]) for s in saved if s["name"].casefold() not in known
    ]
    return rows


def _padded(a: list[str], b: list[str]) -> tuple[list[str], list[str]]:
    n = max(len(a), len(b))
    return a + [""] * (n - len(a)), b + [""] * (n - len(b))


def clean_rows(
    fields: list[str],
    values: list[str],
    new_names: list[str],
    new_values: list[str],
    unit: str,
) -> tuple[list[dict], list[Row]]:
    """Validate posted rows: the pairs to store (inches) and the rows to show."""
    fields, values = _padded(fields, values)
    new_names, new_values = _padded(new_names, new_values)
    candidates = [
        Row(f.strip(), v.strip()) for f, v in zip(fields, values, strict=True)
    ]
    candidates += [
        Row(n.strip(), v.strip(), new=True)
        for n, v in zip(new_names, new_values, strict=True)
    ]
    rows: list[Row] = []
    pairs: list[dict] = []
    for row in candidates:
        if row.new and not row.value:
            continue
        inches = None
        try:
            inches = parse_value(row.value, unit)
        except ValueError as e:
            row.error = str(e)
        if row.new and row.value:
            name_error = ""
            if not row.name:
                name_error = NAME_REQUIRED
            elif len(row.name) > MAX_NAME:
                name_error = NAME_TOO_LONG
            elif any(r.name.casefold() == row.name.casefold() for r in rows):
                name_error = NAME_DUPLICATE
            if name_error:
                row.error, row.field = name_error, "name"
        rows.append(row)
        if inches is not None and not row.error:
            pairs.append({"name": row.name, "value": format_value(inches)})
    return pairs, rows


def tiles(product_fields: list[str], saved: list[dict]) -> list[dict]:
    return [
        {"label": r.name, "value": r.value or "—"}
        for r in merge_fields(product_fields, saved)
    ]
