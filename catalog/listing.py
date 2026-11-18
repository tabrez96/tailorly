from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlencode

SOLD, MATERIALS = "sold", "materials"
TYPES = ("custom", "ready_made")


@dataclass(frozen=True)
class ListFilter:
    kind: str = SOLD
    type: str = ""  # "" means All
    q: str = ""


def parse_filter(params: Mapping[str, str]) -> ListFilter:
    kind = MATERIALS if params.get("kind") == MATERIALS else SOLD
    type_ = params.get("type", "")
    if type_ not in TYPES or kind != SOLD:
        type_ = ""
    return ListFilter(kind, type_, params.get("q", "").strip()[:80])


def filter_url(base: str, f: ListFilter) -> str:
    query = {}
    if f.kind != SOLD:
        query["kind"] = f.kind
    if f.type:
        query["type"] = f.type
    if f.q:
        query["q"] = f.q
    return f"{base}?{urlencode(query)}" if query else base


def options_summary(names: list[str]) -> str:
    if not names:
        return "No options"
    noun = "option" if len(names) == 1 else "options"
    return f"{len(names)} {noun}: {', '.join(names)}"


def uses_summary(uses: list[tuple[str, int, str]]) -> str:
    """`uses` is (option name, product id, product name) per option using the material.

    Products are told apart by id: names are not unique.
    """
    if not uses:
        return "picked by hand"
    options = ", ".join(dict.fromkeys(option for option, _, _ in uses))
    products = {product_id: name for _, product_id, name in uses}
    if len(products) == 1:
        return f"{options} on {next(iter(products.values()))}"
    return f"{options} on {len(products)} products"


def _join(items: list[str]) -> str:
    items = list(dict.fromkeys(items))
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} and {items[-1]}"


def material_used_by(uses: list[tuple[str, str]]) -> str:
    """Sheet subtitle for a material; `uses` is (option name, product name) pairs."""
    note = "Changes apply to new orders only."
    if not uses:
        return note
    options = list(dict.fromkeys(option for option, _ in uses))
    noun = "option" if len(options) == 1 else "options"
    products = _join([product for _, product in uses])
    return f"Used by the {_join(options)} {noun} on {products}. {note}"
