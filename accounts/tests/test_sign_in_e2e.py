from pathlib import Path

import pytest
from django.contrib.auth.models import User

from accounts.roles import EMPLOYEE, OWNER, add_to_role

pytestmark = pytest.mark.e2e

PASSWORD = "correct-horse-staple-9"
SHOTS = Path("artifacts/screens")


@pytest.fixture
def page_for(live_server, browser, settings, db):
    settings.DEBUG = True
    SHOTS.mkdir(parents=True, exist_ok=True)
    contexts = []

    def _open(scheme="light"):
        context = browser.new_context(
            viewport={"width": 390, "height": 844}, color_scheme=scheme
        )
        contexts.append(context)
        page = context.new_page()
        page.goto(live_server.url + "/sign-in/")
        return page

    yield _open
    for context in contexts:
        context.close()


def _fill(page, phone, password):
    page.fill("input[name=username]", phone)
    page.fill("input[name=password]", password)
    page.click("button[type=submit]")


def test_wrong_credentials_then_owner(page_for, live_server):
    owner = User.objects.create_user("9845012345", password=PASSWORD)
    add_to_role(owner, OWNER)
    page = page_for()
    page.screenshot(path=str(SHOTS / "S01-sign-in.png"))
    _fill(page, "98450 12345", "wrong")
    page.wait_for_selector("[role=alert]")
    assert page.input_value("input[name=username]") == "98450 12345"
    page.screenshot(path=str(SHOTS / "S01-sign-in-error.png"))
    _fill(page, "98450 12345", PASSWORD)
    page.wait_for_url(live_server.url + "/")
    assert page.locator(".nav__item", has_text="Today").is_visible()


def test_employee_lands_on_my_work(page_for, live_server):
    employee = User.objects.create_user("9000011111", password=PASSWORD)
    add_to_role(employee, EMPLOYEE)
    page = page_for()
    _fill(page, "9000011111", PASSWORD)
    page.wait_for_url("**/my-work/")
    assert page.locator(".nav__item", has_text="My pay").is_visible()


def test_button_shows_signing_in_while_submitting(page_for):
    page = page_for()
    page.route(
        "**/sign-in/",
        lambda route: None if route.request.method == "POST" else route.continue_(),
    )
    page.fill("input[name=username]", "9845012345")
    page.fill("input[name=password]", "wrong")
    page.click("button[type=submit]", no_wait_after=True)
    button = page.locator("button[type=submit]")
    assert button.inner_text() == "Signing in..."
    assert button.is_disabled()


def test_dark(page_for):
    page = page_for("dark")
    page.screenshot(path=str(SHOTS / "S01-sign-in-dark.png"))
    _fill(page, "9845012345", "wrong")
    page.wait_for_selector("[role=alert]")
