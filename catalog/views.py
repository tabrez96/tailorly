from urllib.parse import urlencode

from django.db.models import Count, Prefetch, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.decorators import owner_required
from catalog.forms import MaterialForm, ProductForm
from catalog.listing import (
    MATERIALS,
    SOLD,
    ListFilter,
    filter_url,
    material_used_by,
    options_summary,
    parse_filter,
    uses_summary,
)
from catalog.models import Product, ProductOption
from core.pages import render_page, sheet_saved_location


@owner_required
def products(request: HttpRequest) -> HttpResponse:
    f = parse_filter(request.GET)
    base = reverse("products")
    active = Product.objects.filter(active=True)
    counts = active.aggregate(
        sold=Count("id", filter=Q(kind="primary")),
        materials=Count("id", filter=Q(kind="secondary")),
        custom=Count("id", filter=Q(kind="primary", type="custom")),
        ready_made=Count("id", filter=Q(kind="primary", type="ready_made")),
    )

    if f.kind == MATERIALS:
        queryset = (
            active.filter(kind="secondary")
            .order_by("name")
            .prefetch_related(
                Prefetch(
                    "used_by_options",
                    queryset=ProductOption.objects.filter(product__active=True)
                    .select_related("product")
                    .order_by("product__name", "position"),
                    to_attr="active_uses",
                )
            )
        )
    else:
        queryset = active.filter(kind="primary")
        if f.type:
            queryset = queryset.filter(type=f.type)
        queryset = queryset.order_by("type", "name").prefetch_related("options")
    if f.q:
        queryset = queryset.filter(name__icontains=f.q)

    if f.kind == MATERIALS:
        rows = [
            {
                "material": m,
                "edit_url": reverse("product_edit", args=[m.pk]),
                "uses": uses_summary(
                    [(o.name, o.product_id, o.product.name) for o in m.active_uses]
                ),
            }
            for m in queryset
        ]
    else:
        rows = [
            {
                "product": p,
                "edit_url": reverse("product_edit", args=[p.pk]),
                "summary": options_summary([o.name for o in p.options.all()]),
            }
            for p in queryset
        ]

    segments = [
        {
            "id": f"seg-{kind}",
            "label": label,
            "count": counts[kind],
            "url": filter_url(base, ListFilter(kind)),
            "selected": f.kind == kind,
        }
        for kind, label in ((SOLD, "Sold"), (MATERIALS, "Materials"))
    ]
    chips = []
    if f.kind == SOLD:
        chips = [
            {
                "id": f"chip-{type_ or 'all'}",
                "label": label,
                "count": counts[key],
                "url": filter_url(base, ListFilter(SOLD, type_, f.q)),
                "selected": f.type == type_,
            }
            for type_, label, key in (
                ("", "All", "sold"),
                ("custom", "Custom", "custom"),
                ("ready_made", "Ready-made", "ready_made"),
            )
        ]

    add_url = reverse("product_add") + (
        "?kind=secondary" if f.kind == MATERIALS else ""
    )
    joiner = "&" if "?" in add_url else "?"
    add_named_url = f"{add_url}{joiner}{urlencode({'name': f.q})}"

    return render_page(
        request,
        "catalog/products.html",
        {
            "title": "Products",
            "tab": "products",
            "filter": f,
            "counts": counts,
            "segments": segments,
            "chips": chips,
            "rows": rows,
            "base_url": base,
            "add_url": add_url,
            "add_named_url": add_named_url,
            "open_add": request.GET.get("add") == "1",
        },
    )


def _list_path(kind: str) -> str:
    sheet_kind = MATERIALS if kind == Product.SECONDARY else SOLD
    return filter_url(reverse("products"), ListFilter(sheet_kind))


def _subtitle(product: Product | None) -> str | None:
    if product is None:
        return None
    if product.kind == Product.SECONDARY:
        options = (
            product.used_by_options.filter(product__active=True)
            .select_related("product")
            .order_by("product__name", "position")
        )
        return material_used_by([(o.name, o.product.name) for o in options])
    return "Changes apply to new orders only."


@owner_required
def product_sheet(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    instance = get_object_or_404(Product, pk=pk, active=True) if pk else None
    data = request.POST if request.method == "POST" else request.GET
    kind = data.get("kind") or (instance.kind if instance else Product.PRIMARY)
    if kind not in (Product.PRIMARY, Product.SECONDARY):
        kind = Product.PRIMARY
    material = kind == Product.SECONDARY
    form_class = MaterialForm if material else ProductForm
    status = 200
    if request.method == "POST":
        form = form_class(request.POST, instance=instance)
        if form.is_valid():
            product = form.save()
            verb = "saved" if instance else "added"
            return sheet_saved_location(
                _list_path(product.kind), f"{product.name} {verb}"
            )
        status = 422
    else:
        initial = {"kind": kind}
        if "name" in request.GET:
            initial["name"] = request.GET["name"].strip()[:80]
        form = form_class(instance=instance, initial=initial)
    template = (
        "catalog/material_sheet.html" if material else "catalog/product_sheet.html"
    )
    context = {
        "form": form,
        "product": instance,
        "action": request.path,
        "subtitle": _subtitle(instance),
    }
    return render(request, template, context, status=status)


@owner_required
@require_POST
def product_remove(request: HttpRequest, pk: int) -> HttpResponse:
    product = get_object_or_404(Product, pk=pk, active=True)
    product.active = False
    product.save(update_fields=["active"])
    return sheet_saved_location(_list_path(product.kind), f"{product.name} removed")
