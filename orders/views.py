from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404

from orders.access import can_see_order
from orders.models import ItemPhoto


@login_required
def item_photo(request, pk, size="full"):
    photo = get_object_or_404(ItemPhoto.objects.select_related("item__order"), pk=pk)
    if not can_see_order(request.user, photo.item.order):
        raise Http404  # don't reveal that the photo exists
    field = photo.thumb if size == "thumb" else photo.image
    try:
        handle = field.open("rb")
    except FileNotFoundError:
        raise Http404 from None
    response = FileResponse(handle, content_type="image/jpeg")
    response["Cache-Control"] = "private, max-age=3600"
    return response
