from pathlib import Path

import pytest

from reports.models import ShopSettings

pytestmark = pytest.mark.e2e

ARTIFACTS = Path(__file__).resolve().parent.parent.parent / "artifacts" / "screens"


def test_running_costs_page(live_server, signed_in):
    _, page = signed_in("owner")
    page.goto(live_server.url + "/settings/running-costs/")
    page.get_by_label("Rent").fill("7000")
    page.get_by_label("Electricity").fill("1800")
    page.get_by_label("Thread, needles and buttons").fill("700")
    page.get_by_text("₹9,500 a month").wait_for()
    page.get_by_text("₹46 an hour").wait_for()
    page.get_by_role("button", name="+ Add a cost").click()
    assert page.locator("[data-cost-amount]").count() == 4
    page.get_by_label("Name of new cost 1").fill("Tea")
    page.get_by_label("Amount of new cost 1").fill("500")
    page.get_by_text("₹10,000 a month").wait_for()
    page.evaluate("document.fonts.ready.then(() => true)")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=ARTIFACTS / "S11-running-costs.png", full_page=True)
    page.get_by_role("button", name="Save", exact=True).click()
    page.get_by_text("Running costs saved").first.wait_for()
    saved = ShopSettings.current()
    assert saved.monthly_total() == 10000
    assert saved.running_rate() == 48
