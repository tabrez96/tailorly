from datetime import date, datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

from catalog.models import Product
from customers.models import Customer
from orders.models import Order, OrderItem
from staff.models import DayRecord, Employee

PARTIAL = {"HX-Request": "true", "HX-Request-Type": "partial"}


@pytest.fixture
def ali(db):
    user = User.objects.create_user("9000011117", password="x", first_name="Ali Khan")
    employee = Employee.objects.create(
        name="Ali Khan", phone="9000011117", daily_wage=800, user=user
    )
    client = Client()
    client.force_login(user)
    employee.client = client
    return employee


@pytest.fixture
def customer(db):
    return Customer.objects.create(name="Meera Iyer", phone="9000000011")


@pytest.fixture
def blouse(db):
    return Product.objects.create(
        name="Blouse",
        kind=Product.PRIMARY,
        type=Product.CUSTOM,
        usual_price=Decimal("1450"),
    )


@pytest.fixture
def make_item(customer, blouse):
    def _make(
        employee,
        due=None,
        name="Blouse",
        price="1450",
        estimate=None,
        status="open",
        kind="custom",
    ):
        number = (Order.objects.order_by("-number").first() or Order(number=0)).number
        order = Order.objects.create(
            customer=customer,
            number=number + 1,
            status=status,
            due_date=due,
            assignee=employee,
        )
        return OrderItem.objects.create(
            order=order,
            product=blouse,
            name=name,
            type=kind,
            price=Decimal(price),
            usual_price=Decimal(price),
            estimate_minutes=estimate,
        )

    return _make


@pytest.fixture
def started_day(db):
    def _start(employee, day: date | None = None, end=None):
        day = day or timezone.localdate()
        start = timezone.make_aware(datetime(day.year, day.month, day.day, 9, 0))
        return DayRecord.objects.create(
            employee=employee,
            date=timezone.localdate(start),
            start=start,
            end=end,
        )

    return _start


@pytest.fixture
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def jpeg_upload(name="p.jpg"):
    from io import BytesIO

    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (40, 30), "tan").save(buffer, "JPEG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


@pytest.fixture
def add_photos(media):
    from orders.photos import add_photo

    def _add(item, count=3):
        return [add_photo(item, jpeg_upload()) for _ in range(count)]

    return _add


@pytest.fixture
def make_rework():
    from orders.models import Rework

    def _make(item, assignee, due=None, **kwargs):
        kwargs.setdefault("reason", "fit")
        kwargs.setdefault("note", "Loosen waist by 1 inch")
        return Rework.objects.create(
            item=item, assignee=assignee, due_date=due, **kwargs
        )

    return _make
