from django.urls import reverse
from django.utils import timezone

from accounts.decorators import owner_required
from core.pages import render_page
from production.report import week_so_far


@owner_required
def today(request):
    week = week_so_far(timezone.now())
    return render_page(
        request,
        "today/today.html",
        {
            "title": "Today",
            "tab": "today",
            "week": week,
            "late_label": f"{week['late']} late",
            "report_url": reverse("production_report") + "?from=today",
        },
    )
