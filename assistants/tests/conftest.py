import pytest
from django.contrib.auth.models import User
from django.test import Client

from accounts.roles import OWNER, add_to_role
from customers.models import Customer
from orders.models import Order


@pytest.fixture
def owner(db):
    user = User.objects.create_user("owner", password="x")
    add_to_role(user, OWNER)
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def ali(db):
    user = User.objects.create_user("9000011117", password="x")
    client = Client()
    client.force_login(user)
    user.client = client
    return user


@pytest.fixture
def order_factory(db):
    customer = Customer.objects.create(name="Asha Rao", phone="9000000011")
    return lambda: Order.objects.create(customer=customer, number=1, status="open")
