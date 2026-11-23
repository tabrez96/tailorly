import pytest
from django.contrib.auth.models import User

from accounts.roles import OWNER, add_to_role


@pytest.fixture
def owner_client(client, db):
    user = User.objects.create_user("owner", password="x")
    add_to_role(user, OWNER)
    client.force_login(user)
    return client
