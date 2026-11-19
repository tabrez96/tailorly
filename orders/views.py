from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.decorators import owner_required
from catalog.models import Product
from core.pages import page_location, render_page
from customers.measurements import tiles
from customers.models import Customer, MeasurementSet
from orders.access import can_see_order
from orders.forms import ItemForm
from orders.items import (
    TYPE_WORDS,
    item_summary,
    price_input,
    product_summary,
    products_for,
    resolve_type,
)
from orders.models import ItemPhoto, Order, OrderItem
from staff.attendance import first_name


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


def _redirect_303(path):
    response = HttpResponseRedirect(path)
    response.status_code = 303
    return response


@owner_required
@require_POST
def draft_create(request):
    raw = request.POST.get("customer", "")
    if not raw.isdigit():
        raise Http404
    customer = get_object_or_404(Customer, pk=int(raw))
    order = Order.objects.create(customer=customer)
    path = reverse("order_draft", args=[order.pk])
    if request.headers.get("HX-Request"):
        return page_location(path)
    return _redirect_303(path)


def _draft_or_404(pk):
    return get_object_or_404(
        Order.objects.select_related("customer"), pk=pk, status=Order.DRAFT
    )


@owner_required
def draft(request, pk):
    order = _draft_or_404(pk)
    rows = [
        {
            "number": n,
            "name": i.name,
            "custom": i.type == Product.CUSTOM,
            "summary": item_summary(i),
            "price": i.price,
        }
        for n, i in enumerate(order.items.all(), 1)
    ]
    return render_page(
        request,
        "orders/draft.html",
        {
            "title": "New order",
            "overline": "Sale order",
            "tab": "orders",
            "subpage": True,
            "back_url": reverse("customer", args=[order.customer_id]),
            "back_direct": True,
            "rows": rows,
            "add_url": reverse("order_item_add", args=[order.pk]),
        },
    )


@owner_required
def item_add(request, pk):
    order = _draft_or_404(pk)
    draft_path = reverse("order_draft", args=[order.pk])
    data = request.POST if request.method == "POST" else request.GET
    type_ = resolve_type(data.get("type"))
    raw = data.get("product", "")
    product = products_for(type_).filter(pk=int(raw)).first() if raw.isdigit() else None
    options = (
        list(product.options.select_related("material"))
        if product and product.type == Product.CUSTOM
        else []
    )
    status = 200
    if request.method == "POST":
        form = ItemForm(request.POST, type_=type_, product=product, options=options)
        if form.is_valid():
            item = OrderItem.from_product(
                order,
                form.cleaned_data["product"],
                form.answers(),
                price=form.cleaned_data["price"],
                notes=form.cleaned_data["notes"].strip(),
            )
            if request.headers.get("HX-Request"):
                return page_location(draft_path, f"{item.name} added")
            return _redirect_303(draft_path)
        status = 422
    else:
        form = ItemForm(
            type_=type_,
            product=product,
            options=options,
            initial={
                "type": type_,
                "product": product.pk if product else None,
                "price": price_input(product.usual_price) if product else "",
                "notes": data.get("notes", ""),
            },
        )
    saved = measurement_tiles = None
    if product and product.type == Product.CUSTOM:
        saved = MeasurementSet.objects.filter(
            customer=order.customer, product=product
        ).first()
        measurement_tiles = tiles(
            product.measurement_fields, saved.values if saved else []
        )
    return render_page(
        request,
        "orders/item_add.html",
        {
            "title": "Add item",
            "overline": f"New order · {order.customer.name}",
            "tab": "orders",
            "subpage": True,
            "back_url": draft_path,
            "action": request.path,
            "form": form,
            "product": product,
            "product_summary": product_summary(product) if product else "",
            "type_": type_,
            "type_word": TYPE_WORDS[type_],
            "has_products": products_for(type_).exists(),
            "saved": saved,
            "tiles": measurement_tiles,
            "first_name": first_name(order.customer.name),
            "products_url": reverse("products"),
            "price_value": form["price"].value() or "",
        },
        status=status,
    )
