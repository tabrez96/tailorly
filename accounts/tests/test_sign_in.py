import pytest
from django.contrib.auth.models import User

from accounts.forms import SIGN_IN_ERROR
from accounts.roles import EMPLOYEE, OWNER, add_to_role

PASSWORD = "correct-horse-staple-9"


@pytest.fixture
def owner(db):
    user = User.objects.create_user("9845012345", password=PASSWORD)
    add_to_role(user, OWNER)
    return user


@pytest.fixture
def employee(db):
    user = User.objects.create_user("9000011111", password=PASSWORD)
    add_to_role(user, EMPLOYEE)
    return user


def test_page_renders(client, db):
    html = client.get("/sign-in/").content.decode()
    assert "Phone number" in html
    assert "Orders, measurements and pay for your shop." in html
    assert "Forgot your password? The shop owner can reset it in Staff." in html
    assert "bottom-nav" not in html and 'id="page"' not in html
    assert 'role="alert"' not in html


def test_owner_lands_on_today(client, owner):
    response = client.post(
        "/sign-in/", {"username": "98450 12345", "password": PASSWORD}
    )
    assert response.status_code == 302 and response["Location"] == "/"
    assert "Today" in client.get("/").content.decode()


def test_employee_lands_on_my_work(client, employee):
    response = client.post(
        "/sign-in/", {"username": "9000011111", "password": PASSWORD}
    )
    assert response.status_code == 302 and response["Location"] == "/my-work/"
    assert "My pay" in client.get("/my-work/").content.decode()


def test_wrong_password_error(client, owner):
    response = client.post("/sign-in/", {"username": "98450 12345", "password": "no"})
    html = response.content.decode()
    assert response.status_code == 422
    assert 'role="alert"' in html
    assert SIGN_IN_ERROR.replace("'", "&#x27;") in html or SIGN_IN_ERROR in html
    assert 'value="98450 12345"' in html
    assert html.count('aria-invalid="true"') == 2
    password_input = html.split('name="password"')[1].split(">")[0]
    assert "value=" not in password_input


def test_unknown_phone_shows_same_error(client, owner):
    response = client.post("/sign-in/", {"username": "1112223334", "password": "x"})
    assert response.status_code == 422
    assert "Check both and try again." in response.content.decode()


def test_inactive_user_shows_same_error(client, owner):
    owner.is_active = False
    owner.save()
    response = client.post(
        "/sign-in/", {"username": "9845012345", "password": PASSWORD}
    )
    assert response.status_code == 422
    assert "Check both and try again." in response.content.decode()


def test_empty_submit_shows_alert(client, db):
    response = client.post("/sign-in/", {})
    html = response.content.decode()
    assert response.status_code == 422
    assert 'role="alert"' in html
    assert "Check both and try again." in html


def test_signed_in_user_redirected_from_sign_in(client, owner):
    client.force_login(owner)
    response = client.get("/sign-in/")
    assert response.status_code == 302 and response["Location"] == "/"


def test_next_is_honoured(client, owner):
    response = client.post(
        "/sign-in/?next=/styleguide/",
        {"username": "9845012345", "password": PASSWORD, "next": "/styleguide/"},
    )
    assert response["Location"] == "/styleguide/"


def test_sign_out(client, owner):
    client.force_login(owner)
    response = client.post("/sign-out/")
    assert response.status_code == 302 and response["Location"] == "/sign-in/"
    assert client.get("/").status_code == 302
