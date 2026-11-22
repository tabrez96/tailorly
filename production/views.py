import json

from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from accounts.decorators import employee_required, owner_required
from core.formats import format_day
from core.pages import render_page, sheet_saved_location
from orders.models import Order, OrderItem, Rework
from production.assign import (
    NEXT,
    SUGGESTED,
    AssignError,
    _items,
    assign,
    assignable,
    read_estimates,
    sheet_context,
)
from production.details import details_context
from production.plan import plan_context
from production.timing import (
    TimingError,
    finish_item,
    finish_rework,
    my_items,
    my_reworks,
    panel,
    start_item,
    start_rework,
    stop,
)
from staff.attendance import day_card, first_name
from staff.models import Employee

NOT_STARTED = "Start your day first."


def _employee(request):
    employee = getattr(request.user, "employee", None)
    if employee is None:
        raise Http404
    return employee


def _context(employee, now) -> dict:
    if employee is None:
        return {
            "day": None,
            "hero": None,
            "up_next": [],
            "finished": [],
            "can_time": False,
            "running": False,
        }
    return panel(employee, now)


@employee_required
def my_work(request):
    now = timezone.now()
    return render_page(
        request,
        "production/my_work.html",
        {
            "title": "My work",
            "tab": "my_work",
            "overline": format_day(now).upper(),
            **_context(getattr(request.user, "employee", None), now),
        },
    )


def panel_response(request, employee, toast=None):
    response = render(
        request, "production/_panel.html", _context(employee, timezone.now())
    )
    if toast:
        response["HX-Trigger"] = json.dumps({"toast": {"message": toast}})
    return response


def _day_started(employee, now) -> bool:
    return day_card(employee, now)["state"] == "started"


@employee_required
@require_POST
def work_start(request, pk):
    employee = _employee(request)
    item = get_object_or_404(my_items(employee), pk=pk)
    now = timezone.now()
    if not _day_started(employee, now):
        return panel_response(request, employee, toast=NOT_STARTED)
    try:
        start_item(employee, item, now)
    except TimingError as error:
        return panel_response(request, employee, toast=str(error))
    return panel_response(request, employee)


@employee_required
@require_POST
def work_finish(request, pk):
    employee = _employee(request)
    item = get_object_or_404(my_items(employee), pk=pk)
    now = timezone.now()
    if not _day_started(employee, now):
        return panel_response(request, employee, toast=NOT_STARTED)
    try:
        finish_item(employee, item, now)
    except TimingError as error:
        return panel_response(request, employee, toast=str(error))
    return panel_response(request, employee, toast=f"{item.name} finished")


@employee_required
@require_POST
def work_pause(request):
    employee = _employee(request)
    now = timezone.now()
    if not _day_started(employee, now):
        return panel_response(request, employee, toast=NOT_STARTED)
    stop(employee, now)
    return panel_response(request, employee)


@employee_required
@require_POST
def rework_start(request, pk):
    employee = _employee(request)
    rework = get_object_or_404(my_reworks(employee), pk=pk)
    now = timezone.now()
    if not _day_started(employee, now):
        return panel_response(request, employee, toast=NOT_STARTED)
    try:
        start_rework(employee, rework, now)
    except TimingError as error:
        return panel_response(request, employee, toast=str(error))
    return panel_response(request, employee)


@employee_required
@require_POST
def rework_finish(request, pk):
    employee = _employee(request)
    rework = get_object_or_404(my_reworks(employee), pk=pk)
    now = timezone.now()
    if not _day_started(employee, now):
        return panel_response(request, employee, toast=NOT_STARTED)
    try:
        finish_rework(employee, rework, now)
    except TimingError as error:
        return panel_response(request, employee, toast=str(error))
    return panel_response(
        request, employee, toast=f"Rework · {rework.item.name} finished"
    )


@employee_required
@require_GET
def item_details(request, pk):
    employee = _employee(request)
    item = get_object_or_404(
        OrderItem.objects.select_related("order__customer", "product").prefetch_related(
            "photos"
        ),
        pk=pk,
        order__assignee=employee,
    )
    return render(request, "production/details_sheet.html", details_context(item))


@employee_required
@require_GET
def rework_details(request, pk):
    employee = _employee(request)
    rework = get_object_or_404(
        Rework.objects.select_related(
            "item__order__customer", "item__product"
        ).prefetch_related("item__photos"),
        pk=pk,
        assignee=employee,
    )
    return render(
        request,
        "production/details_sheet.html",
        details_context(rework.item, rework),
    )


@owner_required
@require_GET
def work_plan(request):
    try:
        back_url = reverse("production")
    except NoReverseMatch:  # the Production tab page isn't built yet
        back_url = reverse("today")
    context = plan_context(timezone.now())
    open_assign = ""
    if request.GET.get("assign") == "next" and context["assign_next_url"]:
        open_assign = context["assign_next_url"]
        employee = request.GET.get("employee", "")
        if employee.isdigit():
            open_assign += f"?employee={employee}"
    return render_page(
        request,
        "production/work_plan.html",
        {
            "title": "Work plan",
            "overline": "PRODUCTION",
            "tab": "production",
            "subpage": True,
            "back_url": back_url,
            "open_assign": open_assign,
            **context,
        },
    )


@owner_required
def assign_sheet(request, pk):
    order = get_object_or_404(
        Order.objects.select_related("customer", "assignee"), pk=pk
    )
    if not assignable(order):
        raise Http404
    data = request.POST if request.method == "POST" else request.GET
    back = "order" if data.get("from") == "order" else "plan"
    now = timezone.now()
    if request.method != "POST":
        return render(
            request,
            "production/assign_sheet.html",
            sheet_context(order, data, now, back=back),
        )
    employee = Employee.objects.filter(
        active=True, pk=data["employee"] if data.get("employee", "").isdigit() else 0
    ).first()
    place = data.get("place") if data.get("place") in (SUGGESTED, NEXT) else SUGGESTED
    estimates, errors = read_estimates(_items(order), data)
    error = "" if employee else "Choose who makes it."
    if employee and not errors:
        try:
            assign(order, employee, estimates, place, now)
        except AssignError as exc:
            error = str(exc)
        else:
            path = (
                reverse("order", args=[order.pk])
                if back == "order"
                else reverse("work_plan")
            )
            return sheet_saved_location(
                path, f"#{order.number} assigned to {first_name(employee.name)}"
            )
    return render(
        request,
        "production/assign_sheet.html",
        sheet_context(order, data, now, back=back, errors=errors, error=error),
        status=422,
    )
