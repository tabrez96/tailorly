import pytest
from django.contrib.auth.models import User

from accounts.roles import OWNER, add_to_role
from customers.models import Customer

PARTIAL = {"HX-Request": "true", "HX-Request-Type": "partial"}


@pytest.fixture
def owner_client(client, db):
    user = User.objects.create_user("owner", password="x")
    add_to_role(user, OWNER)
    client.force_login(user)
    return client


@pytest.fixture
def meera(db):
    return Customer.objects.create(
        name="Meera Iyer", phone="9845022110", notes="Prefers loose sleeves.\nSundays."
    )
