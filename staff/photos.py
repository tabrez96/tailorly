from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

THUMB = 200


def resize_photo(upload) -> ContentFile:
    """The avatar is the only place a photo is shown: keep a 200 px square JPEG."""
    img = ImageOps.exif_transpose(Image.open(upload)).convert("RGB")
    img = ImageOps.fit(img, (THUMB, THUMB))
    buffer = BytesIO()
    img.save(buffer, "JPEG", quality=85)
    return ContentFile(buffer.getvalue(), name="photo.jpg")
