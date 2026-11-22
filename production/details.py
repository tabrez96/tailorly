"""The S08 details sheet: photos, measurements and notes, never money."""

from django.urls import reverse

from catalog.models import Product
from core.thumbs import photo_alt
from customers.measurements import tiles


def details_context(item, rework=None) -> dict:
    photos = list(item.photos.all())
    order = item.order
    due = rework.due_date if rework else order.due_date
    return {
        "item": item,
        "rework": rework,
        "title": f"Rework · {item.name}"
        if rework
        else f"#{order.number} · {item.name}",
        "order": order,
        "customer": order.customer,
        "due": due,
        "photos": [
            {
                "full": reverse("item_photo", args=[p.pk]),
                "thumb": reverse("item_photo_thumb", args=[p.pk]),
                "alt": photo_alt(item.name, n, len(photos)),
            }
            for n, p in enumerate(photos, start=1)
        ],
        "tiles": tiles(
            item.product.measurement_fields if item.product else [], item.measurements
        )
        if item.type == Product.CUSTOM
        else [],
        "notes": item.notes,
    }
