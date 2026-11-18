from django.db.models import Count, Prefetch, Q
from django.http import HttpRequest, HttpResponse
from django.urls import reverse

from accounts.decorators import owner_required
from catalog.listing import (
    MATERIALS,
    SOLD,
    ListFilter,
    filter_url,
    options_summary,
    parse_filter,
    uses_summary,
)
from catalog.models import Product, ProductOption
from core.pages import render_page


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
        },
    )
