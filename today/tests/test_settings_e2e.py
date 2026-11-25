import pytest
from django.contrib.auth.models import User
from django.test import Client
from playwright.sync_api import expect

from production.tests.test_production_e2e import SHOTS, seed

pytestmark = pytest.mark.e2e


@pytest.fixture(autouse=True)
def _shots():
    SHOTS.mkdir(parents=True, exist_ok=True)


def test_settings_main(signed_in, live_server):
    context, page = signed_in("owner")
    seed()
    page.goto(live_server.url + "/settings/")
    expect(page.get_by_role("heading", name="Settings")).to_be_visible()
    expect(page.locator("#settings-staff")).to_contain_text("Ali Khan")
    page.screenshot(path=str(SHOTS / "S18-settings.png"), full_page=True)


def test_settings_dark(signed_in, live_server, browser):
    context, page = signed_in("owner")
    seed()
    client = Client()
    client.force_login(User.objects.get(username="owner"))
    dark = browser.new_context(
        viewport={"width": 390, "height": 844}, color_scheme="dark"
    )
    dark.add_cookies(
        [
            {
                "name": "sessionid",
                "value": client.cookies["sessionid"].value,
                "url": live_server.url,
            }
        ]
    )
    page = dark.new_page()
    page.goto(live_server.url + "/settings/")
    expect(page.get_by_role("heading", name="Settings")).to_be_visible()
    page.screenshot(path=str(SHOTS / "S18-settings-dark.png"), full_page=True)
    dark.close()


def test_gear_opens_settings_in_place(signed_in, live_server):
    context, page = signed_in("owner")
    seed()
    page.goto(live_server.url + "/")
    page.evaluate("window.__marker = 1")
    page.locator('[aria-label="Settings"]').click()
    expect(page.get_by_role("heading", name="Settings")).to_be_visible()
    assert page.url.endswith("/settings/")
    assert page.evaluate("window.__marker") == 1
    page.locator("#settings-production").click()
    expect(page.get_by_role("heading", name="Production")).to_be_visible()
    page.locator('[aria-label="Back"]').click()
    expect(page.get_by_role("heading", name="Settings")).to_be_visible()
    assert page.url.endswith("/settings/")
    assert page.evaluate("window.__marker") == 1
