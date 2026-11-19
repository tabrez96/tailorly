from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.decorators import owner_required
from catalog.models import Product
from core.forms_ui import error_summary_text
from core.pages import page_location, render_page
from customers.measurements import CM, INCHES, clean_rows, merge_fields, tiles
from customers.models import Customer, MeasurementSet
from orders.access import can_see_order
from orders.forms import ItemForm
from orders.items import (
    TYPE_WORDS,
    item_products,
    item_summary,
    price_input,
    product_summary,
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
            "edit_url": reverse("order_item_edit", args=[order.pk, i.pk]),
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
    return _item_page(request, _draft_or_404(pk))


@owner_required
def item_edit(request, pk, item_pk):
    order = _draft_or_404(pk)
    item = get_object_or_404(
        OrderItem.objects.select_related("product"), pk=item_pk, order=order
    )
    return _item_page(request, order, item)


def _item_page(request, order, item=None):
    draft_path = reverse("order_draft", args=[order.pk])
    data = request.POST if request.method == "POST" else request.GET
    keep_pk = item.product_id if item else None
    # First GET of the edit page: nothing from the form yet, so show the item.
    fresh = item is not None and "product" not in data
    type_ = item.type if fresh else resolve_type(data.get("type"))
    raw = data.get("product", "")
    if fresh:
        product = item.product
    else:
        product = (
            item_products(type_, keep_pk).filter(pk=int(raw)).first()
            if raw.isdigit()
            else None
        )
    same = item is not None and product is not None and product.pk == item.product_id
    options = (
        list(product.options.select_related("material"))
        if product and product.type == Product.CUSTOM
        else []
    )
    status = 200
    if request.method == "POST":
        form = ItemForm(
            request.POST,
            type_=type_,
            product=product,
            options=options,
            keep_pk=keep_pk,
        )
        if form.is_valid():
            chosen = form.cleaned_data["product"]
            notes = form.cleaned_data["notes"].strip()
            if item is None:
                item = OrderItem.from_product(
                    order,
                    chosen,
                    form.answers(),
                    price=form.cleaned_data["price"],
                    notes=notes,
                )
                toast = f"{item.name} added"
            else:
                item.change(
                    chosen,
                    form.answers(),
                    price=form.cleaned_data["price"],
                    notes=notes,
                )
                toast = f"{item.name} saved"
            if (
                request.POST.get("next") == "measurements"
                and item.type == Product.CUSTOM
            ):
                path, toast = (
                    reverse("order_item_measurements", args=[order.pk, item.pk]),
                    None,
                )
            else:
                path = draft_path
            if request.headers.get("HX-Request"):
                return page_location(path, toast)
            return _redirect_303(path)
        status = 422
    else:
        initial = {
            "type": type_,
            "product": product.pk if product else None,
            "price": price_input(product.usual_price) if product else "",
            "notes": data.get("notes", ""),
        }
        if same:
            initial["price"] = (
                price_input(item.price)
                if fresh
                else data.get("price", price_input(item.price))
            )
            initial["notes"] = item.notes if fresh else data.get("notes", "")
            for o in options:
                key = f"opt_{o.pk}"
                if key in data:
                    initial[key] = data[key]
                else:
                    for a in item.options:
                        if a["name"] == o.name:
                            initial[key] = a["answer"]
        form = ItemForm(
            type_=type_,
            product=product,
            options=options,
            keep_pk=keep_pk,
            initial=initial,
        )
    copy, copied_on, from_set, measure_tiles = [], None, False, None
    if product and product.type == Product.CUSTOM:
        saved = MeasurementSet.objects.filter(
            customer=order.customer, product=product
        ).first()
        if same:
            copy, copied_on = item.measurements, item.created_at
        elif saved:
            copy, copied_on = saved.values, saved.updated_at
        from_set = saved is not None
        measure_tiles = tiles(product.measurement_fields, copy)
    has_values = any(str(m.get("value", "")).strip() for m in copy)
    if item is None:
        labels = {
            "title": "Add item",
            "overline": f"New order · {order.customer.name}",
            "submit_label": "Add to order",
            "leave_text": "Leave without adding this item? Your changes will be lost.",
            "remove_url": "",
        }
    else:
        ids = list(order.items.values_list("pk", flat=True))
        labels = {
            "title": item.name,
            "overline": f"New order · Item {ids.index(item.pk) + 1} of {len(ids)}",
            "submit_label": "Save item",
            "leave_text": "Leave without saving this item? Your changes will be lost.",
            "remove_url": reverse("order_item_remove", args=[order.pk, item.pk]),
        }
    return render_page(
        request,
        "orders/item_add.html",
        {
            **labels,
            "tab": "orders",
            "subpage": True,
            "back_url": draft_path,
            "action": request.path,
            "form": form,
            "product": product,
            "product_summary": product_summary(product) if product else "",
            "type_": type_,
            "type_word": TYPE_WORDS[type_],
            "has_products": item_products(type_, keep_pk).exists(),
            "tiles": measure_tiles,
            "has_values": has_values,
            "copied_on": copied_on,
            "from_set": from_set,
            "first_name": first_name(order.customer.name),
            "products_url": reverse("products"),
            "price_value": form["price"].value() or "",
        },
        status=status,
    )


@owner_required
@require_POST
def item_remove(request, pk, item_pk):
    order = _draft_or_404(pk)
    item = get_object_or_404(OrderItem, pk=item_pk, order=order)
    name = item.name
    item.delete()
    path = reverse("order_draft", args=[order.pk])
    if request.headers.get("HX-Request"):
        return page_location(path, f"{name} removed")
    return _redirect_303(path)


@owner_required
def item_measurements(request, pk, item_pk):
    order = _draft_or_404(pk)
    item = get_object_or_404(
        OrderItem.objects.select_related("product"),
        pk=item_pk,
        order=order,
        type=Product.CUSTOM,
    )
    product = item.product
    edit_path = reverse("order_item_edit", args=[order.pk, item.pk])
    ids = list(order.items.values_list("pk", flat=True))
    status, unit, errors, also = 200, INCHES, 0, False
    if request.method == "POST":
        unit = CM if request.POST.get("unit") == CM else INCHES
        also = product is not None and request.POST.get("also_update") == "1"
        pairs, rows = clean_rows(
            request.POST.getlist("field"),
            request.POST.getlist("value"),
            request.POST.getlist("new_name"),
            request.POST.getlist("new_value"),
            unit,
        )
        errors = sum(1 for r in rows if r.error)
        if not errors:
            with transaction.atomic():
                item.measurements = pairs
                item.save(update_fields=["measurements"])
                if also:
                    MeasurementSet.objects.update_or_create(
                        customer=order.customer,
                        product=product,
                        defaults={"values": pairs},
                    )
            if request.headers.get("HX-Request"):
                return page_location(edit_path, f"{item.name} measurements saved")
            return _redirect_303(edit_path)
        status = 422
    else:
        rows = merge_fields(
            product.measurement_fields if product else [], item.measurements
        )
    return render_page(
        request,
        "customers/measurements_form.html",
        {
            "title": f"{item.name} measurements",
            "tab": "orders",
            "subpage": True,
            "back_url": edit_path,
            "customer": order.customer,
            "subline": f"Item {ids.index(item.pk) + 1} of {len(ids)} · "
            f"{order.customer.name} · this order only",
            "rows": rows,
            "unit": unit,
            "action": request.path,
            "also_label": (
                f"Also update {first_name(order.customer.name)}'s "
                f"saved {product.name} measurements"
                if product
                else ""
            ),
            "also_checked": also,
            "error_text": error_summary_text(errors, "save these measurements")
            if errors
            else "",
        },
        status=status,
    )
