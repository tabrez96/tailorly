from pathlib import Path

import pytest

from assistants.models import AccessKey
from reports.models import ShopSettings

pytestmark = pytest.mark.e2e

ARTIFACTS = Path(__file__).resolve().parent.parent.parent / "artifacts" / "screens"
SAVE_ERROR = "Couldn't save. Check your connection and try again."


def shot(page, name, **kwargs):
    page.evaluate("document.fonts.ready.then(() => true)")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=ARTIFACTS / name, **kwargs)


def make_key(page, name):
    page.locator("#new-key").click()
    page.get_by_label("Name").fill(name)
    page.get_by_role("button", name="Make key").click()
    page.get_by_text("Your new key").wait_for()


def test_assistants_flow(live_server, signed_in):
    context, page = signed_in("owner")
    page.goto(live_server.url + "/settings/assistants/")
    page.get_by_text("No assistant connected").wait_for()
    shot(page, "S21-off.png", full_page=True)
    page.locator("#mcp-turn-on").click()
    page.get_by_text("Server address").wait_for()

    make_key(page, "Claude on phone")
    page.get_by_role("button", name="Done").click()
    make_key(page, "Claude on tablet")
    shot(page, "S21-new-key.png")
    page.get_by_role("button", name="Done").click()
    page.get_by_text("On · 2 apps connected").wait_for()
    assert AccessKey.active().count() == 2
    shot(page, "S21-main.png", full_page=True)

    # Read and change asks first; cancelling leaves Only read.
    page.once("dialog", lambda d: d.dismiss())
    page.get_by_text("Read and change", exact=True).click()
    assert page.locator("#mcp-mode-read").is_checked()
    assert not ShopSettings.current().mcp_can_change
    page.once("dialog", lambda d: d.accept())
    with page.expect_response(
        lambda r: r.url.endswith("/settings/assistants/set/") and r.ok
    ):
        page.get_by_text("Read and change", exact=True).click()
    # The saved panel replaces the old one; wait for the swap to land.
    page.wait_for_function(
        "document.getElementById('mcp-mode-change').checked && "
        "document.querySelector('#mcp-mode_error').textContent.trim() === ''"
    )
    assert ShopSettings.current().mcp_can_change

    # A failed save puts the switch back and says so.
    page.route("**/settings/assistants/set/", lambda r: r.abort())
    page.locator("#mcp-staff").click()
    page.get_by_text(SAVE_ERROR).wait_for()
    assert not page.locator("#mcp-staff").is_checked()
    assert page.locator("#mcp-staff_error[role=alert]").is_visible()
    page.unroute("**/settings/assistants/set/")

    # Revoke asks first.
    page.once("dialog", lambda d: d.accept())
    page.locator(f"#revoke-{AccessKey.active().first().pk}").click()
    page.get_by_text("On · 1 app connected").wait_for()

    dark = context.browser.new_context(
        viewport={"width": 390, "height": 844}, color_scheme="dark"
    )
    dark.add_cookies(context.cookies())
    dark_page = dark.new_page()
    dark_page.goto(live_server.url + "/settings/assistants/")
    shot(dark_page, "S21-dark.png", full_page=True)
    dark.close()
