from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

from accounts.decorators import owner_required
from core.forms_ui import error_summary_text
from core.pages import page_location, render_page, sheet_saved
from reports import costing
from reports import running_costs as form
from reports.models import ShopSettings


def _redirect_303(path):
    response = HttpResponseRedirect(path)
    response.status_code = 303
    return response


@owner_required
def running_costs(request):
    """The running costs sheet (?sheet=1, from S11), or the same form as a page."""
    sheet = request.GET.get("sheet") == "1"
    saved = ShopSettings.current()
    status, errors = 200, 0
    if request.method == "POST":
        lines, rows = form.parse(
            request.POST.getlist("cost_name"),
            request.POST.getlist("cost_amount"),
            request.POST.getlist("cost_fixed"),
        )
        hours, hours_error = form.parse_hours(request.POST.get("hours", ""))
        errors = sum(1 for r in rows if r.error) + (1 if hours_error else 0)
        if not errors:
            saved.running_costs, saved.working_hours = lines, hours
            saved.save()
            if sheet:
                return sheet_saved(HttpResponse(""), "Running costs saved")
            if request.headers.get("HX-Request"):
                return page_location(reverse("running_costs"), "Running costs saved")
            return _redirect_303(reverse("running_costs"))
        status = 422
        hours_text = request.POST.get("hours", "")
        total = costing.monthly_total(lines)
    else:
        rows = form.rows_for(saved.running_costs)
        hours, hours_error, hours_text = None, "", str(saved.working_hours)
        total = saved.monthly_total()
    context = {
        "rows": rows,
        "hours": hours_text,
        "hours_error": hours_error,
        "total": total,
        "rate": costing.running_rate(total, hours or saved.working_hours),
        "action": request.path + ("?sheet=1" if sheet else ""),
        "sheet": sheet,
        "error_text": error_summary_text(errors, "save running costs")
        if errors
        else "",
    }
    if sheet:
        return render(
            request, "reports/running_costs_sheet.html", context, status=status
        )
    return render_page(
        request,
        "reports/running_costs.html",
        {
            **context,
            "title": "Running costs",
            "subpage": True,
            "back_url": reverse("today"),
        },
        status=status,
    )
