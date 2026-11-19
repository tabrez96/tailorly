import json
from decimal import Decimal
from urllib.parse import urlencode

from django.db.models.functions import Lower
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.decorators import owner_required
from catalog.models import Product
from core.forms_ui import error_summary_text
from core.pages import render_page, sheet_saved_location
from customers.forms import CustomerForm, GarmentForm
from customers.listing import add_initial, parse_query, search_filter
from customers.measurements import (
    CM,
    INCHES,
    clean_rows,
    merge_fields,
    tiles,
)
from customers.models import Customer, MeasurementSet
from staff.attendance import first_name


@owner_required
def customers(request: HttpRequest) -> HttpResponse:
    q = parse_query(request.GET)
    queryset = Customer.objects.order_by(Lower("name"), "pk")
    if q:
        queryset = queryset.filter(search_filter(q))
    add_url = reverse("customer_add")
    return render_page(
        request,
        "customers/customers.html",
        {
            "title": "Customers",
            "tab": "customers",
            "customers": list(queryset),
            "q": q,
            "has_any": Customer.objects.exists(),
            "base_url": reverse("customers"),
            "add_url": add_url,
            "add_named_url": f"{add_url}?{urlencode({'q': q})}",
            "open_add": request.GET.get("add") == "1",
        },
    )


@owner_required
def customer_sheet(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    instance = get_object_or_404(Customer, pk=pk) if pk is not None else None
    status = 200
    if request.method == "POST":
        form = CustomerForm(request.POST, instance=instance)
        if form.is_valid():
            saved = form.save()
            return sheet_saved_location(
                reverse("customer", args=[saved.pk]),
                f"{saved.name} {'saved' if instance else 'added'}",
            )
        status = 422
    else:
        initial = add_initial(request.GET.get("q", "")) if instance is None else {}
        form = CustomerForm(instance=instance, initial=initial)
    return render(
        request,
        "customers/customer_sheet.html",
        {"form": form, "customer": instance, "action": request.path},
        status=status,
    )


@owner_required
def customer(request: HttpRequest, pk: int) -> HttpResponse:
    c = get_object_or_404(Customer, pk=pk)
    sets = list(
        c.measurement_sets.select_related("product").order_by(
            Lower("product__name"), "pk"
        )
    )
    wanted = request.GET.get("g")
    selected = next((s for s in sets if str(s.product_id) == wanted), None) or (
        sets[0] if sets else None
    )
    garments = [
        {
            "id": s.product_id,
            "name": s.product.name,
            "updated": s.updated_at,
            "selected": s is selected,
            "edit_url": reverse("customer_measurements", args=[c.pk, s.product_id]),
            "tiles": tiles(s.product.measurement_fields, s.values),
        }
        for s in sets
    ]
    return render_page(
        request,
        "customers/customer.html",
        {
            "title": c.name,
            "tab": "customers",
            "subpage": True,
            "back_url": reverse("customers"),
            "customer": c,
            "first_name": first_name(c.name),
            # Orders don't exist yet, so nothing has been spent or is owed.
            "spent": Decimal(0),
            "to_collect": Decimal(0),
            "edit_url": reverse("customer_edit", args=[c.pk]),
            "new_order_action": reverse("order_draft_create"),
            "garments": garments,
            "selected_id": selected.product_id if selected else 0,
            "add_garment_url": reverse("customer_garment_add", args=[c.pk]),
        },
    )


def _custom_products():
    return Product.objects.filter(kind=Product.PRIMARY, type=Product.CUSTOM)


@owner_required
def measurements_edit(request: HttpRequest, pk: int, product_pk: int) -> HttpResponse:
    c = get_object_or_404(Customer, pk=pk)
    product = get_object_or_404(Product, pk=product_pk, kind=Product.PRIMARY)
    existing = MeasurementSet.objects.filter(customer=c, product=product).first()
    # A saved set stays editable even if the product changed type or was archived.
    if existing is None and not (product.type == Product.CUSTOM and product.active):
        raise Http404
    path = reverse("customer", args=[c.pk]) + f"?g={product.pk}"
    status = 200
    unit = INCHES
    if request.method == "POST":
        unit = CM if request.POST.get("unit") == CM else INCHES
        pairs, rows = clean_rows(
            request.POST.getlist("field"),
            request.POST.getlist("value"),
            request.POST.getlist("new_name"),
            request.POST.getlist("new_value"),
            unit,
        )
        errors = sum(1 for r in rows if r.error)
        if not errors:
            MeasurementSet.objects.update_or_create(
                customer=c, product=product, defaults={"values": pairs}
            )
            if not request.headers.get("HX-Request"):
                return redirect(path)
            response = HttpResponse(status=204)
            response["HX-Location"] = json.dumps({"path": path, "target": "#page"})
            response["HX-Trigger"] = json.dumps(
                {"toast": {"message": f"{product.name} measurements saved"}}
            )
            return response
        status = 422
    else:
        errors = 0
        rows = merge_fields(
            product.measurement_fields, existing.values if existing else []
        )
    return render_page(
        request,
        "customers/measurements_form.html",
        {
            "title": f"{product.name} measurements",
            "subpage": True,
            "tab": "customers",
            "back_url": path,
            "customer": c,
            "updated": existing.updated_at if existing else None,
            "rows": rows,
            "unit": unit,
            "action": request.path,
            "error_text": error_summary_text(errors, "save these measurements")
            if errors
            else "",
        },
        status=status,
    )


@owner_required
def garment_add(request: HttpRequest, pk: int) -> HttpResponse:
    c = get_object_or_404(Customer, pk=pk)
    status = 200
    form = GarmentForm(request.POST or None, customer=c)
    if request.method == "POST":
        if form.is_valid():
            return sheet_saved_location(
                reverse(
                    "customer_measurements",
                    args=[c.pk, form.cleaned_data["product"].pk],
                )
            )
        status = 422
    return render(
        request,
        "customers/garment_sheet.html",
        {
            "form": form,
            "action": request.path,
            "has_custom": _custom_products().filter(active=True).exists(),
        },
        status=status,
    )
