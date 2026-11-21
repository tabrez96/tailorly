from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

from orders.models import ItemPhoto

FULL, THUMB = 1600, 200
NOT_A_PHOTO = "Choose a photo (JPEG or PNG)."
TOO_BIG = "Choose a photo under 20 MB."
TOO_MANY = "An item can have up to 3 photos."
MAX_PHOTOS = 3
MAX_BYTES = 20 * 1024 * 1024


def resize_photo(upload) -> tuple[ContentFile, ContentFile]:
    """A 1600 px (longest side) JPEG and a 200 px square thumbnail."""
    try:
        img = ImageOps.exif_transpose(Image.open(upload)).convert("RGB")
    except UnidentifiedImageError, Image.DecompressionBombError, OSError:
        raise ValueError(NOT_A_PHOTO) from None
    full = img.copy()
    full.thumbnail((FULL, FULL))  # never upscales
    thumb = ImageOps.fit(img, (THUMB, THUMB))
    return _jpeg(full, "photo.jpg"), _jpeg(thumb, "thumb.jpg")


def _jpeg(img, name) -> ContentFile:
    buffer = BytesIO()
    img.save(buffer, "JPEG", quality=85)
    return ContentFile(buffer.getvalue(), name=name)


def _save_files(photo, upload) -> ItemPhoto:
    full, thumb = resize_photo(upload)
    photo.image.save("photo.jpg", full, save=False)
    photo.thumb.save("thumb.jpg", thumb, save=False)
    photo.save()
    return photo


def add_photo(item, upload) -> ItemPhoto:
    photo = ItemPhoto(item=item, order=item.order, position=item.photos.count())
    return _save_files(photo, upload)


def stage_photo(order, upload) -> ItemPhoto:
    """Save a photo for an item that isn't saved yet; attach_photos claims it."""
    if upload.size > MAX_BYTES:
        raise ValueError(TOO_BIG)
    return _save_files(ItemPhoto(order=order, item=None), upload)


def staged_photos(order, ids) -> list[ItemPhoto]:
    """This order's unattached photos for the posted ids, in the posted order."""
    # isdecimal, not isdigit: "²" is a digit that int() rejects.
    # The length cap keeps ids within the database's integer range.
    wanted = list(
        dict.fromkeys(
            int(i) for i in ids if isinstance(i, str) and i.isdecimal() and len(i) <= 18
        )
    )
    found = {
        p.pk: p
        for p in ItemPhoto.objects.filter(order=order, item__isnull=True, pk__in=wanted)
    }
    return [found[i] for i in wanted if i in found]


def attach_photos(item, ids) -> None:
    have = item.photos.count()
    room = max(0, MAX_PHOTOS - have)
    position = have
    for photo in staged_photos(item.order, ids)[:room]:
        # Claim only if still unattached; a photo another save took is skipped.
        claimed = ItemPhoto.objects.filter(pk=photo.pk, item__isnull=True).update(
            item=item, position=position
        )
        position += claimed
