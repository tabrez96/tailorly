from decimal import Decimal
from urllib.parse import urlencode

from django.db.models.functions import Lower
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from accounts.decorators import owner_required
from core.pages import render_page, sheet_saved_location
from customers.forms import CustomerForm
from customers.listing import add_initial, parse_query, search_filter
from customers.models import Customer
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
            "new_order_url": f"/orders/new/?customer={c.pk}",
        },
    )
