import json
from datetime import date, timedelta

from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import employee_required, owner_required
from core.pages import render_page, sheet_saved_swap
from production.views import my_work
from staff.attendance import (
    day_row,
    end_day,
    hourly_rate,
    parse_week,
    save_day,
    start_day,
    week_days,
    week_label,
    week_start,
)
from staff.forms import DayForm, EmployeeForm
from staff.models import Employee

STAFF_URL = "/settings/staff/"
STAFF_BACK = "/"  # S18 Settings once it exists


@employee_required
def my_pay(request):
    return render_page(
        request, "staff/my_pay.html", {"title": "My pay", "tab": "my_pay"}
    )


def _days_context(employee, monday, today):
    records = {
        r.date: r
        for r in employee.days.filter(date__range=(monday, week_days(monday)[-1]))
    }
    return {
        "employee": employee,
        "today": today,
        "rows": [day_row(d, records.get(d), today) for d in week_days(monday)],
    }


def _staff_url(employee, monday):
    return f"{STAFF_URL}?e={employee.pk}&week={monday.isoformat()}"


@owner_required
def staff(request):
    employees = list(Employee.objects.filter(active=True))
    today = timezone.localdate()
    ctx = {
        "title": "Staff",
        "back_url": STAFF_BACK,
        "subpage": True,
        "employees": employees,
    }
    if employees:
        selected = next(
            (e for e in employees if str(e.pk) == request.GET.get("e")), employees[0]
        )
        monday = parse_week(request.GET.get("week"), today)
        ctx |= _days_context(selected, monday, today) | {
            "hourly": hourly_rate(selected.daily_wage),
            "week_label": week_label(monday),
            "prev_url": _staff_url(selected, monday - timedelta(days=7)),
            "next_url": _staff_url(selected, monday + timedelta(days=7)),
            "chips": (
                [
                    {
                        "label": e.name,
                        "url": _staff_url(e, monday),
                        "selected": e == selected,
                    }
                    for e in employees
                ]
                if len(employees) > 1
                else []
            ),
        }
    return render_page(request, "staff/staff.html", ctx)


def _employee_form(request, instance):
    form = EmployeeForm(request.POST or None, request.FILES or None, instance=instance)
    status = 200
    if request.method == "POST":
        if form.is_valid():
            employee = form.save()
            path = f"{STAFF_URL}?e={employee.pk}"
            if request.headers.get("HX-Request"):
                response = HttpResponse(status=204)
                response["HX-Location"] = json.dumps({"path": path, "target": "#page"})
                return response
            return redirect(path)
        status = 422
    return render_page(
        request,
        "staff/employee_form.html",
        {
            "title": instance.name if instance else "Add employee",
            "back_url": STAFF_URL,
            "subpage": True,
            "form": form,
            "is_add": instance is None,
            "action": request.path,
        },
        status=status,
    )


@owner_required
def employee_add(request):
    return _employee_form(request, None)


@owner_required
def employee_edit(request, pk):
    return _employee_form(request, get_object_or_404(Employee, pk=pk))


@owner_required
def employee_photo(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if not employee.photo:
        raise Http404
    try:
        photo = employee.photo.open("rb")
    except FileNotFoundError:
        raise Http404 from None
    response = FileResponse(photo, content_type="image/jpeg")
    response["Cache-Control"] = "private, max-age=3600"
    return response


def _past_day(day: str) -> date:
    try:
        parsed = date.fromisoformat(day)
    except ValueError:
        raise Http404 from None
    if parsed > timezone.localdate():
        raise Http404
    return parsed


@owner_required
def day_sheet(request, pk, day):
    employee = get_object_or_404(Employee, pk=pk)
    parsed = _past_day(day)
    record = employee.days.filter(date=parsed).first()
    form = DayForm(
        request.POST or None,
        initial={
            "start": timezone.localtime(record.start).time()
            if record
            else (
                timezone.localtime().time().replace(second=0, microsecond=0)
                if parsed == timezone.localdate()
                else None
            ),
            "end": timezone.localtime(record.end).time()
            if record and record.end
            else None,
        },
    )
    status = 200
    if request.method == "POST":
        if form.is_valid():
            save_day(
                employee, parsed, form.cleaned_data["start"], form.cleaned_data["end"]
            )
            ctx = _days_context(employee, week_start(parsed), timezone.localdate())
            return sheet_saved_swap(
                render(request, "staff/_days.html", ctx), "Day saved", "#staff-days"
            )
        status = 422
    return render(
        request,
        "staff/day_sheet.html",
        {"form": form, "employee": employee, "day": parsed},
        status=status,
    )


@owner_required
@require_POST
def day_end(request, pk, day):
    employee = get_object_or_404(Employee, pk=pk)
    parsed = _past_day(day)
    if parsed == timezone.localdate():
        end_day(employee, timezone.now(), by_owner=True)
    ctx = _days_context(employee, week_start(parsed), timezone.localdate())
    return render(request, "staff/_days.html", ctx)


def _my_employee(request):
    employee = getattr(request.user, "employee", None)
    if employee is None:
        raise Http404
    return employee


@employee_required
@require_POST
def start_my_day(request):
    start_day(_my_employee(request), timezone.now())
    return my_work(request)


@employee_required
@require_POST
def end_my_day(request):
    end_day(_my_employee(request), timezone.now())
    return my_work(request)
