import pytest
from django.contrib.auth.models import User
from django.test import Client

from accounts.roles import OWNER, add_to_role
from production.tests.conftest import (  # noqa: F401
    ali,
    blouse,
    customer,
    make_item,
    started_day,
)


@pytest.fixture
def owner(db):
    user = User.objects.create_user("owner", password="x", first_name="Sabreen")
    add_to_role(user, OWNER)
    client = Client()
    client.force_login(user)
    return client
