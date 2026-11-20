from datetime import date
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.db.models.functions import Lower
from django.http import (
    FileResponse,
    Http404,
    HttpResponse,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, render
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import owner_required
from catalog.models import Product
from core.forms_ui import error_summary_text
from core.pages import page_location, render_page, sheet_saved_location
from customers.forms import CustomerForm
from customers.listing import add_initial, parse_query, search_filter
from customers.measurements import CM, INCHES, clean_rows, merge_fields, tiles
from customers.models import Customer, MeasurementSet
from orders.access import can_see_order
from orders.forms import ItemForm, PlaceForm
from orders.items import (
    TYPE_WORDS,
    item_products,
    item_summary,
    price_input,
    product_summary,
    resolve_type,
)
from orders.listing import (
    OPEN,
    READY,
    SHOWS,
    ListFilter,
    filter_url,
    order_row,
    ordering,
    parse_filter,
    rows_queryset,
    show_filter,
)
from orders.listing import search_filter as order_search_filter
from orders.making import ordinal, queue_place
from orders.models import ItemPhoto, Order, OrderError, OrderItem
from orders.photos import (
    MAX_PHOTOS,
    NOT_A_PHOTO,
    attach_photos,
    stage_photo,
    staged_photos,
)
from staff.attendance import first_name, initials
from staff.models import Employee


@login_required
def item_photo(request, pk, size="full"):
    photo = get_object_or_404(
        ItemPhoto.objects.select_related("item__order", "order"), pk=pk
    )
    order = photo.item.order if photo.item_id else photo.order
    if not can_see_order(request.user, order):
        raise Http404  # don't reveal that the photo exists
    field = photo.thumb if size == "thumb" else photo.image
    try:
        handle = field.open("rb")
    except FileNotFoundError:
        raise Http404 from None
    response = FileResponse(handle, content_type="image/jpeg")
    response["Cache-Control"] = "private, max-age=3600"
    return response


@owner_required
@require_POST
def item_photo_upload(request, pk):
    order = _draft_or_404(pk)
    upload = request.FILES.get("photo")
    if upload is None:
        return JsonResponse({"error": NOT_A_PHOTO}, status=400)
    try:
        photo = stage_photo(order, upload)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse(
        {"id": photo.pk, "thumb": reverse("item_photo_thumb", args=[photo.pk])},
        status=201,
    )


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


def _to_draft(request, order, toast=None):
    path = reverse("order_draft", args=[order.pk])
    if request.headers.get("HX-Request"):
        return page_location(path, toast)
    return _redirect_303(path)


@owner_required
def draft_new(request):
    return _to_draft(request, Order.objects.create())


@owner_required
@require_POST
def draft_customer(request, pk):
    order = _draft_or_404(pk)
    raw = request.POST.get("customer", "")
    if not raw.isdigit():
        raise Http404
    order.choose_customer(get_object_or_404(Customer, pk=int(raw)))
    return _to_draft(request, order)


def _placed_count():
    return Count("orders", filter=~Q(orders__status=Order.DRAFT))


@owner_required
def draft_customer_search(request, pk):
    order = _draft_or_404(pk)
    q = parse_query(request.GET)
    results = (
        Customer.objects.filter(search_filter(q))
        .annotate(order_count=_placed_count())
        .order_by(Lower("name"), "pk")[:8]
        if q
        else []
    )
    return render(
        request,
        "orders/_customer_results.html",
        {
            "q": q,
            "results": results,
            "choose_url": reverse("order_draft_customer", args=[order.pk]),
        },
    )


@owner_required
def draft_customer_add(request, pk):
    order = _draft_or_404(pk)
    status = 200
    if request.method == "POST":
        form = CustomerForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                saved = form.save()
                order.choose_customer(saved)
            return sheet_saved_location(
                reverse("order_draft", args=[order.pk]), f"{saved.name} added"
            )
        status = 422
    else:
        form = CustomerForm(initial=add_initial(request.GET.get("q", "")))
    return render(
        request,
        "customers/customer_sheet.html",
        {"form": form, "customer": None, "action": request.path},
        status=status,
    )


def _default_assignee(order):
    if order.assignee_id:
        return order.assignee
    active = list(Employee.objects.filter(active=True)[:2])
    return active[0] if len(active) == 1 else None


def _queue_hint(employee, due):
    try:
        work_plan_url = reverse("work_plan")
    except NoReverseMatch:  # the Work plan page isn't built yet
        work_plan_url = ""
    if employee is None:
        text = "Not in anyone's queue yet. You can assign it later in"
    else:
        dates = Order.objects.filter(
            assignee=employee, status__in=[Order.OPEN, Order.IN_PROGRESS]
        ).values_list("due_date", flat=True)
        text = (
            f"Goes {ordinal(queue_place(list(dates), due))} in "
            f"{first_name(employee.name)}'s queue, by due date and time needed. "
            "You can move it in"
        )
    return {"text": text, "work_plan_url": work_plan_url}


def _place_form(order, items, data=None, **kwargs):
    return PlaceForm(
        data,
        order=order,
        items=items,
        total=order.billed_total(),
        **kwargs,
    )


def _draft_context(request, order, form):
    items = list(order.items.prefetch_related("photos"))
    chosen = order.customer
    rows = []
    for n, i in enumerate(items, 1):
        pics = list(i.photos.all())
        rows.append(
            {
                "number": n,
                "name": i.name,
                "custom": i.type == Product.CUSTOM,
                "summary": item_summary(i),
                "price": i.price,
                "usual": i.usual_price,
                "edit_url": reverse("order_item_edit", args=[order.pk, i.pk]),
                "photo": reverse("item_photo_thumb", args=[pics[0].pk])
                if pics
                else None,
                "photo_count": len(pics),
            }
        )
    form.is_valid()  # no-op for an unbound form
    assignee = form["assignee"].value()
    due = form["due_date"].value()
    try:
        due = date.fromisoformat(due) if isinstance(due, str) else due
    except ValueError:
        due = None
    employee = (
        Employee.objects.filter(pk=assignee, active=True).first()
        if str(assignee).isdigit()
        else None
    )
    return {
        "title": "New order",
        "overline": "Sale order",
        "tab": "orders",
        "subpage": True,
        "back_url": reverse("customer", args=[chosen.pk])
        if chosen
        else reverse("today"),
        "back_direct": True,
        "customer": {
            "name": chosen.name,
            "phone": chosen.phone,
            "initials": initials(chosen.name),
            "orders": chosen.orders.exclude(status=Order.DRAFT).count(),
        }
        if chosen
        else None,
        "choose_url": reverse("order_draft_customer", args=[order.pk]),
        "search_url": reverse("order_draft_customer_search", args=[order.pk]),
        "customer_add_url": reverse("order_draft_customer_add", args=[order.pk]),
        "rows": rows,
        "add_url": reverse("order_item_add", args=[order.pk]),
        "form": form,
        "free": form["paid_by"].value() == Order.FREE,
        "total": form.total,
        "usual_total": sum((i.usual_price for i in items), Decimal("0")),
        "item_count": len(rows),
        "show_making": not rows or form.custom,
        "estimates": [form[n] for n in form.estimate_names],
        "place_url": reverse("order_draft_place", args=[order.pk]),
        "paid_by_url": reverse("order_draft_paid_by", args=[order.pk]),
        "hint_url": reverse("order_draft_queue_hint", args=[order.pk]),
        "hint": _queue_hint(employee, due),
        "error_text": error_summary_text(form.error_count(), "create this order")
        if form.is_bound and form.error_count()
        else "",
    }


@owner_required
def draft(request, pk):
    order = _draft_or_404(pk)
    form = _place_form(
        order,
        list(order.items.select_related("product")),
        initial={
            "paid_by": order.paid_by,
            "assignee": _default_assignee(order),
        },
    )
    return render_page(
        request, "orders/draft.html", _draft_context(request, order, form)
    )


@owner_required
@require_POST
def draft_paid_by(request, pk):
    _draft_or_404(pk)
    value = request.POST.get("paid_by")
    if value not in (Order.CUSTOMER, Order.FREE):
        return HttpResponse(status=400)
    # Only while it is still a draft: a placed order must keep its payer.
    changed = Order.objects.filter(pk=pk, status=Order.DRAFT).update(
        paid_by=value, updated_at=timezone.now()
    )
    return HttpResponse(status=204 if changed else 409)


@owner_required
def draft_queue_hint(request, pk):
    order = _draft_or_404(pk)
    raw = request.GET.get("assignee", "")
    employee = (
        Employee.objects.filter(pk=int(raw), active=True).first()
        if raw.isdigit()
        else None
    )
    try:
        due = date.fromisoformat(request.GET.get("due_date", ""))
    except ValueError:
        due = None
    return render(
        request,
        "orders/_queue_hint.html",
        {
            "hint": _queue_hint(employee, due),
            "hint_url": reverse("order_draft_queue_hint", args=[order.pk]),
        },
    )


class _AlreadyPlaced(Exception):
    pass


def _redirect_or_location(request, path):
    if request.headers.get("HX-Request"):
        return page_location(path)
    return _redirect_303(path)


@owner_required
@require_POST
def draft_place(request, pk):
    order = _draft_or_404(pk)
    items = list(order.items.select_related("product"))
    form = _place_form(order, items, request.POST)
    if form.ready():
        cd = form.cleaned_data
        try:
            with transaction.atomic():
                # Lock the row so a second tab can't place the same draft again.
                if not Order.objects.select_for_update().filter(
                    pk=order.pk, status=Order.DRAFT
                ):
                    raise _AlreadyPlaced
                order.paid_by = cd["paid_by"]
                order.due_date = cd["due_date"] if form.custom else None
                order.assignee = cd["assignee"] if form.custom else None
                order.save(
                    update_fields=["paid_by", "due_date", "assignee", "updated_at"]
                )
                for item in items:
                    if item.pk in form.estimates:
                        updated = OrderItem.objects.filter(pk=item.pk).update(
                            estimate_minutes=form.estimates[item.pk]
                        )
                        if not updated:
                            raise OrderError("An item was removed. Check the items.")
                order.place()
                if not order.is_free and cd["advance"]:
                    order.record_payment(
                        cd["advance"], timezone.localdate(), cd["method"]
                    )
        except _AlreadyPlaced:
            return _redirect_or_location(request, reverse("order", args=[order.pk]))
        except OrderError as e:  # e.g. an item was removed in another tab
            items = list(order.items.select_related("product"))
            form = _place_form(order, items, request.POST)
            form.is_valid()
            form.items_error = str(e)
        else:
            path = reverse("order", args=[order.pk])
            if request.headers.get("HX-Request"):
                return page_location(path, f"Order #{order.number} created")
            return _redirect_303(path)
    return render_page(
        request,
        "orders/draft.html",
        _draft_context(request, order, form),
        status=422,
    )


@login_required
def order_detail(request, pk):
    order = get_object_or_404(
        Order.objects.select_related("customer", "assignee").exclude(
            status=Order.DRAFT
        ),
        pk=pk,
    )
    if not can_see_order(request.user, order):
        raise Http404
    return render_page(
        request,
        "orders/order.html",
        {
            "title": f"Order #{order.number}",
            "overline": order.customer.name,
            "tab": "orders",
            "subpage": True,
            "back_url": reverse("orders"),
            "order": order,
            "items": list(order.items.all()),
            "invoice": order.invoice(),
            "payments": list(order.payments.all()),
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
    photo_ids = data.getlist("photo")
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
            with transaction.atomic():
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
                attach_photos(item, photo_ids)
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
    name = order.customer.name if order.customer else ""
    if item is None:
        labels = {
            "title": "Add item",
            "overline": f"New order · {name}" if name else "New order",
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
    saved_photos = list(item.photos.all()) if item else []
    saved_pks = {p.pk for p in saved_photos}
    staged = staged_photos(order, photo_ids)[: max(0, MAX_PHOTOS - len(saved_photos))]
    photos = [
        {
            "id": p.pk,
            "thumb": reverse("item_photo_thumb", args=[p.pk]),
            "saved": p.pk in saved_pks,
        }
        for p in saved_photos + staged
    ]
    photo_name = product.name if product else (item.name if item else "Item")
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
            "first_name": first_name(name) if name else "",
            "products_url": reverse("products"),
            "price_value": form["price"].value() or "",
            "photos_data": {
                "photos": photos,
                "max": MAX_PHOTOS,
                "url": reverse("order_photo_upload", args=[order.pk]),
                "name": photo_name,
            },
            "picture_url": photos[0]["thumb"] if photos else "",
            "photo_count": len(photos),
            "photo_name": photo_name,
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
        also = (
            product is not None
            and order.customer is not None
            and request.POST.get("also_update") == "1"
        )
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
            + (f"{order.customer.name} · " if order.customer else "")
            + "this order only",
            "rows": rows,
            "unit": unit,
            "action": request.path,
            "also_label": (
                f"Also update {first_name(order.customer.name)}'s "
                f"saved {product.name} measurements"
                if product and order.customer
                else ""
            ),
            "also_checked": also,
            "error_text": error_summary_text(errors, "save these measurements")
            if errors
            else "",
        },
        status=status,
    )


@owner_required
def orders(request):
    f = parse_filter(request.GET)
    today = timezone.localdate()
    base = reverse("orders")
    placed = Order.objects.exclude(status=Order.DRAFT)
    counts = placed.aggregate(
        open=Count("id", filter=show_filter(OPEN, today)),
        ready=Count("id", filter=show_filter(READY, today)),
    )
    qs = placed.filter(show_filter(f.show, today))
    if f.q:
        qs = qs.filter(order_search_filter(f.q))
    rows = [order_row(o, today) for o in rows_queryset(qs.order_by(*ordering(f.show)))]
    chips = [
        {
            "id": f"chip-{key}",
            "label": label,
            "count": counts.get(key),
            "url": filter_url(base, ListFilter(key, f.q)),
            "selected": f.show == key,
        }
        for key, label in SHOWS
    ]
    return render_page(
        request,
        "orders/orders.html",
        {
            "title": "Orders",
            "tab": "orders",
            "filter": f,
            "chips": chips,
            "rows": rows,
            "has_any": placed.exists(),
            "base_url": base,
            "new_url": reverse("order_new"),
            "clear_url": filter_url(base, ListFilter(f.show)),
            "show_label": dict(SHOWS)[f.show].lower(),
        },
    )
