import json

from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import employee_required
from core.formats import format_day
from core.pages import render_page
from production.timing import (
    TimingError,
    finish_item,
    my_items,
    panel,
    start_item,
    stop,
)
from staff.attendance import day_card

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
