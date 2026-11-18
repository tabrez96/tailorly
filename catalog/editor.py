"""Parse and validate what the product sheet's measurement and option editors post."""

import json
from dataclasses import dataclass

MAX_MEASUREMENTS = 30
MAX_OPTIONS = 20
MEASUREMENTS_UNREADABLE = "Measurements could not be read. Try again."
MEASUREMENT_TOO_LONG = "Use 40 characters or fewer for each measurement."
MEASUREMENT_DUPLICATE = "Each measurement needs a different name."
MEASUREMENTS_TOO_MANY = "Use 30 measurements or fewer."
OPTIONS_UNREADABLE = "Options could not be read. Try again."
OPTIONS_TOO_MANY = "Use 20 options or fewer."
OPTIONS_FIX = "Fix the options marked below."
NAME_REQUIRED = "Enter an option name."
NAME_TOO_LONG = "Use 60 characters or fewer."
CHOICES_TOO_FEW = "Add at least 2 choices."
CHOICE_TOO_LONG = "Use 40 characters or fewer for each choice."
CHOICE_DUPLICATE = "Each choice needs a different name."
MATERIAL_INVALID = "Choose a material from the list."


class EditorError(ValueError):
    """Whole-field error; .message is shown under the field."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class OptionData:
    name: str
    answer: str  # "yes_no" | "choice"
    choices: list[str]  # [] for yes_no
    material: int | None
    asks_quantity: bool
    asks_notes: bool
    asked_when: str  # "at_order" | "when_done"


def load_list(raw: str) -> list:
    """'' -> []. Raises ValueError when the text is not a JSON list."""
    if not raw:
        return []
    value = json.loads(raw)
    if not isinstance(value, list):
        raise ValueError("not a list")
    return value


def parse_measurements(raw: str) -> list[str]:
    try:
        items = load_list(raw)
    except ValueError:
        raise EditorError(MEASUREMENTS_UNREADABLE) from None
    if not all(isinstance(item, str) for item in items):
        raise EditorError(MEASUREMENTS_UNREADABLE)
    names = [item.strip() for item in items if item.strip()]
    if any(len(name) > 40 for name in names):
        raise EditorError(MEASUREMENT_TOO_LONG)
    if _has_duplicate(names):
        raise EditorError(MEASUREMENT_DUPLICATE)
    if len(names) > MAX_MEASUREMENTS:
        raise EditorError(MEASUREMENTS_TOO_MANY)
    return names


def _has_duplicate(names: list[str]) -> bool:
    return len({name.casefold() for name in names}) != len(names)


def _parse_material(value, material_ids: set[int]) -> tuple[int | None, bool]:
    """(material id or None, valid)."""
    if value is None or value == "":
        return None, True
    try:
        material = int(value)
    except TypeError, ValueError:
        return None, False
    return material, material in material_ids


def _parse_option(item: dict, material_ids: set[int]) -> tuple[OptionData, dict]:
    errors: dict[str, str] = {}
    name = str(item.get("name") or "").strip()
    if not name:
        errors["name"] = NAME_REQUIRED
    elif len(name) > 60:
        errors["name"] = NAME_TOO_LONG

    answer = "choice" if item.get("answer") == "choice" else "yes_no"
    choices: list[str] = []
    if answer == "choice":
        raw_choices = item.get("choices")
        if isinstance(raw_choices, list):
            choices = [str(c).strip() for c in raw_choices if str(c).strip()]
        if any(len(c) > 40 for c in choices):
            errors["choices"] = CHOICE_TOO_LONG
        elif _has_duplicate(choices):
            errors["choices"] = CHOICE_DUPLICATE
        elif len(choices) < 2:
            errors["choices"] = CHOICES_TOO_FEW

    material, valid = _parse_material(item.get("material"), material_ids)
    if not valid:
        errors["material"] = MATERIAL_INVALID
        material = None

    option = OptionData(
        name=name,
        answer=answer,
        choices=choices,
        material=material,
        asks_quantity=bool(item.get("asks_quantity")) and material is not None,
        asks_notes=bool(item.get("asks_notes")),
        asked_when="when_done" if item.get("asked_when") == "when_done" else "at_order",
    )
    return option, errors


def parse_options(
    raw: str, material_ids: set[int]
) -> tuple[list[OptionData], list[dict[str, str]]]:
    """Options in order, and one error dict per option (empty when it is fine)."""
    try:
        items = load_list(raw)
    except ValueError:
        raise EditorError(OPTIONS_UNREADABLE) from None
    if not all(isinstance(item, dict) for item in items):
        raise EditorError(OPTIONS_UNREADABLE)
    if len(items) > MAX_OPTIONS:
        raise EditorError(OPTIONS_TOO_MANY)
    parsed = [_parse_option(item, material_ids) for item in items]
    return [option for option, _ in parsed], [errors for _, errors in parsed]


def option_to_dict(option) -> dict:
    """Saved ProductOption -> the editor's JSON shape."""
    return {
        "name": option.name,
        "answer": option.answer,
        "choices": list(option.choices),
        "material": option.material_id,
        "asks_quantity": option.asks_quantity,
        "asks_notes": option.asks_notes,
        "asked_when": option.asked_when,
    }
