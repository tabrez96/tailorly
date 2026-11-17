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
