from pathlib import Path

import pytest
from django.contrib.auth.models import User
from playwright.sync_api import expect

from staff.models import Employee

pytestmark = pytest.mark.e2e

SHOTS = Path("artifacts/screens")


@pytest.fixture(autouse=True)
def _shots():
    SHOTS.mkdir(parents=True, exist_ok=True)


def _employee(db):
    return Employee.objects.create(name="Ali Khan", phone="9000011119", daily_wage=800)


def test_employee_starts_and_ends_day_in_place(signed_in, live_server):
    context, page = signed_in("employee")
    user = User.objects.get(username="employee")
    Employee.objects.create(name="Ali Khan", phone="9000011120", user=user)
    page.goto(live_server.url + "/my-work/")
    page.evaluate("window.__marker = 1")
    page.screenshot(path=str(SHOTS / "S08-not-started.png"))
    page.get_by_role("button", name="Start my day").click()
    page.get_by_text("Day started").wait_for()
    page.get_by_role("button", name="End my day").click()
    page.get_by_text("Day ended at").wait_for()
    assert page.evaluate("window.__marker") == 1


def test_owner_fixes_day_in_sheet(signed_in, live_server, db):
    _employee(db)
    context, page = signed_in("owner")
    page.goto(live_server.url + "/settings/staff/?week=2026-11-09")
    page.evaluate("window.__marker = 1")
    assert not page.locator(".nav").is_visible()
    page.get_by_role("button", name="Add Mon 9").click()
    page.fill("input[name=start]", "09:00")
    page.fill("input[name=end]", "17:30")
    page.get_by_role("button", name="Save").click()
    page.get_by_text("edited by owner").wait_for()
    assert page.get_by_text("9:00 am – 5:30 pm").is_visible()
    assert page.evaluate("window.__marker") == 1
    page.screenshot(path=str(SHOTS / "S10-staff.png"))


def test_owner_edit_employee_form(signed_in, live_server, db):
    # Reset password only shows for an employee who already has a login
    employee = _employee(db)
    employee.user = User.objects.create_user("9000011119", password="secret123")
    employee.save()
    context, page = signed_in("owner")
    page.goto(live_server.url + "/settings/staff/")
    page.evaluate("window.__marker = 1")
    page.get_by_role("link", name="Edit").click()
    page.get_by_role("button", name="Reset password").wait_for()
    assert not page.locator(".nav").is_visible()
    page.screenshot(path=str(SHOTS / "S10-edit-employee.png"))
    # Alpine may still be starting on the swapped form: retry until the field shows
    password = page.locator("input[name=password]")
    expect(password).to_be_hidden()
    # The button hides itself once the click works, so wait on the field, not the button
    for attempt in range(5):
        page.get_by_role("button", name="Reset password").click()
        try:
            expect(password).to_be_visible(timeout=1000)
            break
        except AssertionError:
            if attempt == 4:
                raise
    assert page.evaluate("window.__marker") == 1


def _seed_week(employee):
    from datetime import date, datetime
    from zoneinfo import ZoneInfo

    from staff.models import DayRecord

    tz = ZoneInfo("Asia/Kolkata")
    for day, end in ((9, 19), (10, 17), (11, 17)):
        DayRecord.objects.create(
            employee=employee,
            date=date(2026, 11, day),
            start=datetime(2026, 11, day, 9, 0, tzinfo=tz),
            end=datetime(2026, 11, day, end, 0, tzinfo=tz),
        )


def test_owner_records_payout(signed_in, live_server, db):
    _seed_week(_employee(db))
    context, page = signed_in("owner")
    page.goto(live_server.url + "/settings/staff/?week=2026-11-09")
    page.evaluate("window.__marker = 1")
    page.screenshot(path=str(SHOTS / "S10-staff.png"), full_page=True)
    page.get_by_role("button", name="Record payout").click()
    page.get_by_role("button", name="Save payout").wait_for()
    page.screenshot(path=str(SHOTS / "S10-record-payout.png"))
    page.get_by_role("button", name="Save payout").click()
    page.locator("#staff-total").get_by_text("Paid ").wait_for()
    assert not page.get_by_role("button", name="Save payout").is_visible()
    assert page.evaluate("window.__marker") == 1


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_employee_my_pay(signed_in, live_server, scheme):
    context, page = signed_in("employee")
    user = User.objects.get(username="employee")
    employee = Employee.objects.create(
        name="Ali Khan", phone="9000011121", daily_wage=800, user=user
    )
    _seed_week(employee)
    page.emulate_media(color_scheme=scheme)
    page.goto(live_server.url + "/my-pay/")
    expect(page.get_by_text("This week so far")).to_be_visible()
    name = "S09-dark.png" if scheme == "dark" else "S09-my-pay.png"
    page.screenshot(path=str(SHOTS / name), full_page=True)
