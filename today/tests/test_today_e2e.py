import re

import pytest
from django.contrib.auth.models import User
from django.test import Client
from playwright.sync_api import expect

from production import timing
from production.tests.test_production_e2e import SHOTS, seed

pytestmark = pytest.mark.e2e


@pytest.fixture(autouse=True)
def _shots():
    SHOTS.mkdir(parents=True, exist_ok=True)


@pytest.fixture
def not_stale(monkeypatch):
    """Keep the open session running when the test runs just after local midnight."""
    monkeypatch.setattr(timing, "_stale_cutoff", lambda session, now: None)


def test_today_main(signed_in, live_server, not_stale):
    context, page = signed_in("owner")
    seed(session="open")
    page.goto(live_server.url + "/")
    hero = page.locator("#today-hero")
    expect(hero.get_by_text("Working", exact=True)).to_be_visible()
    expect(hero.locator("[x-text='text']")).to_have_text("1h 12m")
    expect(page.locator(".nav [aria-current]")).to_contain_text("Today")
    page.screenshot(path=str(SHOTS / "S02-today.png"), full_page=True)


def test_today_dark(signed_in, live_server, browser, not_stale):
    context, page = signed_in("owner")
    seed(session="open")
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
    page.goto(live_server.url + "/")
    expect(page.get_by_text("Working", exact=True)).to_be_visible()
    page.screenshot(path=str(SHOTS / "S02-today-dark.png"), full_page=True)
    dark.close()


def test_today_opens_in_place(signed_in, live_server, not_stale):
    context, page = signed_in("owner")
    seed(session="open")
    page.goto(live_server.url + "/")
    page.evaluate("window.__marker = 1")
    page.locator("#money-collect").click()
    expect(page.get_by_role("heading", name="Orders")).to_be_visible()
    assert page.url.endswith("/orders/?show=owing")
    assert page.evaluate("window.__marker") == 1
    page.go_back()
    page.locator("#today-plan").click()
    expect(page.get_by_role("heading", name="Work plan")).to_be_visible()
    assert page.evaluate("window.__marker") == 1


def test_hero_polls_and_ticks(signed_in, live_server, not_stale):
    context, page = signed_in("owner")
    seed(session="open")
    page.clock.install()
    polls = []
    page.on("request", lambda r: "/today/hero/" in r.url and polls.append(r.url))
    page.goto(live_server.url + "/")
    timer = page.locator("#today-hero [x-text='text']")
    expect(timer).to_have_text("1h 12m")
    page.clock.run_for(31_000)
    page.wait_for_timeout(300)
    assert len(polls) >= 1
    # Swaps would reset the timer offset from the real server time; block them.
    page.route("**/today/hero/", lambda route: route.abort())
    page.clock.run_for(60_000)
    expect(timer).not_to_have_text("1h 12m")
    page.locator(".nav").get_by_text("Orders").click()
    page.clock.run_for(1_000)
    expect(page.get_by_role("heading", name="Orders")).to_be_visible()
    page.wait_for_timeout(300)
    seen = len(polls)
    page.clock.run_for(61_000)
    page.wait_for_timeout(300)
    assert len(polls) == seen


def test_end_day_from_hero(signed_in, live_server, not_stale):
    context, page = signed_in("owner")
    seed(session="open")
    page.goto(live_server.url + "/")
    page.evaluate("window.__marker = 1")
    page.get_by_role("button", name="End Ali's day").click()
    expect(page.locator("#today-hero").get_by_text("Gone home")).to_be_visible()
    assert page.evaluate("window.__marker") == 1


def test_today_first_run(signed_in, live_server):
    context, page = signed_in("owner")
    page.goto(live_server.url + "/")
    expect(page.get_by_text("Welcome to Tailorly")).to_be_visible()
    page.screenshot(path=str(SHOTS / "S02-today-first-run.png"))
    page.evaluate("window.__marker = 1")
    page.locator("#setup-2 a").click()
    expect(page).to_have_url(re.compile(r"/customers/\?add=1"))
    expect(page.locator(".nav")).to_be_visible()
    assert page.evaluate("window.__marker") == 1  # no full reload


def test_today_hold_tip(signed_in, live_server, not_stale):
    context, page = signed_in("owner", hold_tip_seen=False)
    seed(session="open")
    page.goto(live_server.url + "/")
    expect(page.locator(".hold-tip__card")).to_be_visible()
    page.screenshot(path=str(SHOTS / "S02-today-hold-tip.png"))
    page.get_by_role("button", name="Got it").click()
    expect(page.locator("#hold-tip")).to_have_count(0)
    page.reload()
    expect(page.locator("#hold-tip")).to_have_count(0)
