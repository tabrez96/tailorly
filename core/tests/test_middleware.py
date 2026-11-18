import pytest
from django.contrib.auth.models import Group, User

from core import assets


@pytest.fixture
def owner(client, db):
    user = User.objects.create_user("owner", password="x")
    user.groups.add(Group.objects.get_or_create(name="owner")[0])
    client.force_login(user)


def test_stale_asset_version_refreshes(client, owner):
    response = client.get("/", headers={"HX-Request": "true", "X-Asset-Version": "old"})
    assert response["HX-Refresh"] == "true"


def test_current_version_passes(client, owner):
    response = client.get(
        "/",
        headers={
            "HX-Request": "true",
            "HX-Request-Type": "partial",
            "X-Asset-Version": assets.asset_version(),
        },
    )
    assert response.status_code == 200
    assert "HX-Refresh" not in response
    assert "<nav" not in response.content.decode()


def test_no_header_no_refresh(client, owner):
    assert "HX-Refresh" not in client.get("/", headers={"HX-Request": "true"})


def test_expired_session_htmx_redirects(client, db):
    response = client.get("/", headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert response["HX-Redirect"].startswith("/sign-in/")


def test_expired_session_full_load(client, db):
    response = client.get("/")
    assert response.status_code == 302
    assert response["Location"] == "/sign-in/?next=/"


def test_wrong_role_htmx_gets_hx_redirect_home(client, db):
    client.force_login(User.objects.create_user("e", password="x"))
    response = client.get("/", headers={"HX-Request": "true"})
    assert response.status_code == 403
    assert response["HX-Redirect"] == "/my-work/"


def test_expired_session_history_restore_redirects(client, db):
    response = client.get("/", headers={"HX-History-Restore-Request": "true"})
    assert response["HX-Redirect"].startswith("/sign-in/")
