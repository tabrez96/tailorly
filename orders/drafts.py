from datetime import timedelta

from django.db import transaction

from orders.models import ItemPhoto, Order

MAX_AGE = timedelta(days=1)


def delete_old_drafts(now) -> int:
    """Delete drafts over a day old, with their photo files. Returns how many went."""
    old = Order.objects.filter(status=Order.DRAFT, created_at__lt=now - MAX_AGE)
    with transaction.atomic():
        photos = list(ItemPhoto.objects.filter(item__order__in=old))
        files = [
            (p.image.storage, n) for p in photos for n in (p.image.name, p.thumb.name)
        ]
        count = old.count()
        old.delete()
    # Files go only after the rows are gone, so a failure never orphans rows.
    for storage, name in files:
        storage.delete(name)
    return count
