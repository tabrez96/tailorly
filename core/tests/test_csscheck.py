import pytest

from core.csscheck import (
    colour_literals,
    declarations,
    template_colour_literals,
    value_colour_literals,
)


def test_hex_rgb_hsl_and_named_found():
    found = colour_literals("a{color:#fff;b:rgba(0,0,0,.1);c:white}")
    assert len(found) == 3


def test_tokens_and_keywords_allowed():
    css = "a{color:var(--ink);background:transparent;fill:currentColor}"
    assert colour_literals(css) == []


def test_comments_ignored():
    assert colour_literals("/* #fff and white */ a{color:var(--ink)}") == []


def test_named_colour_in_selector_ignored():
    assert colour_literals(".white-card{color:var(--ink)}") == []


def test_template_style_contexts():
    assert template_colour_literals('<p style="color:#000">x</p>') == ["#000"]
    assert template_colour_literals("<style>a{color:red}</style>") == ["red"]
    assert template_colour_literals('<path fill="#fff">') == ["#fff"]
    assert template_colour_literals('<a href="#add">Add</a>') == []


def test_template_unquoted_attributes():
    assert template_colour_literals("<p style=color:red>x</p>") == ["red"]
    assert template_colour_literals("<path fill=red>") == ["red"]
    assert template_colour_literals("<path fill=#fff stroke=none>") == ["#fff"]


def test_template_data_attributes_ignored():
    assert template_colour_literals('<div data-color="red"></div>') == []
    assert template_colour_literals('<div data-style="color:red"></div>') == []


def test_declarations_parses_block():
    assert declarations("x{--a: 1px; --b:#fff}", "x") == {"--a": "1px", "--b": "#fff"}
    with pytest.raises(KeyError):
        declarations("x{--a: 1px}", "y")


def test_declarations_selector_must_match_exactly():
    css = "a:root{--a: 1} :root{--b: 2}"
    assert declarations(css, ":root") == {"--b": "2"}


def test_all_css_named_colours_found():
    for name in ("cyan", "teal", "rebeccapurple", "lightgoldenrodyellow"):
        assert colour_literals(f"a{{color:{name}}}") == [name]


def test_bare_value_named_colour_found():
    assert value_colour_literals("red") == ["red"]
    assert value_colour_literals("var(--ink)") == []


def test_custom_property_identifier_is_not_a_colour():
    assert colour_literals("a{color:var(--red)}") == []
    assert colour_literals("a{color:var(--dark-red, var(--ink))}") == []


def test_var_fallback_literal_still_found():
    assert colour_literals("a{color:var(--ink, red)}") == ["red"]
    assert value_colour_literals("var(--ink, #fff)") == ["#fff"]
