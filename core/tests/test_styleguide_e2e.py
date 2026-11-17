from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

SCHEMES = ["light", "dark"]
ARTIFACTS = Path(__file__).resolve().parent.parent.parent / "artifacts" / "screens"
BUTTONS = ["btn-primary", "btn-tonal", "btn-accent", "btn-ghost", "btn-disabled"]
CHIPS = ["chip-ok", "chip-warn", "chip-bad", "chip-pri", "chip-grey"]
STYLE_PROPS = [
    "background-color",
    "background-image",
    "color",
    "border-top-color",
    "box-shadow",
]


@pytest.fixture
def open_page(live_server, browser, settings):
    settings.DEBUG = True
    contexts = []

    def _open(scheme):
        context = browser.new_context(
            viewport={"width": 390, "height": 844}, color_scheme=scheme
        )
        contexts.append(context)
        page = context.new_page()
        page.goto(live_server.url + "/styleguide/")
        page.evaluate("document.fonts.ready.then(() => true)")
        return page

    yield _open
    for context in contexts:
        context.close()


def _styles(page, selector):
    return page.eval_on_selector(
        selector,
        "(el, props) => props.map(p => getComputedStyle(el)[p])",
        STYLE_PROPS,
    )


def _radius(page, selector):
    return page.eval_on_selector(
        selector, "el => getComputedStyle(el).borderTopLeftRadius"
    )


@pytest.mark.parametrize("scheme", SCHEMES)
def test_sizes(open_page, scheme):
    page = open_page(scheme)
    for name in BUTTONS:
        selector = f"[data-sg={name}]"
        assert page.locator(selector).bounding_box()["height"] == 48
        assert _radius(page, selector) == "999px"
    assert page.locator("[data-sg=btn-sm]").bounding_box()["height"] == 44
    assert _radius(page, "[data-sg=btn-sm]") == "999px"
    for name in CHIPS:
        assert _radius(page, f"[data-sg={name}] .chip") == "999px"
    assert _radius(page, "[data-sg=card]") == "20px"
    assert _radius(page, "[data-sg=hero]") == "24px"
    assert _radius(page, "[data-sg=list]") == "20px"
    rows = page.locator("[data-sg=list] .list__row")
    for i in range(rows.count()):
        assert rows.nth(i).bounding_box()["height"] >= 60
    back = page.locator("[data-sg=header-sub] .header__back")
    assert back.bounding_box()["width"] == 44
    assert back.bounding_box()["height"] == 44
    assert _radius(page, "[data-sg=header-sub] .header__back") == "999px"
    actions = page.locator(".header__action")
    for i in range(actions.count()):
        assert actions.nth(i).bounding_box()["height"] == 44
        assert (
            actions.nth(i).evaluate("el => getComputedStyle(el).borderTopLeftRadius")
            == "999px"
        )
    nav = page.locator("[data-sg=nav-owner] .nav").bounding_box()
    frame = page.locator("[data-sg=nav-owner]").bounding_box()
    assert nav["height"] == 68
    assert _radius(page, "[data-sg=nav-owner] .nav") == "999px"
    # The frame has a 1px dashed border; fixed children sit inside its padding box.
    assert abs(nav["x"] - frame["x"] - 13) <= 0.5
    assert abs(frame["x"] + frame["width"] - nav["x"] - nav["width"] - 13) <= 0.5
    assert abs(frame["y"] + frame["height"] - nav["y"] - nav["height"] - 13) <= 0.5
    items = page.locator("[data-sg=nav-owner] .nav__item")
    widths = [items.nth(i).bounding_box()["width"] for i in range(items.count())]
    assert len(widths) == 5 and max(widths) - min(widths) < 0.5
    assert _radius(page, "[data-sg=nav-owner] .nav__item[aria-current=page]") == "999px"
    corners = page.eval_on_selector(
        "[data-sg=sheet]",
        """el => ["TopLeft", "TopRight", "BottomLeft"].map(
            c => getComputedStyle(el)["border" + c + "Radius"])""",
    )
    assert corners == ["28px", "28px", "0px"]
    assert page.locator(".sheet__handle").is_visible()
    bar = page.eval_on_selector(
        "[data-sg=action-bar]",
        """el => ["TopLeft", "BottomLeft"].map(
            c => getComputedStyle(el)["border" + c + "Radius"])""",
    )
    assert bar == ["20px", "0px"]


@pytest.mark.parametrize("scheme", SCHEMES)
def test_header_action_stays_on_title_row(open_page, scheme):
    page = open_page(scheme)
    title = page.locator("[data-sg=header-long] .header__title").bounding_box()
    action = page.locator("[data-sg=header-long] .header__action").bounding_box()
    row = page.locator("[data-sg=header-long] .header__row").bounding_box()
    short = page.locator("[data-sg=header-short] .header__action").bounding_box()
    assert title["height"] > 40
    assert action["x"] >= title["x"] + title["width"]
    assert action["y"] >= row["y"] - 0.5
    assert action["y"] + action["height"] <= row["y"] + row["height"] + 0.5
    assert abs(action["width"] - short["width"]) <= 0.5


def test_nav_labels_and_current(open_page):
    page = open_page("light")
    for name, labels, icons, current in [
        (
            "nav-owner",
            ["Today", "Orders", "Customers", "Products", "Production"],
            ["house", "list", "people", "hanger", "spool"],
            "Orders",
        ),
        ("nav-employee", ["My work", "My pay"], ["stopwatch", "wallet"], "My work"),
    ]:
        items = page.locator(f"[data-sg={name}] .nav__item")
        assert [t.strip() for t in items.all_inner_texts()] == labels
        for i, icon in enumerate(icons):
            assert items.nth(i).locator("svg.icon").get_attribute("data-icon") == icon
        marked = page.locator(f"[data-sg={name}] [aria-current=page]")
        assert marked.count() == 1
        assert marked.inner_text().strip() == current


def test_dark_changes_every_component(open_page):
    light, dark = open_page("light"), open_page("dark")
    # btn-accent is left out on purpose: ux.md keeps saffron the same in both themes.
    selectors = (
        ["body"]
        + [
            f"[data-sg={n}]"
            for n in ["btn-primary", "btn-tonal", "btn-ghost", "btn-disabled"]
        ]
        + [f"[data-sg={n}] .chip" for n in CHIPS]
        + [f"[data-sg={n}]" for n in ["card", "hero", "list"]]
        + [
            "[data-sg=header-sub] .header__back",
            "[data-sg=header-sub] .header__title",
            "[data-sg=header-sub] .header__action",
            "[data-sg=nav-owner] .nav",
            "[data-sg=nav-owner] .nav__item[aria-current=page]",
            "[data-sg=nav-owner] .nav__item:not([aria-current])",
            "[data-sg=action-bar]",
            "[data-sg=sheet]",
            "[data-sg=sheet] .sheet__handle",
            "[data-sg=icons] svg",
        ]
    )
    for selector in selectors:
        assert _styles(light, selector) != _styles(dark, selector), selector


@pytest.mark.parametrize("scheme", SCHEMES)
def test_screenshots(open_page, scheme):
    page = open_page(scheme)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    path = ARTIFACTS / f"styleguide-{scheme}.png"
    page.screenshot(path=str(path), full_page=True)
    assert path.exists()


def test_no_third_party_requests_and_font_loads(live_server, browser, settings):
    settings.DEBUG = True
    page = browser.new_page(viewport={"width": 390, "height": 844})
    urls = []
    page.on("request", lambda request: urls.append(request.url))
    page.goto(live_server.url + "/styleguide/")
    page.evaluate("document.fonts.ready.then(() => true)")
    assert all(u.startswith((live_server.url, "data:")) for u in urls)
    faces = page.evaluate(
        """document.fonts.ready.then(() =>
            [...document.fonts]
                .filter((f) => f.family.replace(/"/g, "") === "Plus Jakarta Sans")
                .map((f) => f.status))"""
    )
    assert faces and "loaded" in faces
    assert any(u.endswith(".woff2") for u in urls)
    page.close()
