from urllib.parse import urlencode

from django.db.models import Count, Prefetch, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
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


def _materials(instance: Product | None) -> list[Product]:
    """Active materials, plus any inactive one an option of this product still uses."""
    q = Q(active=True)
    if instance:
        q |= Q(used_by_options__product=instance)
    return list(
        Product.objects.filter(q, kind=Product.SECONDARY).distinct().order_by("name")
    )


@owner_required
def product_sheet(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    instance = get_object_or_404(Product, pk=pk, active=True) if pk else None
    data = request.POST if request.method == "POST" else request.GET
    kind = data.get("kind") or (instance.kind if instance else Product.PRIMARY)
    if kind not in (Product.PRIMARY, Product.SECONDARY):
        kind = Product.PRIMARY
    material = kind == Product.SECONDARY
    form_class = MaterialForm if material else ProductForm
    kwargs = {"materials": _materials(instance)} if form_class is ProductForm else {}
    return_to = data.get("return_to", "")
    if not (
        return_to.startswith("/orders/")
        and url_has_allowed_host_and_scheme(
            return_to, allowed_hosts={request.get_host()}
        )
    ):
        return_to = ""
    status = 200
    if request.method == "POST":
        form = form_class(request.POST, instance=instance, **kwargs)
        if form.is_valid():
            product = form.save()
            verb = "saved" if instance else "added"
            if instance is None and material and return_to:
                joiner = "&" if "?" in return_to else "?"
                return redirect(f"{return_to}{joiner}material={product.pk}")
            return sheet_saved_location(
                _list_path(product.kind), f"{product.name} {verb}"
            )
        status = 422
    else:
        initial = {"kind": kind}
        if "name" in request.GET:
            initial["name"] = request.GET["name"].strip()[:80]
        form = form_class(instance=instance, initial=initial, **kwargs)
    template = (
        "catalog/material_sheet.html" if material else "catalog/product_sheet.html"
    )
    context = {
        "form": form,
        "product": instance,
        "action": request.path,
        "subtitle": _subtitle(instance),
        "return_to": return_to,
    }
    return render(request, template, context, status=status)


@owner_required
@require_POST
def product_remove(request: HttpRequest, pk: int) -> HttpResponse:
    product = get_object_or_404(Product, pk=pk, active=True)
    product.active = False
    product.save(update_fields=["active"])
    return sheet_saved_location(_list_path(product.kind), f"{product.name} removed")
