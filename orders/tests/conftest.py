from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from accounts.roles import OWNER, add_to_role
from catalog.models import Product, ProductOption
from customers.models import Customer
from staff.models import Employee


@pytest.fixture
def owner_client(client, db):
    user = User.objects.create_user("owner", password="x")
    add_to_role(user, OWNER)
    client.force_login(user)
    return client


@pytest.fixture
def customer(db):
    return Customer.objects.create(name="Asha Rao", phone="9000000011")


@pytest.fixture
def lining(db):
    return Product.objects.create(
        name="Lining, cotton",
        kind=Product.SECONDARY,
        unit="m",
        cost_price=Decimal("60"),
        selling_price=Decimal("90"),
        billed_by_default=True,
    )


@pytest.fixture
def blouse(lining):
    product = Product.objects.create(
        name="Blouse",
        kind=Product.PRIMARY,
        type=Product.CUSTOM,
        usual_price=Decimal("1200"),
        measurement_fields=["Bust", "Waist"],
    )
    ProductOption.objects.create(product=product, name="Lining", material=lining)
    return product


@pytest.fixture
def kurta(db):
    return Product.objects.create(
        name="Cotton kurta",
        kind=Product.PRIMARY,
        type=Product.READY_MADE,
        usual_price=Decimal("799"),
    )


def make_employee(phone, username):
    user = User.objects.create_user(username, password="x")
    return user, Employee.objects.create(user=user, name=username, phone=phone)


@pytest.fixture
def employee_user(db):
    return make_employee("9000000001", "ravi")


@pytest.fixture
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path
