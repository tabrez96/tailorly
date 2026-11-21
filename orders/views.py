import json
from datetime import date
from decimal import Decimal

from django.conf import settings
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
from django.utils.http import urlencode
from django.views.decorators.http import require_POST

from accounts.decorators import owner_required
from accounts.roles import OWNER, role_for
from catalog.models import Product
from core.formats import format_day
from core.forms_ui import error_summary_text
from core.money import format_inr
from core.pages import (
    page_location,
    render_page,
    sheet_saved_location,
    sheet_saved_swap,
)
from customers.forms import CustomerForm
from customers.listing import add_initial, parse_query, search_filter
from customers.measurements import CM, INCHES, clean_rows, merge_fields, tiles
from customers.models import Customer, MeasurementSet
from orders import finishing
from orders import invoice as invoice_mod
from orders.access import can_see_order
from orders.detail import (
    assigned_line,
    measurement_summary,
    queue_rank,
    status_steps,
)
from orders.finishing import per_unit, total_for
from orders.forms import (
    ItemForm,
    MaterialLineForm,
    OrderEditForm,
    PaymentForm,
    PlaceForm,
)
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
    STATUS_CHIPS,
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
from orders.materials import (
    bill_lines,
    cost_total,
    format_qty,
    line_row,
    material_choices,
    options_to_add,
    qty_label,
)
from orders.models import (
    ItemPhoto,
    MaterialLine,
    Order,
    OrderError,
    OrderItem,
    Payment,
)
from orders.photos import (
    MAX_BYTES,
    MAX_PHOTOS,
    NOT_A_PHOTO,
    TOO_BIG,
    TOO_MANY,
    add_photo,
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
    return render_page(request, "orders/order.html", _order_context(request, order))


ITEM_TONES = {"not_started": "warn", "in_progress": "pri", "finished": "ok"}


def _order_context(request, order) -> dict:
    owner = role_for(request.user) == OWNER
    assigned = None
    maker = ""
    if order.assignee:
        name = order.assignee.name
        maker = first_name(name)
        place = None
        if order.status in (Order.OPEN, Order.IN_PROGRESS):
            others = (
                Order.objects.filter(
                    assignee=order.assignee,
                    status__in=[Order.OPEN, Order.IN_PROGRESS],
                )
                .exclude(pk=order.pk)
                .values_list("pk", "due_date")
            )
            place = queue_rank(list(others), order.pk, order.due_date)
        assigned = {"initials": initials(name), "line": assigned_line(name, place)}
    saved = {
        s.product_id: s for s in MeasurementSet.objects.filter(customer=order.customer)
    }
    items = list(
        order.items.select_related("product").prefetch_related("photos", "materials")
    )
    label, tone = STATUS_CHIPS[order.status]
    return {
        "title": f"Order #{order.number}",
        "tab": "orders",
        "subpage": True,
        "back_url": reverse("orders"),
        "edit_url": reverse("order_edit", args=[order.pk])
        if owner
        and (
            order.status != Order.DELIVERED
            or any(i.type == Product.CUSTOM for i in items)
        )
        else "",
        "is_owner": owner,
        "customer_url": reverse("customer", args=[order.customer.pk]) if owner else "",
        "status_chip": {"label": label, "tone": tone},
        "steps": status_steps(order.status),
        "assigned": assigned,
        "maker": maker,
        "free": order.is_free,
        "items": [
            _item_card(order, item, number, saved.get(item.product_id), owner)
            for number, item in enumerate(items, start=1)
        ],
        "ready_url": reverse("order_ready", args=[order.pk]),
        "deliver_url": reverse("order_deliver", args=[order.pk]),
        "bar": finishing.bar(
            order,
            order.status == Order.READY and bool(finishing.pending_questions(order)),
        )
        if owner
        else None,
        **_invoice_context(order),
    }


def _placed_item_or_404(pk, item_pk, **filters) -> OrderItem:
    return get_object_or_404(
        OrderItem.objects.select_related(
            "order__customer", "order__assignee", "product"
        ).exclude(order__status=Order.DRAFT),
        pk=item_pk,
        order_id=pk,
        **filters,
    )


def _maker(order) -> str:
    return first_name(order.assignee.name) if order.assignee else ""


def _item_card(order, item, number, saved_set, owner=False) -> dict:
    custom = item.type == Product.CUSTOM
    item_tiles = (
        tiles(
            item.product.measurement_fields if item.product else [], item.measurements
        )
        if custom
        else []
    )
    # A set saved after the item was made says nothing about where it came from.
    if saved_set and saved_set.updated_at <= item.created_at:
        copied = (
            f"Copied from {first_name(order.customer.name)}'s {item.name} set, "
            f"{format_day(item.created_at)}. Kept with this item."
        )
    else:
        copied = "Measurements for this item only."
    photos = list(item.photos.all())
    return {
        "pk": item.pk,
        "number": number,
        "name": item.name,
        "custom": custom,
        "type_label": item.get_type_display(),
        "price": item.price,
        "status_label": item.get_status_display(),
        "status_tone": ITEM_TONES[item.status],
        "tiles": item_tiles,
        "has_values": any(str(m.get("value", "")).strip() for m in item.measurements),
        "summary": measurement_summary(item_tiles),
        "copied_text": copied,
        "notes": item.notes,
        "materials": _materials_block(item, "order", editable=owner),
        "measure_url": reverse(
            "order_item_measurements_sheet", args=[order.pk, item.pk]
        )
        if owner and custom and (item.product_id or item.measurements)
        else "",
        "photo_data_id": f"item-{item.pk}-photos-data",
        "photo_data": {
            "photos": [
                {
                    "id": p.pk,
                    "thumb": reverse("item_photo_thumb", args=[p.pk]),
                    "full": reverse("item_photo", args=[p.pk]),
                    "saved": True,
                }
                for p in photos
            ],
            "max": MAX_PHOTOS,
            "url": reverse("order_item_photo_add", args=[order.pk, item.pk]),
            "name": item.name,
        }
        if owner
        else None,
        "thumb": reverse("item_photo_thumb", args=[photos[0].pk]) if photos else None,
        "photos": [
            {
                "thumb": reverse("item_photo_thumb", args=[p.pk]),
                "full": reverse("item_photo", args=[p.pk]),
            }
            for p in photos
        ],
    }


def _render_item_card(request, item) -> HttpResponse:
    order = item.order
    ids = list(order.items.values_list("pk", flat=True))
    saved_set = MeasurementSet.objects.filter(
        customer=order.customer, product_id=item.product_id
    ).first()
    fresh = (
        OrderItem.objects.select_related("product")
        .prefetch_related("photos", "materials")
        .get(pk=item.pk)
    )
    card = _item_card(order, fresh, ids.index(item.pk) + 1, saved_set, owner=True)
    return render(
        request,
        "orders/_item_card.html",
        {"item": card, "is_owner": True, "free": order.is_free, "maker": _maker(order)},
    )


@owner_required
def item_measurements_sheet(request, pk, item_pk):
    item = _placed_item_or_404(pk, item_pk, type=Product.CUSTOM)
    order, product = item.order, item.product
    status, errors = 200, 0
    if request.method == "POST":
        also = product is not None and request.POST.get("also_update") == "1"
        pairs, rows = clean_rows(
            request.POST.getlist("field"),
            request.POST.getlist("value"),
            [],
            [],
            INCHES,
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
            if not request.headers.get("HX-Request"):
                return _redirect_303(reverse("order", args=[order.pk]))
            return sheet_saved_swap(
                _render_item_card(request, item),
                f"{item.name} measurements saved",
                f"#item-{item.pk}",
            )
        status = 422
    else:
        also = product is not None  # on by default
        rows = merge_fields(
            product.measurement_fields if product else [], item.measurements
        )
    ids = list(order.items.values_list("pk", flat=True))
    first = item.photos.order_by("position", "pk").first()
    return render(
        request,
        "orders/measurements_sheet.html",
        {
            "item": item,
            "thumb": reverse("item_photo_thumb", args=[first.pk]) if first else None,
            "subline": f"Item {ids.index(item.pk) + 1} of {len(ids)} · "
            f"#{order.number} · inches",
            "rows": rows,
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


@owner_required
@require_POST
def item_photo_add(request, pk, item_pk):
    item = _placed_item_or_404(pk, item_pk)
    upload = request.FILES.get("photo")
    if upload is None:
        return JsonResponse({"error": NOT_A_PHOTO}, status=400)
    if upload.size > MAX_BYTES:
        return JsonResponse({"error": TOO_BIG}, status=400)
    try:
        with transaction.atomic():
            # Lock the item so two uploads can't both pass the count check.
            OrderItem.objects.select_for_update().get(pk=item.pk)
            if item.photos.count() >= MAX_PHOTOS:
                return JsonResponse({"error": TOO_MANY}, status=400)
            photo = add_photo(item, upload)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse(
        {
            "id": photo.pk,
            "thumb": reverse("item_photo_thumb", args=[photo.pk]),
            "full": reverse("item_photo", args=[photo.pk]),
        },
        status=201,
    )


def _invoice_context(order) -> dict:
    invoice = order.invoice()
    return {
        "order": order,
        "invoice": invoice,
        "lines": bill_lines(order.items.prefetch_related("materials"))
        if invoice
        else [],
        "payments": list(order.payments.all()) if invoice else [],
        "payment_url": reverse("order_payment", args=[order.pk]),
        "send": _send_context(order) if invoice and order.can_send_invoice else None,
    }


def _invoice_message(order) -> str:
    return invoice_mod.whatsapp_text(
        settings.SHOP_NAME,
        order.number,
        bill_lines(order.items.prefetch_related("materials")),
        order.invoice(),
    )


def _send_context(order) -> dict:
    if not order.customer.phone:
        note = finishing.SEND_NO_PHONE
    elif order.invoice_last_sent_at:
        note = f"Last sent {format_day(order.invoice_last_sent_at)}"
    else:
        note = "Opens WhatsApp with the invoice and balance"
    return {
        "url": reverse("order_invoice_send", args=[order.pk]),
        "disabled": not order.customer.phone,
        "note": note,
        "text": (text := _invoice_message(order)),
        "wa_url": (
            invoice_mod.whatsapp_url(order.customer.phone, text)
            if order.customer.phone
            else ""
        ),
    }


def _whatsapp_redirect(request, url) -> HttpResponse:
    """Leave for WhatsApp; the URL is external, so _redirect_303 can't be used."""
    if request.headers.get("HX-Request"):
        return HttpResponse(headers={"HX-Redirect": url})
    return HttpResponseRedirect(url, status=303)


@owner_required
def payment_sheet(request, pk):
    order = get_object_or_404(
        Order.objects.select_related("customer").exclude(status=Order.DRAFT), pk=pk
    )
    invoice = order.invoice()
    form = PaymentForm(
        request.POST or None,
        initial={
            "amount": price_input(max(invoice.balance, Decimal(0))) if invoice else "",
            "date": timezone.localdate(),
            "method": Payment.CASH,
        },
    )
    status = 200
    if request.method == "POST":
        if form.is_valid():
            cd = form.cleaned_data
            try:
                with transaction.atomic():
                    order.record_payment(cd["amount"], cd["date"], cd["method"])
            except OrderError as e:
                form.add_error(None, str(e))
            else:
                return sheet_saved_swap(
                    render(
                        request,
                        "orders/_invoice.html",
                        {**_invoice_context(order), "is_owner": True},
                    ),
                    "Payment saved",
                    "#order-invoice",
                )
        status = 422
    subline = f"#{order.number}"
    if invoice:
        subline += f" · balance {format_inr(invoice.balance)}"
    return render(
        request,
        "orders/payment_sheet.html",
        {"form": form, "order": order, "subline": subline},
        status=status,
    )


def _order_refreshed(request, order, toast) -> HttpResponse:
    """Refresh the page content in place, close the sheet and show a toast."""
    if not request.headers.get("HX-Request"):
        return _redirect_303(reverse("order", args=[order.pk]))
    order = Order.objects.select_related("customer", "assignee").get(pk=order.pk)
    response = render(
        request,
        "shell/page.html",
        {
            **_order_context(request, order),
            "page_template": "orders/order.html",
            "partial": False,
        },
    )
    response["HX-Retarget"] = "#page"
    response["HX-Reswap"] = "innerHTML"
    response["HX-Trigger"] = json.dumps(
        {"sheet:close": True, "toast": {"message": toast}}
    )
    return response


def _finish_sheet(
    request,
    order,
    mode,
    questions,
    rows=None,
    *,
    error_count=0,
    confirm="",
    action="",
    status=200,
    send_checked=False,
) -> HttpResponse:
    if questions:
        subline = (
            f"#{order.number} has {finishing.things(len(questions))} to fill in first."
        )
    elif mode == "ready":
        subline = (
            f"Mark #{order.number} ready for "
            f"{first_name(order.customer.name)} to collect?"
        )
    else:
        subline = f"Mark #{order.number} delivered?"
    words = f"mark this order {'ready' if mode == 'ready' else 'delivered'}"
    response = render(
        request,
        "orders/finish_sheet.html",
        {
            "order": order,
            "mode": mode,
            "action_url": reverse(f"order_{mode}", args=[order.pk]),
            "rows": rows
            if rows is not None
            else [finishing.question_row(q) for q in questions],
            "subline": subline,
            "error_text": error_summary_text(error_count, words) if error_count else "",
            "confirm": confirm,
            "action": action,
            "send": finishing.send_row(order, send_checked)
            if mode == "ready"
            else None,
        },
        status=status,
    )
    return response


def _ready_order_or_404(pk) -> Order:
    return get_object_or_404(
        Order.objects.select_related("customer").exclude(status=Order.DRAFT), pk=pk
    )


@owner_required
def order_ready(request, pk):
    order = _ready_order_or_404(pk)
    if request.method != "POST":
        if order.status not in (Order.OPEN, Order.IN_PROGRESS):
            return _order_refreshed(
                request,
                order,
                f"This order is already {order.get_status_display().lower()}.",
            )
        return _finish_sheet(
            request, order, "ready", finishing.pending_questions(order)
        )
    action = request.POST.get("action")  # "save" | "skip" | None (no questions)
    send = request.POST.get("send_invoice") == "1"
    url = ""
    try:
        with transaction.atomic():
            order = (
                Order.objects.select_for_update(of=("self",))
                .select_related("customer")
                .get(pk=order.pk)
            )
            if order.status not in (Order.OPEN, Order.IN_PROGRESS):
                order.mark_ready()  # raises OrderError before any answer is checked
            questions = finishing.pending_questions(order)
            if questions and action == "save":
                rows, errors = finishing.save_answers(questions, request.POST)
                if errors:
                    return _finish_sheet(
                        request,
                        order,
                        "ready",
                        questions,
                        rows,
                        error_count=errors,
                        status=422,
                        send_checked=send,
                    )
            order.mark_ready()  # raises OrderError unless Open or In progress
            if send and order.customer.phone and not order.is_free:
                order.record_invoice_sent()
                url = invoice_mod.whatsapp_url(
                    order.customer.phone, _invoice_message(order)
                )
    except OrderError as e:
        return _order_refreshed(request, order, str(e))
    if url:
        return _whatsapp_redirect(request, url)
    return _order_refreshed(request, order, f"Order #{order.number} is ready")


@owner_required
@require_POST
def invoice_send(request, pk):
    order = _ready_order_or_404(pk)
    if not order.can_send_invoice:
        return _order_refreshed(
            request, order, "Only ready and delivered orders have an invoice to send."
        )
    if not order.customer.phone:
        return _order_refreshed(request, order, finishing.SEND_NO_PHONE)
    order.record_invoice_sent()
    # The page opens WhatsApp itself (window.open), so htmx has nothing to swap.
    if request.headers.get("HX-Request"):
        return HttpResponse(status=204)
    url = invoice_mod.whatsapp_url(order.customer.phone, _invoice_message(order))
    return _whatsapp_redirect(request, url)


@owner_required
def order_deliver(request, pk):
    order = _ready_order_or_404(pk)
    if request.method != "POST":
        if order.status != Order.READY:
            message = (
                "Mark this order ready first."
                if order.status in (Order.OPEN, Order.IN_PROGRESS)
                else f"This order is already {order.get_status_display().lower()}."
            )
            return _order_refreshed(request, order, message)
        return _finish_sheet(
            request, order, "deliver", finishing.pending_questions(order)
        )
    action = request.POST.get("action", "")
    try:
        with transaction.atomic():
            order = (
                Order.objects.select_for_update(of=("self",))
                .select_related("customer")
                .get(pk=order.pk)
            )
            if order.status != Order.READY:
                order.mark_delivered()  # raises OrderError with the model's message
            questions = finishing.pending_questions(order)
            rows = None
            if questions and action == "save":
                rows, errors = finishing.save_answers(questions, request.POST)
                if errors:
                    return _finish_sheet(
                        request,
                        order,
                        "deliver",
                        questions,
                        rows,
                        error_count=errors,
                        status=422,
                    )
            confirm = finishing.deliver_confirm(order)  # billed materials change it
            if confirm and request.POST.get("confirmed") != "1":
                transaction.set_rollback(True)
                return _finish_sheet(
                    request,
                    order,
                    "deliver",
                    questions,
                    rows,
                    confirm=confirm,
                    action=action,
                )
            order.mark_delivered()
    except OrderError as e:
        return _order_refreshed(request, order, str(e))
    return _order_refreshed(request, order, f"Order #{order.number} delivered")


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


ONE_ITEM = (
    "An order needs at least one item. Add another item before removing this one."
)


def _placed_or_404(pk) -> Order:
    return get_object_or_404(
        Order.objects.select_related("customer").exclude(status=Order.DRAFT), pk=pk
    )


def _editable_or_404(pk) -> Order:
    """A placed order whose items can still change (not Delivered)."""
    return get_object_or_404(
        Order.objects.select_related("customer").exclude(
            status__in=[Order.DRAFT, Order.DELIVERED]
        ),
        pk=pk,
    )


def _toast_only(message) -> HttpResponse:
    """Stay on the page and show a toast (nothing is swapped)."""
    response = HttpResponse()
    response["HX-Reswap"] = "none"
    response["HX-Trigger"] = json.dumps({"toast": {"message": message}})
    return response


@owner_required
def order_edit(request, pk):
    order = _placed_or_404(pk)
    form = OrderEditForm(
        request.POST if request.method == "POST" else None,
        order=order,
        initial={"due_date": order.due_date},
    )
    status = 200
    if request.method == "POST":
        if form.is_valid():
            if "due_date" in form.fields:
                order.due_date = form.cleaned_data["due_date"]
                order.save(update_fields=["due_date", "updated_at"])
            path = reverse("order", args=[order.pk])
            if request.headers.get("HX-Request"):
                return page_location(path, f"Order #{order.number} saved")
            return _redirect_303(path)
        status = 422
    locked = order.status == Order.DELIVERED
    rows = []
    for n, i in enumerate(order.items.prefetch_related("photos"), 1):
        pics = list(i.photos.all())
        rows.append(
            {
                "number": n,
                "name": i.name,
                "custom": i.type == Product.CUSTOM,
                "summary": item_summary(i),
                "price": i.price,
                "usual": i.usual_price,
                "edit_url": ""
                if locked
                else reverse("order_edit_item", args=[order.pk, i.pk]),
                "photo": reverse("item_photo_thumb", args=[pics[0].pk])
                if pics
                else None,
                "photo_count": len(pics),
            }
        )
    return render_page(
        request,
        "orders/order_edit.html",
        {
            "title": f"Edit order #{order.number}",
            "overline": order.customer.name,
            "tab": "orders",
            "subpage": True,
            "back_url": reverse("order", args=[order.pk]),
            "back_direct": True,
            "form": form,
            "locked": locked,
            "rows": rows,
            "add_url": ""
            if locked
            else reverse("order_edit_item_add", args=[order.pk]),
            "free": order.is_free,
            "total": order.billed_total(),
            "item_count": len(rows),
            "error_text": error_summary_text(len(form.errors), "save this order")
            if form.is_bound and form.errors
            else "",
        },
        status=status,
    )


@owner_required
def order_edit_item_add(request, pk):
    return _item_page(request, _editable_or_404(pk))


@owner_required
def order_edit_item(request, pk, item_pk):
    order = _editable_or_404(pk)
    item = get_object_or_404(
        OrderItem.objects.select_related("product"), pk=item_pk, order=order
    )
    return _item_page(request, order, item)


@owner_required
@require_POST
def order_edit_item_remove(request, pk, item_pk):
    order = _editable_or_404(pk)
    with transaction.atomic():
        # Lock the order so two tabs can't each remove one of the last two items.
        locked = Order.objects.select_for_update(of=("self",)).get(pk=order.pk)
        # Delivery may have committed since the order was first loaded.
        if locked.status == Order.DELIVERED:
            raise Http404
        item = get_object_or_404(OrderItem, pk=item_pk, order=order)
        if order.items.count() <= 1:
            if request.headers.get("HX-Request"):
                return _toast_only(ONE_ITEM)
            return _redirect_303(reverse("order_edit_item", args=[order.pk, item.pk]))
        name = item.name
        item.delete()
    path = reverse("order_edit", args=[order.pk])
    if request.headers.get("HX-Request"):
        return page_location(path, f"{name} removed")
    return _redirect_303(path)


def _materials_block(item, on, editable=True, heading=False) -> dict:
    """The context for the materials list of one item (S04 card, S20)."""
    query = f"?on={on}"
    lines = list(item.materials.all())
    costs = [c for c in (cost_total(m) for m in lines) if c is not None]
    return {
        "id": f"item-{item.pk}-materials",
        "heading": heading,
        "rows": [
            line_row(m)
            | {
                "edit_url": reverse(
                    "order_item_material", args=[item.order_id, item.pk, m.pk]
                )
                + query
                if editable
                else ""
            }
            for m in lines
        ],
        "cost": format_inr(sum(costs, Decimal(0))) if costs else "",
        "add_url": reverse("order_item_material_add", args=[item.order_id, item.pk])
        + query
        if editable
        else "",
    }


def _material_products():
    return (
        Product.objects.filter(kind=Product.SECONDARY, active=True)
        .annotate(uses=Count("material_lines"))
        .order_by("-uses", "name")
    )


def _material_item_or_404(pk, item_pk) -> OrderItem:
    return get_object_or_404(
        OrderItem.objects.select_related("order__customer", "product"),
        pk=item_pk,
        order_id=pk,
    )


def _material_on(data) -> str:
    return "page" if data.get("on") == "page" else "order"


def _material_done(request, item, on, toast) -> HttpResponse:
    if on == "page":
        fresh = OrderItem.objects.prefetch_related("materials").get(pk=item.pk)
        return sheet_saved_swap(
            render(
                request,
                "orders/_item_materials.html",
                {"block": _materials_block(fresh, "page", heading=True)},
            ),
            toast,
            f"#item-{item.pk}-materials",
        )
    return _order_refreshed(request, item.order, toast)


def _material_state(request, form, line, products, picked) -> dict:
    """What the sheet's Alpine component starts with."""
    post = request.method == "POST"
    if line is not None:
        state = {
            "materials": [],
            "picked": line.product_id,
            "unit": line.unit,
            "unitCost": None if line.cost_price is None else str(line.cost_price),
            "unitSell": str(line.selling_price),
            "qty": format_qty(line.quantity),
            "cost": price_input(cost_total(line))
            if line.cost_price is not None
            else "",
            "sell": price_input(total_for(line.selling_price, line.quantity)),
            "onBill": line.on_bill,
        }
    else:
        state = {
            "materials": material_choices(products),
            "picked": picked.pk if picked else None,
            "unit": picked.unit if picked else "",
            "unitCost": str(picked.cost_price) if picked else None,
            "unitSell": str(picked.selling_price) if picked else None,
            "qty": "1",
            "cost": price_input(total_for(picked.cost_price, Decimal(1)))
            if picked
            else "",
            "sell": price_input(total_for(picked.selling_price, Decimal(1)))
            if picked
            else "",
            "onBill": picked.billed_by_default if picked else False,
        }
    if post:
        state["qty"] = request.POST.get("qty", "")
        state["cost"] = request.POST.get("cost", "")
        state["sell"] = request.POST.get("sell", "")
        state["onBill"] = "on_bill" in request.POST
    return state


def _material_sheet(request, item, form, on, line=None, status=200):
    order = item.order
    adding = line is None
    ids = list(order.items.values_list("pk", flat=True))
    names = dict(order.items.values_list("pk", "name"))
    first = item.photos.order_by("position", "pk").first()
    products = list(_material_products()) if adding else []
    picked = None
    if adding:
        raw = request.POST.get("material") or request.GET.get("material", "")
        picked = next((p for p in products if str(p.pk) == raw), None)
    unit = line.unit if line else (picked.unit if picked else "")
    customer = order.customer
    here = reverse("order_item_material_add", args=[order.pk, item.pk])
    posted = request.POST.get("item", "")
    selected = int(posted) if posted.isdecimal() and int(posted) in ids else item.pk
    verb = "add" if adding else "save"
    return render(
        request,
        "orders/material_sheet.html",
        {
            "title": "Add material" if adding else "Edit material",
            "submit_label": "Add" if adding else "Save",
            "action": request.path,
            "on": on,
            "form": form,
            "item": item,
            "line": line,
            "thumb": reverse("item_photo_thumb", args=[first.pk]) if first else None,
            "number": ids.index(item.pk) + 1,
            "items": [
                {"pk": pk, "number": n, "name": names[pk]}
                for n, pk in enumerate(ids, start=1)
            ]
            if adding and on == "order" and len(ids) > 1
            else [],
            "selected": selected,
            "state": _material_state(request, form, line, products, picked)
            | {"changing": selected != item.pk},
            "qty_label": qty_label(unit),
            "bill_label": f"Add to {first_name(customer.name)}\u2019s bill"
            if customer
            else "Add to the customer\u2019s bill",
            "item_word": item.name.lower(),
            "remove_url": ""
            if adding
            else reverse(
                "order_item_material_remove", args=[order.pk, item.pk, line.pk]
            )
            + f"?on={on}",
            "new_material_url": reverse("product_add")
            + "?"
            + urlencode({"kind": "secondary", "return_to": f"{here}?on={on}"}),
            "error_text": error_summary_text(len(form.errors), f"{verb} this material")
            if form.errors
            else "",
        },
        status=status,
    )


@owner_required
def material_add(request, pk, item_pk):
    item = _material_item_or_404(pk, item_pk)
    data = request.POST if request.method == "POST" else request.GET
    on = _material_on(data)
    form = MaterialLineForm(
        request.POST or None,
        initial={"item": item.pk, "bought_on": timezone.localdate()},
        order=item.order,
        adding=True,
    )
    if request.method == "POST" and form.is_valid():
        cd = form.cleaned_data
        qty, cost, sell = form.amounts
        with transaction.atomic():
            MaterialLine.from_product(
                cd["material"],
                qty,
                item=cd["item"],
                cost_price=per_unit(cost, qty) if cost is not None else None,
                cost_unknown=cost is None,
                selling_price=per_unit(sell, qty),
                on_bill=cd["on_bill"],
                bought_on=cd["bought_on"],
            )
        return _material_done(
            request, cd["item"], on, f"{cd['material'].name} added to {cd['item'].name}"
        )
    return _material_sheet(
        request, item, form, on, status=422 if request.method == "POST" else 200
    )


@owner_required
def material_edit(request, pk, item_pk, line_pk):
    item = _material_item_or_404(pk, item_pk)
    line = get_object_or_404(MaterialLine, pk=line_pk, item=item)
    data = request.POST if request.method == "POST" else request.GET
    on = _material_on(data)
    form = MaterialLineForm(
        request.POST or None,
        initial={"item": item.pk, "bought_on": line.bought_on},
        order=item.order,
        adding=False,
    )
    if request.method == "POST" and form.is_valid():
        cd = form.cleaned_data
        qty, cost, sell = form.amounts
        line.quantity = qty
        line.cost_price = per_unit(cost, qty) if cost is not None else None
        line.selling_price = per_unit(sell, qty)
        line.on_bill = cd["on_bill"]
        line.bought_on = cd["bought_on"]
        line.save(
            update_fields=[
                "quantity",
                "cost_price",
                "selling_price",
                "on_bill",
                "bought_on",
            ]
        )
        return _material_done(request, item, on, f"{line.name} saved")
    return _material_sheet(
        request, item, form, on, line, status=422 if request.method == "POST" else 200
    )


@owner_required
@require_POST
def material_remove(request, pk, item_pk, line_pk):
    item = _material_item_or_404(pk, item_pk)
    line = get_object_or_404(MaterialLine, pk=line_pk, item=item)
    name = line.name
    line.delete()
    return _material_done(request, item, _material_on(request.GET), f"{name} removed")


def _item_page(request, order, item=None):
    placed = order.status != Order.DRAFT
    back_path = (
        reverse("order_edit", args=[order.pk])
        if placed
        else reverse("order_draft", args=[order.pk])
    )
    data = request.POST if request.method == "POST" else request.GET
    photo_ids = [] if placed else data.getlist("photo")
    keep_pk = item.product_id if item else None
    # First GET of the edit page: nothing from the form yet, so show the item.
    fresh = item is not None and "product" not in data
    # A placed item keeps its garment: only price, options and notes change.
    lock_product = placed and item is not None and bool(item.product_id)
    if lock_product:
        data = data.copy()
        data["type"] = item.type
        data["product"] = str(item.product_id)
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
            data,
            type_=type_,
            product=product,
            options=options,
            keep_pk=keep_pk,
        )
        if form.is_valid():
            chosen = form.cleaned_data["product"]
            notes = form.cleaned_data["notes"].strip()
            with transaction.atomic():
                # Delivery may have committed since the order was first loaded.
                if (
                    placed
                    and Order.objects.select_for_update(of=("self",))
                    .get(pk=order.pk)
                    .status
                    == Order.DELIVERED
                ):
                    raise Http404
                # Answers saved before this edit: lines they made stay removed.
                before = (
                    list(item.options) if item and item.product_id == chosen.pk else []
                )
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
                if not placed:
                    attach_photos(item, photo_ids)
                have = {m.product_id for m in item.materials.all()}
                have |= {o.material_id for o in options_to_add(options, before, set())}
                for o in options_to_add(options, item.options, have):
                    MaterialLine.from_product(o.material, Decimal(1), item=item)
            if (
                not placed
                and request.POST.get("next") == "measurements"
                and item.type == Product.CUSTOM
            ):
                path, toast = (
                    reverse("order_item_measurements", args=[order.pk, item.pk]),
                    None,
                )
            elif request.POST.get("next") == "material":
                path, toast = (
                    reverse(
                        "order_edit_item" if placed else "order_item_edit",
                        args=[order.pk, item.pk],
                    )
                    + "?material=1",
                    None,
                )
            else:
                path = back_path
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
            "overline": f"Order #{order.number}"
            if placed
            else (f"New order · {name}" if name else "New order"),
            "submit_label": "Add to order",
            "leave_text": "Leave without adding this item? Your changes will be lost.",
            "remove_url": "",
        }
    else:
        ids = list(order.items.values_list("pk", flat=True))
        labels = {
            "title": item.name,
            "overline": (f"Order #{order.number}" if placed else "New order")
            + f" · Item {ids.index(item.pk) + 1} of {len(ids)}",
            "submit_label": "Save item",
            "leave_text": "Leave without saving this item? Your changes will be lost.",
            "remove_url": reverse(
                "order_edit_item_remove" if placed else "order_item_remove",
                args=[order.pk, item.pk],
            ),
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
            "placed": placed,
            "lock_product": lock_product,
            "tab": "orders",
            "subpage": True,
            "back_url": back_path,
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
            "materials": _materials_block(item, "page", heading=True) if item else None,
            "open_material": item is not None and request.GET.get("material") == "1",
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
