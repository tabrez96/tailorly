import pytest
from django.contrib.auth import authenticate
from django.contrib.auth.models import User

from accounts.roles import OWNER, add_to_role

OLD, NEW = "old-pass-phrase-1", "new-pass-phrase-2"


@pytest.fixture
def signed_in(client, db):
    user = User.objects.create_user("9845012345", password=OLD)
    add_to_role(user, OWNER)
    client.force_login(user)
    return user


def post(client, **data):
    body = {"old_password": OLD, "new_password1": NEW, "new_password2": NEW} | data
    return client.post("/account/password/", body)


def test_valid_change_keeps_session(client, signed_in):
    response = post(client)
    assert response.status_code == 200
    assert "Password changed." in response.content.decode()
    assert client.get("/").status_code == 200
    assert authenticate(username="9845012345", password=NEW) is not None


def test_wrong_current_password(client, signed_in):
    response = post(client, old_password="nope")
    assert response.status_code == 422
    assert 'role="alert"' in response.content.decode()
    assert authenticate(username="9845012345", password=OLD) is not None


def test_anonymous_redirected(client, db):
    response = client.get("/account/password/")
    assert response.status_code == 302 and "/sign-in/" in response["Location"]


def test_partial_returns_fragment(client, signed_in):
    response = client.get("/account/password/", headers={"HX-Request-Type": "partial"})
    html = response.content.decode()
    assert response.status_code == 200 and "<html" not in html
    assert "Current password" in html
