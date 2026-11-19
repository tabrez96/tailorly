import json
import re
from datetime import timedelta
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from orders.drafts import delete_old_drafts
from orders.models import ItemPhoto, Order, OrderItem, Rework
from orders.photos import (
    MAX_BYTES,
    NOT_A_PHOTO,
    TOO_BIG,
    add_photo,
    attach_photos,
    resize_photo,
    stage_photo,
    staged_photos,
)
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


@pytest.fixture
def draft(customer):
    return Order.objects.create(customer=customer)


@pytest.fixture
def staged(media, draft):
    return stage_photo(draft, png(400, 300))


def photos_data(response):
    raw = re.search(
        r'<script id="item-photos-data"[^>]*>(.*?)</script>',
        response.content.decode(),
    ).group(1)
    return json.loads(raw)


def post_item(client, url, blouse, **extra):
    data = {"type": "custom", "product": blouse.pk, "price": "1500", **extra}
    return client.post(url, data, HTTP_HX_REQUEST="true")


def test_stage_photo_has_order_no_item(media, draft):
    photo = stage_photo(draft, png(400, 300))
    assert photo.item is None and photo.order == draft
    assert (media / photo.image.name).exists()
    assert (media / photo.thumb.name).exists()


def test_stage_photo_too_big(media, draft):
    upload = png(10, 10)
    upload.size = MAX_BYTES + 1
    with pytest.raises(ValueError, match=TOO_BIG):
        stage_photo(draft, upload)


def test_staged_photos_filters_and_keeps_order(media, draft, customer, photo):
    a, b = stage_photo(draft, png(50, 50)), stage_photo(draft, png(50, 50))
    other = stage_photo(Order.objects.create(customer=customer), png(50, 50))
    ids = [
        str(b.pk),
        "x",
        str(a.pk),
        str(a.pk),
        str(other.pk),
        str(photo.pk),
        7,
        "²",
        "9" * 40,
    ]
    assert staged_photos(draft, ids) == [b, a]


def test_attach_photos_positions_and_cap(media, item, draft):
    add_photo(item, png(50, 50))
    extra = [stage_photo(item.order, png(50, 50)) for _ in range(3)]
    attach_photos(item, [str(p.pk) for p in extra])
    for p in extra:
        p.refresh_from_db()
    assert [(p.item_id, p.position) for p in extra[:2]] == [
        (item.pk, 1),
        (item.pk, 2),
    ]
    assert extra[2].item_id is None
    assert item.photos.count() == 3


def test_attach_photos_skips_photo_claimed_meanwhile(media, item, draft, monkeypatch):
    other = OrderItem.from_product(draft, item.product)
    taken = stage_photo(draft, png(50, 50))
    free = stage_photo(draft, png(50, 50))
    # Both pass the read, but another save claims `taken` before the write.
    candidates = [taken, free]
    ItemPhoto.objects.filter(pk=taken.pk).update(item=other, position=0)
    monkeypatch.setattr("orders.photos.staged_photos", lambda order, ids: candidates)
    attach_photos(item, [str(taken.pk), str(free.pk)])
    taken.refresh_from_db()
    free.refresh_from_db()
    assert (taken.item_id, taken.position) == (other.pk, 0)
    assert (free.item_id, free.position) == (item.pk, 0)


def test_upload_view_returns_id_and_thumb(owner_client, media, draft):
    response = owner_client.post(
        reverse("order_photo_upload", args=[draft.pk]), {"photo": png(300, 300)}
    )
    assert response.status_code == 201
    body = response.json()
    assert ItemPhoto.objects.get(pk=body["id"]).order == draft
    thumb = owner_client.get(body["thumb"])
    assert thumb.status_code == 200
    thumb.close()
    assert body["thumb"] == reverse("item_photo_thumb", args=[body["id"]])


def test_upload_view_rejects_non_image(owner_client, media, draft):
    url = reverse("order_photo_upload", args=[draft.pk])
    bad = SimpleUploadedFile("x.txt", b"hello")
    response = owner_client.post(url, {"photo": bad})
    assert (response.status_code, response.json()) == (400, {"error": NOT_A_PHOTO})
    assert owner_client.post(url, {}).status_code == 400


def test_upload_view_404_for_non_draft(owner_client, draft):
    Order.objects.filter(pk=draft.pk).update(status=Order.OPEN, number=1)
    url = reverse("order_photo_upload", args=[draft.pk])
    assert owner_client.post(url, {"photo": png(10, 10)}).status_code == 404


def test_staged_photo_hidden_from_employee(client, staged, employee_user):
    user, _ = employee_user
    client.force_login(user)
    assert client.get(reverse("item_photo_thumb", args=[staged.pk])).status_code == 404


def test_add_item_attaches_staged_photos(owner_client, media, draft, blouse):
    a, b = stage_photo(draft, png(50, 50)), stage_photo(draft, png(50, 50))
    url = f"/orders/drafts/{draft.pk}/items/new/"
    response = post_item(owner_client, url, blouse, photo=[a.pk, b.pk])
    assert response.status_code == 204
    item = draft.items.get()
    assert list(item.photos.all()) == [a, b]
    page = owner_client.get(f"/orders/drafts/{draft.pk}/").content.decode()
    assert reverse("item_photo_thumb", args=[a.pk]) in page
    assert 'alt="Blouse, photo 1 of 2"' in page


def test_edit_item_shows_saved_and_attaches_new(owner_client, media, draft, blouse):
    item = OrderItem.from_product(draft, blouse)
    saved = add_photo(item, png(50, 50))
    url = f"/orders/drafts/{draft.pk}/items/{item.pk}/"
    data = photos_data(owner_client.get(url))
    assert data["photos"] == [
        {
            "id": saved.pk,
            "thumb": reverse("item_photo_thumb", args=[saved.pk]),
            "saved": True,
        }
    ]
    new = stage_photo(draft, png(50, 50))
    post_item(owner_client, url, blouse, photo=[saved.pk, new.pk])
    assert list(item.photos.all()) == [saved, new]


def test_rerender_keeps_staged_photos(owner_client, staged, draft, blouse):
    url = f"/orders/drafts/{draft.pk}/items/new/"
    response = owner_client.get(
        f"{url}?type=custom&product={blouse.pk}&photo={staged.pk}"
    )
    assert [p["id"] for p in photos_data(response)["photos"]] == [staged.pk]


def test_delete_old_drafts_removes_staged_files(media, draft, staged):
    Order.objects.update(created_at=timezone.now() - timedelta(days=3))
    paths = [media / staged.image.name, media / staged.thumb.name]
    assert delete_old_drafts(timezone.now()) == 1
    assert not any(p.exists() for p in paths)
    assert not ItemPhoto.objects.exists()
