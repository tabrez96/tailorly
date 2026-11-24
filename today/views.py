from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from accounts.decorators import owner_required
from core.pages import render_page
from production.report import week_so_far
from production.timing import close_stale, stop
from staff.attendance import end_day, start_day
from staff.models import Employee
from today import cards


@owner_required
@require_GET
def today(request):
    now = timezone.now()
    day = timezone.localdate(now)
    week = week_so_far(now)
    return render_page(
        request,
        "today/today.html",
        {
            "title": "Today",
            "tab": "today",
            "overline": cards.overline(now, request.user.first_name),
            "gear_url": cards.settings_url(),
            "heroes": cards.hero_cards(now),
            "now": now,
            "plan": cards.work_plan_card(now),
            "week": week,
            "late_label": f"{week['late']} late",
            "report_url": reverse("production_report") + "?from=today",
            "due": cards.due_rows(day),
            "money": cards.money(day),
            "pay": cards.staff_pay(day),
        },
    )


def _hero(request, now):
    return render(
        request, "today/_hero.html", {"heroes": cards.hero_cards(now), "now": now}
    )


@owner_required
@require_GET
def today_hero(request):
    return _hero(request, timezone.now())


@owner_required
@require_POST
def today_start_day(request, pk):
    employee = get_object_or_404(Employee, pk=pk, active=True)
    now = timezone.now()
    close_stale(employee, now)
    start_day(employee, now)  # the same code as Start day on S12
    return _hero(request, now)


@owner_required
@require_POST
def today_end_day(request, pk):
    employee = get_object_or_404(Employee, pk=pk, active=True)
    now = timezone.now()
    stop(employee, now)
    end_day(employee, now, by_owner=True)  # the same code as End day on S10
    return _hero(request, now)
