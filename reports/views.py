from urllib.parse import urlencode

from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET

from accounts.decorators import owner_required
from core.forms_ui import error_summary_text
from core.pages import page_location, render_page, sheet_saved, sheet_saved_location
from core.reports import report_row
from reports import costing, garments, order_costs, payments, profit, sales
from reports import running_costs as form
from reports import staff_report as staff_report_mod
from reports.forms import ShopBillForm
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
    next_url = request.GET.get("next", "")
    if not (
        next_url.startswith(reverse("profit_report"))
        and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}
        )
    ):
        next_url = ""
    if request.method == "POST":
        lines, rows = form.parse(
            request.POST.getlist("cost_name"),
            request.POST.getlist("cost_amount"),
            request.POST.getlist("cost_fixed"),
        )
        hours, hours_error = form.parse_hours(request.POST.get("hours", ""))
        errors = sum(1 for r in rows if r.error) + (1 if hours_error else 0)
        if not errors:
            # Write only these fields so a stale read can't undo hold_tip_seen.
            ShopSettings.objects.update_or_create(
                pk=1,
                defaults={
                    "running_costs": lines,
                    "working_hours": hours,
                    "costs_saved": True,
                },
            )
            if sheet and next_url:
                return sheet_saved_location(next_url, "Running costs saved")
            if sheet:
                return sheet_saved(HttpResponse(""), "Running costs saved")
            if request.headers.get("HX-Request"):
                return page_location(reverse("running_costs"), "Running costs saved")
            return _redirect_303(reverse("running_costs"))
        status = 422
        hours_text = request.POST.get("hours", "")
        total = costing.monthly_total(lines)
    else:
        lines = saved.running_costs
        if not saved.costs_saved:  # never saved: start from the shop bills
            bills = order_costs.bill_months(timezone.localdate())
            lines = garments.prefill_lines(garments.bills_average(bills))
        rows = form.rows_for(lines)
        hours, hours_error, hours_text = None, "", str(saved.working_hours)
        total = costing.monthly_total(lines)
    context = {
        "rows": rows,
        "hours": hours_text,
        "hours_error": hours_error,
        "total": total,
        "rate": costing.running_rate(total, hours or saved.working_hours),
        "action": request.get_full_path() if sheet else request.path,
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
            "back_url": reverse("settings"),
        },
        status=status,
    )


@owner_required
@require_GET
def sales_report(request):
    return render_page(
        request,
        "reports/sales.html",
        sales.sales_context(request.GET, timezone.localdate()),
    )


def _profit_context(params, today, now) -> dict:
    period = sales.parse_period(params, today)
    by = params.get("by") if params.get("by") in ("sale", "garment") else "customer"
    first, last = period.first, period.last
    settings = ShopSettings.current()
    rate = settings.running_rate()
    period_orders = order_costs.period_orders(first, last)
    orders = [order_costs.figures(o, rate, now) for o in period_orders]
    reworks_total, rework_logged = order_costs.period_rework_total(first, last, now)
    bill_list = order_costs.bills(first, last)
    shop = profit.shop_profit(
        sales.summary(sales.load_sales(first, last))["total"],
        sum((o.materials for o in orders), sales.ZERO) + reworks_total.materials,
        order_costs.payouts_total(first, last),
        sum((b.amount for b in bill_list), sales.ZERO),
        sum((o.logged_staff for o in orders), sales.ZERO) + rework_logged,
    )
    free = profit.free_work(orders)
    reworks = profit.reworks_line(reworks_total)
    query = sales.period_query(period)
    sheet_query = params.urlencode()
    if by == "sale":
        rows = [
            r | {"url": reverse("order", args=[r["order_id"]])}
            for r in profit.by_sale(orders)
        ]
    elif by == "garment":
        # S03 has no garment filter yet, so this opens it unfiltered (All).
        pieces = order_costs.period_pieces(period_orders, rate, now)
        rows = [
            r | {"url": reverse("orders") + "?show=all"}
            for r in garments.rows(garments.by_garment(pieces))
        ]
    else:
        rows = [
            r | {"url": reverse("customer", args=[r["customer_id"]])}
            for r in profit.by_customer(orders)
        ]
    return {
        "title": "Reports",
        "subpage": True,
        "back_url": sales.back_url(),
        "report_row": report_row("profit_report", query),
        "period": period,
        "options": [
            {
                "value": k,
                "label": sales.option_label(k, today),
                "selected": k == period.key,
            }
            for k in sales.PERIODS
        ],
        "is_custom": period.key == sales.CUSTOM,
        "shop": shop,
        "note": profit.note(shop),
        "free": free,
        "reworks": reworks,
        "none_text": profit.none_text(period),
        "caption": profit.caption(free, reworks),
        "free_url": reverse("orders") + "?show=free",
        # S03 has no Rework filter yet, so this opens it unfiltered (All, not Open).
        "reworks_url": reverse("orders") + "?show=all",
        "segments": [
            {
                "id": f"by-{b}",
                "label": b.capitalize(),
                "url": f"{reverse('profit_report')}?{query}"
                + (f"&by={b}" if b != "customer" else ""),
                "selected": by == b,
            }
            for b in ("customer", "sale", "garment")
        ],
        "by": by,
        "rows": rows,
        "rows_empty_text": sales.empty_text(period),
        "run_card": garments.rate_card(
            settings.monthly_total(), settings.working_hours, rate
        ),
        "run_url": reverse("running_costs")
        + "?"
        + urlencode(
            {
                "sheet": "1",
                "next": reverse("profit_report") + "?" + params.urlencode(),
            }
        ),
        "garment_caption": garments.caption(period),
        "no_rate_note": garments.NO_RATE_NOTE if rate is None else "",
        "bills": bill_list,
        "bill_url": reverse("bill_new") + (f"?{sheet_query}" if sheet_query else ""),
    }


@owner_required
@require_GET
def profit_report(request):
    return render_page(
        request,
        "reports/profit.html",
        _profit_context(request.GET, timezone.localdate(), timezone.now()),
    )


@owner_required
def bill_new(request):
    form = ShopBillForm(request.POST or None, initial={"date": timezone.localdate()})
    if request.method == "POST" and form.is_valid():
        form.save()
        query = request.GET.urlencode()
        path = reverse("profit_report") + (f"?{query}" if query else "")
        return sheet_saved_location(path, "Bill saved")
    return render(
        request,
        "reports/bill_sheet.html",
        {"form": form, "action": request.get_full_path()},
        status=422 if request.method == "POST" else 200,
    )


@owner_required
@require_GET
def payments_report(request):
    return render_page(
        request,
        "reports/payments.html",
        payments.payments_context(request.GET, timezone.localdate()),
    )


@owner_required
@require_GET
def staff_report(request):
    return render_page(
        request,
        "reports/staff.html",
        staff_report_mod.staff_context(request.GET, timezone.now()),
    )
