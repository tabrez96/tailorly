import pytest

from catalog.listing import (
    ListFilter,
    filter_url,
    options_summary,
    parse_filter,
    uses_summary,
)


def test_parse_filter_defaults():
    assert parse_filter({}) == ListFilter("sold", "", "")


def test_parse_filter_materials_drops_type():
    assert parse_filter({"kind": "materials", "type": "custom"}) == ListFilter(
        "materials", "", ""
    )
    assert parse_filter({"type": "custom"}).type == "custom"


def test_parse_filter_unknown_values():
    assert parse_filter({"kind": "other", "type": "nope"}) == ListFilter()


def test_parse_filter_trims_and_caps_q():
    assert parse_filter({"q": "  blo  "}).q == "blo"
    assert len(parse_filter({"q": "a" * 200}).q) == 80


def test_filter_url_default_has_no_query():
    assert filter_url("/products/", ListFilter()) == "/products/"


def test_filter_url_orders_params():
    assert (
        filter_url("/products/", ListFilter("sold", "custom", "blo"))
        == "/products/?type=custom&q=blo"
    )
    assert (
        filter_url("/products/", ListFilter("materials", "", "a b"))
        == "/products/?kind=materials&q=a+b"
    )


@pytest.mark.parametrize(
    ("names", "text"),
    [
        ([], "No options"),
        (["Lining"], "1 option: Lining"),
        (
            ["Lining", "Sleeve style", "Padding"],
            "3 options: Lining, Sleeve style, Padding",
        ),
    ],
)
def test_options_summary(names, text):
    assert options_summary(names) == text


@pytest.mark.parametrize(
    ("uses", "text"),
    [
        ([], "picked by hand"),
        ([("Collar", 1, "Kurta")], "Collar on Kurta"),
        (
            [("Lining", 1, "A"), ("Lining", 2, "B"), ("Lining", 3, "C")],
            "Lining on 3 products",
        ),
        (
            [("Lining", 1, "A"), ("Padding", 1, "A"), ("Lining", 2, "B")],
            "Lining, Padding on 2 products",
        ),
        ([("Lining", 1, "A"), ("Lining", 1, "A")], "Lining on A"),
        ([("Lining", 1, "Blouse"), ("Lining", 2, "Blouse")], "Lining on 2 products"),
    ],
)
def test_uses_summary(uses, text):
    assert uses_summary(uses) == text
