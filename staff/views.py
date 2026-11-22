import json
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import IntegrityError, transaction
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import employee_required, owner_required
from core.formats import format_day
from core.pages import render_page, sheet_saved_swap
from production.timing import close_stale, stop
from production.views import panel_response
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
from staff.forms import DayForm, EmployeeForm, PayoutForm
from staff.models import Employee, Payout
from staff.pay import pay_day, payout_summary, short_period, week_pay

STAFF_URL = "/settings/staff/"
STAFF_BACK = "/"  # S18 Settings once it exists


def _records(employee, monday):
    return {
        r.date: r
        for r in employee.days.filter(date__range=(monday, week_days(monday)[-1]))
    }


def _week(employee, monday, today):
    records = {d: (r.start, r.end) for d, r in _records(employee, monday).items()}
    return week_pay(
        monday, records, employee.daily_wage, employee.overtime_multiplier, today
    )


def payout_rows(payouts):
    return [
        {
            "payout": p,
            "period": short_period(p.week_start),
            "summary": payout_summary(p.days, p.overtime_minutes),
        }
        for p in payouts
    ]


@employee_required
def my_pay(request):
    employee = _my_employee(request)
    today = timezone.localdate()
    monday = week_start(today)
    week = _week(employee, monday, today)
    records = _records(employee, monday)
    days = [
        {"pay": d, "record": records.get(d.date)} for d in week.days if d.date <= today
    ]
    payouts = payout_rows(employee.payouts.all())
    next_pay_day = pay_day(monday)
    payout = employee.payouts.filter(week_start=monday).first()
    return render_page(
        request,
        "staff/my_pay.html",
        {
            "title": "My pay",
            "tab": "my_pay",
            "week": week,
            "week_label": week_label(monday),
            "pay_day": next_pay_day,
            "payout": payout,
            "hourly": _hourly(employee, payout),
            "days": days,
            "payouts": payouts,
            "empty_text": (
                f"No payments yet. Your first pay day is {format_day(next_pay_day)}."
            ),
        },
    )


def _hourly(employee, payout):
    """Hourly rate for the overtime row: the stored wage once the week is paid."""
    return hourly_rate(payout.daily_wage if payout else employee.daily_wage)


def _days_context(employee, monday, today):
    records = _records(employee, monday)
    week = _week(employee, monday, today)
    payout = employee.payouts.filter(week_start=monday).first()
    return {
        "employee": employee,
        "today": today,
        "rows": [
            day_row(d, records.get(d), today) | {"pay": week.days[i]}
            for i, d in enumerate(week_days(monday))
        ],
        "week": week,
        "monday": monday,
        "hourly": _hourly(employee, payout),
        "payout": payout,
        "payouts": payout_rows(employee.payouts.all()),
        "can_pay": monday <= today,
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
            ctx["oob"] = True
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
        now = timezone.now()
        stop(employee, now)
        end_day(employee, now, by_owner=True)
    ctx = _days_context(employee, week_start(parsed), timezone.localdate())
    ctx["oob"] = True
    return render(request, "staff/_days.html", ctx)


@owner_required
def payout_sheet(request, pk, week):
    employee = get_object_or_404(Employee, pk=pk)
    today = timezone.localdate()
    try:
        monday = date.fromisoformat(week)
    except ValueError:
        raise Http404 from None
    if (
        monday.weekday() != 0
        or monday > today
        or employee.payouts.filter(week_start=monday).exists()
    ):
        raise Http404
    week_data = _week(employee, monday, today)
    form = PayoutForm(
        request.POST or None,
        initial={
            "amount": str(week_data.total.quantize(Decimal(1), ROUND_HALF_UP)),
            "paid_on": min(pay_day(monday), today),
            "method": Payout.CASH,
        },
    )
    status = 200
    if request.method == "POST":
        if form.is_valid():
            try:
                with transaction.atomic():
                    week_data = _week(employee, monday, today)
                    Payout.objects.create(
                        employee=employee,
                        week_start=monday,
                        paid_on=form.cleaned_data["paid_on"],
                        method=form.cleaned_data["method"],
                        amount=form.cleaned_data["amount"],
                        days=week_data.days_paid,
                        daily_wage=week_data.daily_wage,
                        base_total=week_data.base_total,
                        overtime_minutes=week_data.overtime_minutes,
                        overtime_multiplier=week_data.multiplier,
                        overtime_total=week_data.overtime_total,
                        calculated_total=week_data.total,
                    )
            except IntegrityError:
                form.add_error(None, "This week is already paid.")
            else:
                return sheet_saved_swap(
                    render(
                        request,
                        "staff/_payout_saved.html",
                        _days_context(employee, monday, today),
                    ),
                    "Payout saved",
                    "#staff-total",
                )
        status = 422
    return render(
        request,
        "staff/payout_sheet.html",
        {
            "employee": employee,
            "form": form,
            "monday": monday,
            "period": short_period(monday),
            "week": week_data,
        },
        status=status,
    )


def _my_employee(request):
    employee = getattr(request.user, "employee", None)
    if employee is None:
        raise Http404
    return employee


@employee_required
@require_POST
def start_my_day(request):
    now = timezone.now()
    employee = _my_employee(request)
    close_stale(employee, now)
    start_day(employee, now)
    return panel_response(request, employee)


@employee_required
@require_POST
def end_my_day(request):
    now = timezone.now()
    employee = _my_employee(request)
    stop(employee, now)
    end_day(employee, now)
    return panel_response(request, employee)
