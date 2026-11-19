from decimal import Decimal

import pytest

from customers.measurements import (
    CM,
    INCHES,
    NAME_DUPLICATE,
    NAME_REQUIRED,
    NAME_TOO_LONG,
    NUMBER_INVALID,
    NUMBER_RANGE,
    clean_rows,
    format_value,
    merge_fields,
    parse_value,
    tiles,
    to_inches,
)


def test_to_inches_converts_cm():
    assert to_inches(Decimal("86.36"), CM) == Decimal("34.00")
    assert to_inches(Decimal("34"), INCHES) == Decimal("34.00")


def test_format_value_trims_zeros():
    assert format_value(Decimal("34.00")) == "34"
    assert format_value(Decimal("11.50")) == "11.5"
    assert format_value(Decimal("30")) == "30"


def test_parse_value_blank_is_none():
    assert parse_value("  ", INCHES) is None


@pytest.mark.parametrize("raw", ["abc", "-1", "1e3", "11,5"])
def test_parse_value_rejects_text_and_signs(raw):
    with pytest.raises(ValueError, match=NUMBER_INVALID):
        parse_value(raw, INCHES)


def test_parse_value_range():
    for raw, unit in [("0", INCHES), ("121", INCHES), ("400", CM)]:
        with pytest.raises(ValueError, match=NUMBER_RANGE):
            parse_value(raw, unit)
    assert parse_value("120", INCHES) == Decimal("120")


def test_merge_fields_product_order_then_custom():
    saved = [
        {"name": "Hip", "value": "38"},
        {"name": "bust", "value": "34"},
        {"name": "Old", "value": "5"},
    ]
    rows = merge_fields(["Waist", "Bust"], saved)
    assert [(r.name, r.value) for r in rows] == [
        ("Waist", ""),
        ("Bust", "34"),
        ("Hip", "38"),
        ("Old", "5"),
    ]


def test_clean_rows_drops_blanks_and_converts_cm():
    pairs, rows = clean_rows(
        ["Bust", "Waist"], ["86.36", ""], ["Hip", "Neck"], ["96.52", ""], CM
    )
    assert pairs == [{"name": "Bust", "value": "34"}, {"name": "Hip", "value": "38"}]
    assert [r.name for r in rows] == ["Bust", "Waist", "Hip"]
    assert not any(r.error for r in rows)


def test_clean_rows_new_row_errors():
    _, rows = clean_rows(
        ["Bust"], ["34"], ["", "x" * 41, "bust", "Skip"], ["5", "5", "5", ""], INCHES
    )
    assert [r.error for r in rows] == [
        "",
        NAME_REQUIRED,
        NAME_TOO_LONG,
        NAME_DUPLICATE,
    ]
    assert all(r.name != "Skip" for r in rows)


def test_clean_rows_value_error_not_stored():
    pairs, rows = clean_rows(["Bust"], ["abc"], [], [], INCHES)
    assert pairs == []
    assert rows[0].error == NUMBER_INVALID


def test_clean_rows_pads_uneven_lists():
    pairs, rows = clean_rows(["Bust", "Waist"], ["34"], ["Hip"], [], INCHES)
    assert pairs == [{"name": "Bust", "value": "34"}]
    assert [r.name for r in rows] == ["Bust", "Waist"]


def test_tiles_dash_for_missing():
    assert tiles(["Bust", "Waist"], [{"name": "Bust", "value": "34"}]) == [
        {"label": "Bust", "value": "34"},
        {"label": "Waist", "value": "—"},
    ]


def test_parse_value_rejects_non_ascii_digits():
    with pytest.raises(ValueError, match=NUMBER_INVALID):
        parse_value("३४", CM)


def test_parse_value_huge_number_is_range_error():
    for unit in (INCHES, CM):
        with pytest.raises(ValueError, match=NUMBER_RANGE):
            parse_value("9" * 40, unit)


def test_clean_rows_error_field():
    _, rows = clean_rows([], [], ["", "Hip"], ["5", "abc"], INCHES)
    assert [(r.error, r.field) for r in rows] == [
        (NAME_REQUIRED, "name"),
        (NUMBER_INVALID, "value"),
    ]
