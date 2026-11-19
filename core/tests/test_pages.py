import json
import re

import pytest
from django.contrib.auth.models import Group, User
from django.http import HttpResponse
from django.test import RequestFactory

from core import assets
from core.pages import is_partial, render_page, sheet_saved, sheet_saved_location


@pytest.fixture
def owner(client, db):
    user = User.objects.create_user("owner", password="x")
    user.groups.add(Group.objects.get_or_create(name="owner")[0])
    client.force_login(user)
    return user


def test_is_partial():
    assert is_partial({"HX-Request-Type": "partial"})
    assert not is_partial({"HX-Request-Type": "full"})
    assert not is_partial({})


def test_render_page_partial(client, owner):
    response = client.get("/", headers={"HX-Request-Type": "partial"})
    html = response.content.decode()
    assert "<title>Today · Tailorly</title>" in html
    assert 'data-tab="today"' in html
    assert "<nav" not in html and "<html" not in html
    assert "HX-Request-Type" in response["Vary"]


def test_render_page_full(client, owner):
    html = client.get("/").content.decode()
    for part in [
        "<html",
        'id="page"',
        '<dialog id="sheet"',
        'id="announce"',
        "/static/vendor/htmx-4.0.1.min.js",
        "X-Asset-Version",
        assets.asset_version(),
    ]:
        assert part in html
    assert re.search(r"<body [^>]*hx-headers:inherited=", html)
    today = html.split('href="/"')[1].split(">")[0]
    assert 'aria-current="page"' in today


def test_render_page_status(owner):
    request = RequestFactory().get("/")
    request.user = owner
    response = render_page(request, "today/today.html", {"title": "Today"}, status=422)
    assert response.status_code == 422


def test_sheet_saved():
    response = sheet_saved(HttpResponse(""), "Saved")
    trigger = json.loads(response["HX-Trigger"])
    assert trigger["sheet:close"] is True
    assert trigger["toast"]["message"] == "Saved"
    assert response["HX-Reswap"] == "none"


def test_sheet_saved_location_without_toast():
    response = sheet_saved_location("/x/")
    trigger = json.loads(response["HX-Trigger"])
    assert trigger == {"sheet:close": True}
    assert json.loads(response["HX-Location"])["path"] == "/x/"
