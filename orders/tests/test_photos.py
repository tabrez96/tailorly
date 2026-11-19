from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from orders.models import Order, OrderItem, Rework
from orders.photos import NOT_A_PHOTO, add_photo, resize_photo
from staff.models import Employee

from .conftest import make_employee


def png(width, height):
    buffer = BytesIO()
    Image.new("RGB", (width, height), "teal").save(buffer, "PNG")
    return SimpleUploadedFile("p.png", buffer.getvalue(), "image/png")


def open_image(content):
    return Image.open(BytesIO(content.read()))


@pytest.fixture
def item(customer, blouse):
    order = Order.objects.create(customer=customer)
    return OrderItem.from_product(order, blouse)


@pytest.fixture
def photo(media, item):
    return add_photo(item, png(400, 300))


def test_resize_makes_1600_and_200_jpegs():
    full, thumb = map(open_image, resize_photo(png(3000, 2000)))
    assert (full.format, full.size) == ("JPEG", (1600, 1067))
    assert (thumb.format, thumb.size) == ("JPEG", (200, 200))


def test_small_photo_not_upscaled():
    full, _ = map(open_image, resize_photo(png(800, 600)))
    assert full.size == (800, 600)


def test_not_an_image_raises():
    with pytest.raises(ValueError, match="Choose a photo"):
        resize_photo(SimpleUploadedFile("x.txt", b"hello"))
    assert NOT_A_PHOTO.startswith("Choose a photo")


def test_add_photo_saves_files_and_positions(media, item):
    first, second = add_photo(item, png(400, 300)), add_photo(item, png(400, 300))
    assert (first.position, second.position) == (0, 1)
    for photo in (first, second):
        assert (media / photo.image.name).exists()
        assert (media / photo.thumb.name).exists()


def test_anonymous_redirected_to_sign_in(client, photo):
    response = client.get(reverse("item_photo", args=[photo.pk]))
    assert response.status_code == 302
    assert response.url.startswith(reverse("sign_in"))


def test_owner_gets_photo_and_thumb(owner_client, photo):
    responses = [
        owner_client.get(reverse(name, args=[photo.pk]))
        for name in ("item_photo", "item_photo_thumb")
    ]
    for response in responses:
        assert response.status_code == 200
        assert response["Content-Type"] == "image/jpeg"
        assert "private" in response["Cache-Control"]
    for response in responses:
        response.close()


def test_assigned_employee_gets_photo(client, photo, employee_user):
    user, employee = employee_user
    photo.item.order.assignee = employee
    photo.item.order.save()
    client.force_login(user)
    response = client.get(reverse("item_photo", args=[photo.pk]))
    assert response.status_code == 200
    response.close()


def test_rework_assignee_gets_photo(client, photo, employee_user):
    user, employee = employee_user
    Rework.objects.create(item=photo.item, reason=Rework.FIT, assignee=employee)
    client.force_login(user)
    response = client.get(reverse("item_photo", args=[photo.pk]))
    assert response.status_code == 200
    response.close()


def test_other_employee_gets_404(client, photo, employee_user):
    user, _ = employee_user
    _, other = make_employee("9000000002", "mina")
    photo.item.order.assignee = other
    photo.item.order.save()
    client.force_login(user)
    assert client.get(reverse("item_photo", args=[photo.pk])).status_code == 404


def test_user_without_employee_row_gets_404(client, photo, django_user_model):
    client.force_login(django_user_model.objects.create_user("nobody", password="x"))
    assert not Employee.objects.exists()
    assert client.get(reverse("item_photo", args=[photo.pk])).status_code == 404


def test_missing_file_404(owner_client, photo, media):
    (media / photo.image.name).unlink()
    assert owner_client.get(reverse("item_photo", args=[photo.pk])).status_code == 404
