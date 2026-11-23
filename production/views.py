import json

from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from accounts.decorators import employee_required, owner_required
from catalog.models import Product
from core.formats import format_clock, format_day
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
from production.live import live_context
from production.plan import (
    clear_queue,
    parse_key,
    plan_context,
    save_move,
    section_context,
)
from production.record import item_record, rework_record
from production.timing import (
    TimingError,
    close_stale,
    finish_item,
    finish_rework,
    my_items,
    my_reworks,
    panel,
    start_item,
    start_rework,
    stop,
)
from staff.attendance import day_card, first_name, start_day
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
def production(request):
    now = timezone.now()
    return render_page(
        request,
        "production/production.html",
        {
            "title": "Production",
            "tab": "production",
            "overline": f"{format_day(now)} · {format_clock(now)}".upper(),
            "work_plan_url": reverse("work_plan"),
            **live_context(now),
        },
    )


@owner_required
@require_GET
def production_now(request):
    return render(request, "production/_right_now.html", live_context(timezone.now()))


@owner_required
@require_POST
def production_start_day(request, pk):
    employee = get_object_or_404(Employee, pk=pk, active=True)
    now = timezone.now()
    close_stale(employee, now)
    start_day(employee, now)  # the same DayRecord as Start my day on S08
    return render(request, "production/_right_now.html", live_context(now))


@owner_required
@require_GET
def work_plan(request):
    return _plan_page(request)


def _plan_page(request):
    back_url = reverse("production")
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
    back = data.get("from") if data.get("from") in ("order", "production") else "plan"
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
            path = {
                "order": reverse("order", args=[order.pk]),
                "production": reverse("production"),
            }.get(back, reverse("work_plan"))
            return sheet_saved_location(
                path, f"#{order.number} assigned to {first_name(employee.name)}"
            )
    return render(
        request,
        "production/assign_sheet.html",
        sheet_context(order, data, now, back=back, errors=errors, error=error),
        status=422,
    )


@owner_required
@require_POST
def queue_move(request, pk):
    employee = get_object_or_404(Employee, pk=pk, active=True)
    key = parse_key(request.POST.get("key", ""))
    to = request.POST.get("to", "")
    if key is None or not to.isdigit():
        return HttpResponseBadRequest()
    now = timezone.now()
    try:
        save_move(employee, key, int(to), now)
    except KeyError as error:
        raise Http404 from error
    return render(
        request, "production/_queue_moved.html", section_context(employee, now)
    )


@owner_required
@require_POST
def queue_reset(request, pk):
    employee = get_object_or_404(Employee, pk=pk, active=True)
    clear_queue(employee, timezone.now())
    return _plan_page(request)


NOTE_MAX = 500


@owner_required
@require_GET
def production_record(request, pk):
    item = get_object_or_404(
        OrderItem.objects.select_related(
            "order__customer", "order__assignee", "product"
        )
        .prefetch_related("photos", "sessions__employee", "reworks__sessions")
        .exclude(order__status=Order.DRAFT),
        pk=pk,
        type=Product.CUSTOM,
    )
    return render_page(
        request, "production/record.html", item_record(item, timezone.now())
    )


@owner_required
@require_GET
def rework_record_view(request, pk):
    rework = get_object_or_404(
        Rework.objects.select_related(
            "item__order__customer", "item__product", "assignee"
        ).prefetch_related("item__photos", "sessions__employee"),
        pk=pk,
    )
    return render_page(
        request, "production/record.html", rework_record(rework, timezone.now())
    )


@owner_required
@require_POST
def production_record_note(request, pk):
    item = get_object_or_404(OrderItem, pk=pk, status=OrderItem.FINISHED)
    note = request.POST.get("note", "").strip()
    block = {"url": reverse("production_record_note", args=[item.pk]), "value": note}
    if len(note) > NOTE_MAX:
        return render(
            request,
            "production/_record_note.html",
            {"note": block, "error": f"Keep it under {NOTE_MAX} characters."},
            status=422,
        )
    item.delay_note = note
    item.save(update_fields=["delay_note"])
    response = render(request, "production/_record_note.html", {"note": block})
    response["HX-Trigger"] = json.dumps({"toast": {"message": "Note saved"}})
    return response
