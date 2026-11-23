import json
from decimal import Decimal as D

import pytest
from django.contrib.auth.models import User

from reports import running_costs as rc
from reports.models import ShopSettings

URL = "/settings/running-costs/"
HX = {"HTTP_HX_REQUEST": "true"}


def post_data(**extra):
    data = {
        "cost_name": ["Rent", "Electricity", "Thread, needles and buttons"],
        "cost_amount": ["7000", "1800", "700"],
        "cost_fixed": ["1", "1", "1"],
        "hours": "208",
    }
    return {**data, **extra}


def test_rows_for_defaults_then_saved_lines():
    rows = rc.rows_for(
        [{"name": "Rent", "amount": "7000"}, {"name": "Tea", "amount": "250.50"}]
    )
    assert [(r.name, r.amount) for r in rows] == [
        ("Rent", "7000"),
        ("Electricity", ""),
        ("Thread, needles and buttons", ""),
        ("Tea", "250.5"),
    ]
    assert all(r.fixed for r in rows)


def test_parse_drops_blank_amounts_and_flags_missing_name():
    lines, rows = rc.parse(
        ["Rent", "Tea", "", "Gas", "Oil", "Misc"],
        ["₹7,000", "", "300", "abc", "-5", "1.234"],
        ["1", "0", "0", "0", "0", "0"],
    )
    assert lines == [{"name": "Rent", "amount": "7000"}]
    assert [r.error for r in rows] == [
        "",
        "",
        rc.NAME_ERROR,
        rc.AMOUNT_ERROR,
        rc.AMOUNT_ERROR,
        rc.AMOUNT_ERROR,
    ]
    assert rows[0].fixed and not rows[1].fixed
    assert [r.name_error for r in rows] == [False, False, True, False, False, False]


def test_parse_cuts_long_names():
    lines, _ = rc.parse(["x" * 90], ["10"], ["0"])
    assert len(lines[0]["name"]) == rc.NAME_MAX


def test_parse_hours():
    assert rc.parse_hours("208") == (208, "")
    assert rc.parse_hours(" 1 ") == (1, "")
    for bad in ("", "0", "745", "abc", "2.5", "-3"):
        assert rc.parse_hours(bad) == (None, rc.HOURS_ERROR)


@pytest.mark.django_db
def test_owner_saves_lines_and_hours(owner_client):
    response = owner_client.post(URL, post_data())
    assert response.status_code == 303
    saved = ShopSettings.current()
    assert saved.working_hours == 208
    assert saved.monthly_total() == D(9500)
    assert saved.running_rate() == D(46)
    body = owner_client.get(URL).content.decode()
    assert "₹9,500 a month" in body and "₹46 an hour" in body
    assert 'value="7000"' in body


@pytest.mark.django_db
def test_page_save_over_htmx_loads_page(owner_client):
    response = owner_client.post(URL, post_data(), **HX)
    assert json.loads(response["HX-Location"])["path"] == URL
    assert "Running costs saved" in response["HX-Trigger"]


@pytest.mark.django_db
def test_sheet_mode_save_closes_sheet(owner_client):
    response = owner_client.post(URL + "?sheet=1", post_data(), **HX)
    assert "sheet:close" in response["HX-Trigger"]
    assert ShopSettings.current().working_hours == 208


@pytest.mark.django_db
def test_sheet_renders_without_page_header(owner_client):
    body = owner_client.get(URL + "?sheet=1", **HX).content.decode()
    assert 'hx-target="#sheet"' in body and "Running costs" in body


@pytest.mark.django_db
def test_invalid_post_is_422_with_errors(owner_client):
    data = post_data(cost_amount=["7000", "abc", ""], hours="0")
    response = owner_client.post(URL, data)
    body = response.content.decode()
    assert response.status_code == 422
    assert rc.AMOUNT_ERROR in body and rc.HOURS_ERROR in body
    assert "2 things need fixing before you can save running costs." in body
    assert not ShopSettings.objects.exists()


@pytest.mark.django_db
def test_invalid_post_redisplays_new_rows(owner_client):
    data = post_data(
        cost_name=["Rent", "Tea"],
        cost_amount=["7000", "x"],
        cost_fixed=["1", "0"],
    )
    body = owner_client.post(URL, data).content.decode()
    assert 'value="Tea"' in body


@pytest.mark.django_db
def test_defaults_when_nothing_saved(owner_client):
    body = owner_client.get(URL).content.decode()
    assert "Not set" in body and 'value="208"' in body
    assert not ShopSettings.objects.exists()


@pytest.mark.django_db
def test_employee_cannot_open_running_costs(client):
    user = User.objects.create_user("emp", password="x")
    client.force_login(user)
    assert client.get(URL).status_code != 200
    assert client.post(URL, post_data()).status_code != 200
    assert not ShopSettings.objects.exists()


def test_duplicate_names_round_trip_without_losing_amounts():
    saved = [{"name": "Rent", "amount": "7000"}, {"name": "Rent", "amount": "500"}]
    rows = rc.rows_for(saved)
    assert [(r.name, r.amount) for r in rows[:2]] == [
        ("Rent", "7000"),
        ("Electricity", ""),
    ]
    assert [(r.name, r.amount) for r in rows if r.name == "Rent"] == [
        ("Rent", "7000"),
        ("Rent", "500"),
    ]
    lines, _ = rc.parse(
        [r.name for r in rows], [r.amount for r in rows], ["1"] * len(rows)
    )
    assert sum(D(line["amount"]) for line in lines) == D("7500")
