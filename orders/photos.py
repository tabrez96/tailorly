from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

from orders.models import ItemPhoto

FULL, THUMB = 1600, 200
NOT_A_PHOTO = "Choose a photo (JPEG or PNG)."


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


def add_photo(item, upload) -> ItemPhoto:
    full, thumb = resize_photo(upload)
    photo = ItemPhoto(item=item, position=item.photos.count())
    photo.image.save("photo.jpg", full, save=False)
    photo.thumb.save("thumb.jpg", thumb, save=False)
    photo.save()
    return photo
