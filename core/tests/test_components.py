import re

import pytest
from django.template import Context, Template

from core.nav import nav_items

ICONS = [
    "house",
    "list",
    "people",
    "hanger",
    "spool",
    "badge",
    "bars",
    "stopwatch",
    "wallet",
    "chevron-back",
    "chevron-right",
    "plus",
    "camera",
    "drag",
]


def render(source, **context):
    return Template("{% load ui %}" + source).render(Context(context))


def test_nav_items_owner():
    items = nav_items("owner", "orders")
    assert [e["item"].label for e in items] == [
        "Today",
        "Orders",
        "Customers",
        "Products",
        "Production",
    ]
    assert [e["item"].icon for e in items] == [
        "house",
        "list",
        "people",
        "hanger",
        "spool",
    ]
    assert [e["item"].label for e in items if e["current"]] == ["Orders"]


def test_nav_items_employee():
    items = nav_items("employee")
    assert [e["item"].label for e in items] == ["My work", "My pay"]
    assert [e["item"].icon for e in items] == ["stopwatch", "wallet"]


@pytest.mark.parametrize("active", ["nope", None])
def test_nav_items_unknown_active_marks_nothing(active):
    assert not any(e["current"] for e in nav_items("owner", active))


def test_nav_items_unknown_role():
    with pytest.raises(KeyError):
        nav_items("guest")


def test_bottom_nav_renders_aria_current():
    html = render('{% bottom_nav "owner" "orders" %}')
    assert html.count('aria-current="page"') == 1
    assert re.search(r'<a[^>]*href="/orders/"[^>]*aria-current="page"', html)
    for label in ["Today", "Orders", "Customers", "Products", "Production"]:
        assert f">{label}</span>" in html
    for icon in ["house", "list", "people", "hanger", "spool"]:
        assert f'data-icon="{icon}"' in html


def test_bottom_nav_employee():
    html = render('{% bottom_nav "employee" "my_work" %}')
    assert html.count('class="nav__item"') == 2
    assert re.search(r'<a[^>]*href="/my-work/"[^>]*aria-current="page"', html)
    assert "My pay" in html


@pytest.mark.parametrize("name", ICONS)
def test_icon_partial_every_name(name):
    html = render('{% include "components/icon.html" with name=n %}', n=name)
    for part in [
        f'data-icon="{name}"',
        "<path",
        'stroke-width="1.9"',
        'stroke-linecap="round"',
        'stroke="currentColor"',
        'aria-hidden="true"',
    ]:
        assert part in html


def test_icon_partial_unknown_name():
    html = render('{% include "components/icon.html" with name="nope" %}')
    assert "<svg" in html
    assert "<path" not in html


def test_header_full():
    html = render(
        '{% include "components/header.html" with back_url="/b/" overline="Thu 12 Nov"'
        ' title="ORD-1" action_label="Edit" action_url="/e/" %}'
    )
    for part in [
        'aria-label="Back"',
        'data-icon="chevron-back"',
        "Thu 12 Nov",
        "<h1",
        "ORD-1",
        "btn--tonal",
        'href="/e/"',
    ]:
        assert part in html


def test_header_minimal():
    html = render('{% include "components/header.html" with title="Orders" %}')
    assert "Orders" in html
    for part in ["header__back", "t-over", "header__action"]:
        assert part not in html


def test_header_action_without_url_is_button():
    html = render(
        '{% include "components/header.html" with title="Orders" action_label="Edit" %}'
    )
    assert (
        '<button class="btn btn--tonal btn--sm header__action" type="button">' in html
    )
