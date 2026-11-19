from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.utils import timezone

from orders.drafts import delete_old_drafts
from orders.models import MaterialLine, Order, OrderItem
from orders.photos import add_photo

from .test_photos import png


def aged(order, hours):
    Order.objects.filter(pk=order.pk).update(
        created_at=timezone.now() - timedelta(hours=hours)
    )


def test_delete_old_drafts_removes_only_old_drafts(media, customer, blouse):
    old = Order.objects.create(customer=customer)
    photo = add_photo(OrderItem.from_product(old, blouse), png(300, 200))
    paths = [media / photo.image.name, media / photo.thumb.name]
    recent = Order.objects.create(customer=customer)
    placed = Order.objects.create(customer=customer, due_date=timezone.localdate())
    OrderItem.from_product(placed, blouse)
    placed.place()
    aged(old, 25)
    aged(recent, 2)
    aged(placed, 25)

    assert delete_old_drafts(timezone.now()) == 1
    assert set(Order.objects.all()) == {recent, placed}
    assert not any(p.exists() for p in paths)


def test_delete_old_drafts_command_reports_count(customer):
    aged(Order.objects.create(customer=customer), 30)
    out = StringIO()
    call_command("delete_old_drafts", stdout=out)
    assert "Deleted 1" in out.getvalue()


def test_seed_demo_creates_every_status(db):
    call_command("seed_demo", stdout=StringIO())
    orders = Order.objects.all()
    assert {o.status for o in orders} == {s for s, _ in Order.STATUSES}
    assert any(o.is_free for o in orders)
    assert MaterialLine.objects.filter(rework__isnull=False).exists()
    assert all(o.number for o in orders.exclude(status=Order.DRAFT))


def test_seed_demo_twice_adds_nothing(db):
    call_command("seed_demo", stdout=StringIO())
    count = Order.objects.count()
    out = StringIO()
    call_command("seed_demo", stdout=out)
    assert Order.objects.count() == count
    assert "already exist" in out.getvalue()


def test_delete_old_drafts_removes_files_after_rows(
    media, customer, blouse, monkeypatch
):
    old = Order.objects.create(customer=customer)
    add_photo(OrderItem.from_product(old, blouse), png(300, 200))
    aged(old, 25)
    rows_left = []
    from django.core.files.storage import FileSystemStorage

    real_delete = FileSystemStorage.delete

    def spy(self, name):
        rows_left.append(Order.objects.filter(pk=old.pk).exists())
        real_delete(self, name)

    monkeypatch.setattr(FileSystemStorage, "delete", spy)
    delete_old_drafts(timezone.now())
    assert rows_left == [False, False]
