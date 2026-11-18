import pytest
from django.contrib.auth.models import Group, User
from django.test import Client

from core import assets

pytestmark = pytest.mark.e2e

HOLD_FRAGMENT = (
    '<title>New order · Tailorly</title><div class="page" data-tab="orders" '
    'data-title="New order"><h1 tabindex="-1">New order</h1></div>'
)
ORDERS_FRAGMENT = HOLD_FRAGMENT.replace("New order", "Orders")


@pytest.fixture
def signed_in(live_server, browser, settings, db):
    settings.DEBUG = True
    contexts = []

    def _open(role):
        user = User.objects.create_user(role, password="x")
        if role == "owner":
            user.groups.add(Group.objects.get_or_create(name="owner")[0])
        client = Client()
        client.force_login(user)
        context = browser.new_context(viewport={"width": 390, "height": 844})
        contexts.append(context)
        context.add_cookies(
            [
                {
                    "name": "sessionid",
                    "value": client.cookies["sessionid"].value,
                    "url": live_server.url,
                }
            ]
        )
        return context, context.new_page()

    yield _open
    for context in contexts:
        context.close()


def _nav(page, label):
    return page.locator(".nav__item", has_text=label)


def test_tab_swaps_page_in_place(live_server, signed_in):
    _, page = signed_in("employee")
    page.goto(live_server.url + "/my-work/")
    page.evaluate("window.__marker = 1")
    _nav(page, "My pay").click()
    page.wait_for_url("**/my-pay/")
    page.wait_for_function("document.activeElement.tagName === 'H1'")
    assert page.evaluate("window.__marker") == 1
    assert page.evaluate("document.activeElement.textContent.trim()") == "My pay"
    assert _nav(page, "My pay").get_attribute("aria-current") == "page"
    assert _nav(page, "My work").get_attribute("aria-current") is None
    page.wait_for_function("document.getElementById('announce').textContent")
    assert page.inner_text("#announce") == "My pay"
    assert page.title().startswith("My pay")


def test_refresh_and_back_render_full_page(live_server, signed_in):
    _, page = signed_in("employee")
    page.goto(live_server.url + "/my-work/")
    _nav(page, "My pay").click()
    page.wait_for_url("**/my-pay/")
    page.reload()
    assert page.inner_text("h1") == "My pay"
    assert page.locator(".nav").count() == 1
    page.go_back()
    page.wait_for_url("**/my-work/")
    page.wait_for_selector("h1:has-text('My work')")
    assert page.locator(".nav").count() == 1
    page.wait_for_function("document.activeElement.tagName === 'H1'")
    assert page.locator(".nav [aria-current=page]").all_inner_texts() == ["My work"]
    page.goto(live_server.url + "/my-pay/")
    assert page.inner_text("h1") == "My pay"
    assert page.locator(".nav").count() == 1


def _open_sheet_by_keyboard(page, live_server):
    page.goto(live_server.url + "/styleguide/shell/")
    page.wait_for_function("window.htmx && window.Alpine?.store('shell')")
    opener = page.get_by_role("button", name="Open sample sheet")
    opener.focus()
    page.keyboard.press("Enter")
    page.wait_for_selector("dialog#sheet[open]")


def test_sheet_keyboard_escape_and_focus_return(live_server, signed_in):
    _, page = signed_in("owner")
    _open_sheet_by_keyboard(page, live_server)
    for _ in range(10):
        page.keyboard.press("Tab")
        assert page.evaluate(
            "document.getElementById('sheet').contains(document.activeElement)"
        )
    page.keyboard.press("Escape")
    page.wait_for_selector("dialog#sheet:not([open])", state="attached")
    assert (
        page.evaluate("document.activeElement.textContent.trim()")
        == "Open sample sheet"
    )


def test_sheet_422_focuses_first_error_and_save_closes(live_server, signed_in):
    _, page = signed_in("owner")
    page.goto(live_server.url + "/styleguide/shell/")
    page.get_by_role("button", name="Open sample sheet").click()
    page.wait_for_selector("dialog#sheet[open]")
    with page.expect_response("**/styleguide/sheet/") as info:
        page.get_by_role("button", name="Save").click()
    assert info.value.status == 422
    page.wait_for_function("document.activeElement.id === 'id_name'")
    assert page.get_attribute("#id_name", "aria-invalid") == "true"
    assert page.locator("#sheet .error-summary").is_visible()
    page.fill("#id_name", "Hem")
    page.get_by_role("button", name="Save").click()
    page.wait_for_selector("dialog#sheet:not([open])", state="attached")
    page.wait_for_selector(".toast:has-text('Saved')")


def test_hold_fires_shortcut_and_ring(live_server, signed_in):
    _, page = signed_in("owner")
    requests = []
    page.on("request", lambda r: requests.append(r.url))

    def slow_hold(route):
        # Still pending when the pointer is released.
        page.wait_for_timeout(500)
        route.fulfill(status=200, content_type="text/html", body=HOLD_FRAGMENT)

    page.route("**/orders/new/**", slow_hold)
    page.goto(live_server.url + "/")
    box = _nav(page, "Orders").bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.wait_for_timeout(600)
    orders = _nav(page, "Orders")
    assert "nav__item--held" in orders.get_attribute("class")
    shadow = orders.evaluate("el => getComputedStyle(el).boxShadow")
    assert "rgb(242, 184, 75)" in shadow and "3px" in shadow
    page.mouse.up()
    page.wait_for_url("**/orders/new/")
    assert not any(u.rstrip("/").endswith("/orders") for u in requests)


def test_short_tap_only_navigates(live_server, signed_in):
    _, page = signed_in("owner")
    requests = []
    page.on("request", lambda r: requests.append(r.url))
    page.route(
        "**/orders/",
        lambda route: route.fulfill(
            status=200, content_type="text/html", body=ORDERS_FRAGMENT
        ),
    )
    page.goto(live_server.url + "/")
    _nav(page, "Orders").click()
    page.wait_for_url("**/orders/")
    assert not any("/orders/new/" in u for u in requests)
    assert "nav__item--held" not in _nav(page, "Orders").get_attribute("class")


def test_expired_session_lands_on_sign_in(live_server, signed_in):
    context, page = signed_in("owner")
    page.goto(live_server.url + "/")
    context.clear_cookies()
    _nav(page, "Today").click()
    page.wait_for_url("**/sign-in/**")
    assert page.inner_text("h1") == "Tailorly"
    assert page.get_by_label("Phone number").is_visible()


def test_new_asset_version_reloads_once(live_server, signed_in, monkeypatch):
    _, page = signed_in("owner")
    page.goto(live_server.url + "/")
    page.evaluate("window.__marker = 1")
    navigations = []
    page.on(
        "framenavigated",
        lambda f: navigations.append(f.url) if f == page.main_frame else None,
    )
    monkeypatch.setattr(assets, "asset_version", lambda: "new")
    _nav(page, "Today").click()
    page.wait_for_load_state("load")
    page.wait_for_function("window.__marker === undefined")
    assert len(navigations) == 1
    assert page.inner_text("h1") == "Today"


def test_no_third_party_requests(live_server, signed_in):
    for role, path in [("owner", "/"), ("employee", "/my-work/")]:
        _, page = signed_in(role)
        urls = []
        page.on("request", lambda r, urls=urls: urls.append(r.url))
        page.goto(live_server.url + path)
        page.wait_for_load_state("networkidle")
        assert all(u.startswith((live_server.url, "data:")) for u in urls)
        assert any(u.endswith("htmx-4.0.1.min.js") for u in urls)
        assert any(u.endswith("alpine-3.15.12.min.js") for u in urls)
