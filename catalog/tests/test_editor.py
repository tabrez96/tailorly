import json
from types import SimpleNamespace

import pytest

from catalog import editor
from catalog.editor import (
    EditorError,
    OptionData,
    option_to_dict,
    parse_measurements,
    parse_options,
)

MATERIALS = {7, 8}


def options(*items, materials=MATERIALS):
    return parse_options(json.dumps(items), materials)


def test_measurements_strip_and_keep_order():
    assert parse_measurements(json.dumps([" Bust ", "", "Waist"])) == ["Bust", "Waist"]


def test_measurements_empty_string_is_empty_list():
    assert parse_measurements("") == []


def test_measurements_duplicate_case_insensitive():
    with pytest.raises(EditorError) as e:
        parse_measurements(json.dumps(["Bust", "bust"]))
    assert e.value.message == editor.MEASUREMENT_DUPLICATE


def test_measurements_too_long_and_too_many():
    with pytest.raises(EditorError) as e:
        parse_measurements(json.dumps(["x" * 41]))
    assert e.value.message == editor.MEASUREMENT_TOO_LONG
    with pytest.raises(EditorError) as e:
        parse_measurements(json.dumps([f"m{i}" for i in range(31)]))
    assert e.value.message == editor.MEASUREMENTS_TOO_MANY


@pytest.mark.parametrize("raw", ["{", '{"a":1}', "[1]"])
def test_measurements_unreadable(raw):
    with pytest.raises(EditorError) as e:
        parse_measurements(raw)
    assert e.value.message == editor.MEASUREMENTS_UNREADABLE


def test_options_valid_yes_no_with_material():
    parsed, errors = options(
        {
            "name": " Lining ",
            "answer": "yes_no",
            "material": 7,
            "asks_quantity": True,
            "asks_notes": True,
            "asked_when": "when_done",
        }
    )
    assert parsed == [OptionData("Lining", "yes_no", [], 7, True, True, "when_done")]
    assert errors == [{}]


def test_options_empty_string():
    assert parse_options("", MATERIALS) == ([], [])


def test_options_name_required_and_too_long():
    assert options({"name": "  "})[1] == [{"name": editor.NAME_REQUIRED}]
    assert options({"name": "x" * 61})[1] == [{"name": editor.NAME_TOO_LONG}]


def test_choice_needs_two_choices():
    one = options({"name": "Sleeve", "answer": "choice", "choices": ["Short", ""]})
    assert one[1] == [{"choices": editor.CHOICES_TOO_FEW}]
    same = options(
        {"name": "Sleeve", "answer": "choice", "choices": ["Short", "short"]}
    )
    assert same[1] == [{"choices": editor.CHOICE_DUPLICATE}]
    long = options({"name": "Sleeve", "answer": "choice", "choices": ["a", "b" * 41]})
    assert long[1] == [{"choices": editor.CHOICE_TOO_LONG}]
    none = options({"name": "Sleeve", "answer": "choice", "choices": "Short"})
    assert none[1] == [{"choices": editor.CHOICES_TOO_FEW}]


def test_choice_valid_keeps_order():
    parsed, errors = options(
        {"name": "Sleeve", "answer": "choice", "choices": ["Short", "Full"]}
    )
    assert parsed[0].choices == ["Short", "Full"]
    assert errors == [{}]


def test_yes_no_drops_choices():
    parsed, errors = options({"name": "Lining", "choices": ["a"]})
    assert parsed[0].choices == []
    assert errors == [{}]


def test_material_not_allowed():
    assert options({"name": "A", "material": 99})[1] == [
        {"material": editor.MATERIAL_INVALID}
    ]
    assert options({"name": "A", "material": "abc"})[1] == [
        {"material": editor.MATERIAL_INVALID}
    ]
    assert options({"name": "A", "material": ""})[1] == [{}]


def test_quantity_needs_material():
    parsed, _ = options({"name": "A", "asks_quantity": True})
    assert parsed[0].asks_quantity is False


def test_unknown_values_default():
    parsed, _ = options(
        {"name": "A", "answer": "x", "asked_when": "x", "uid": 4, "open": True}
    )
    assert parsed[0].answer == "yes_no"
    assert parsed[0].asked_when == "at_order"


@pytest.mark.parametrize("raw", ["{", '{"a":1}', "[1]"])
def test_options_unreadable(raw):
    with pytest.raises(EditorError) as e:
        parse_options(raw, MATERIALS)
    assert e.value.message == editor.OPTIONS_UNREADABLE


def test_options_too_many():
    with pytest.raises(EditorError) as e:
        parse_options(json.dumps([{"name": "A"}] * 21), MATERIALS)
    assert e.value.message == editor.OPTIONS_TOO_MANY


def test_option_to_dict_round_trip():
    saved = SimpleNamespace(
        name="Sleeve",
        answer="choice",
        choices=["Short", "Full"],
        material_id=7,
        asks_quantity=True,
        asks_notes=False,
        asked_when="when_done",
    )
    parsed, errors = parse_options(json.dumps([option_to_dict(saved)]), MATERIALS)
    assert errors == [{}]
    assert parsed == [
        OptionData("Sleeve", "choice", ["Short", "Full"], 7, True, False, "when_done")
    ]
