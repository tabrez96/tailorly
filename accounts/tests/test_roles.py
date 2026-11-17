import pytest
from django.contrib.auth.models import Group, User

from accounts.roles import EMPLOYEE, OWNER, home_url, role_for


@pytest.fixture
def owner(db):
    user = User.objects.create_user("owner", password="x")
    user.groups.add(Group.objects.get_or_create(name="owner")[0])
    return user


@pytest.fixture
def employee(db):
    return User.objects.create_user("employee", password="x")


def test_role_for(owner, employee):
    assert role_for(owner) == OWNER
    assert role_for(employee) == EMPLOYEE


def test_home_url():
    assert home_url(OWNER) == "/"
    assert home_url(EMPLOYEE) == "/my-work/"


def test_owner_sent_home_from_employee_page(client, owner):
    client.force_login(owner)
    assert client.get("/my-work/")["Location"] == "/"


def test_employee_sent_home_from_owner_page(client, employee):
    client.force_login(employee)
    assert client.get("/")["Location"] == "/my-work/"
