import re
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from assistants.models import AccessKey
from core.money import format_inr
from orders.models import Order, Payment
from reports.models import ShopSettings
from staff.attendance import week_start
from staff.models import DayRecord, Payout
from today import settings_rows


def page(client):
    return client.get("/settings/").content.decode()


def line(html, row_id):
    """The muted figure line of one row."""
    body = html[html.index(f'id="{row_id}"') :]
    return re.search(r'<p class="t-small muted">\s*(.*?)\s*</p>', body, re.S).group(1)


def test_owner_only(ali, client):
    assert ali.client.get("/settings/").status_code in (302, 403)
    response = client.get("/settings/")
    assert response.status_code == 302 and response["Location"].startswith("/sign-in/")


def test_rows_link_in_place(owner, ali):
    html = page(owner)
    expected = {
        "settings-sales": reverse("sales_report"),
        "settings-production": reverse("production_report") + "?from=settings",
        "settings-payments": reverse("payments_report"),
        "settings-staff-report": reverse("staff_report") + "?period=week",
        "settings-staff": reverse("staff"),
        "settings-running": reverse("running_costs"),
        "settings-password": reverse("change_password"),
    }
    for row_id, url in expected.items():
        tag = html[html.index(f'id="{row_id}"') :].split(">", 1)[0]
        assert f'href="{url}"' in tag, row_id
        assert 'hx-target="#page"' in tag and 'hx-push-url="true"' in tag, row_id


@pytest.fixture
def busy(owner, ali, make_item):
    """An invoiced and part-paid order, a finished one and a worked day."""
    today = timezone.localdate()
    item = make_item(ali, due=today + timedelta(days=1), price="1450")
    Payment.objects.create(
        order=item.order, amount=Decimal("500"), method="cash", date=today
    )
    DayRecord.objects.create(
        employee=ali,
        date=today,
        start=timezone.now() - timedelta(hours=11),
        end=timezone.now() - timedelta(minutes=1),
    )
    return item


def test_sales_figure_matches_report(owner, busy):
    Order.objects.update(status=Order.DELIVERED, delivered_at=timezone.now())
    total = owner.get(reverse("sales_report")).context["summary"]["total"]
    assert total > 0
    assert format_inr(total) in line(page(owner), "settings-sales")


def test_production_figure_matches_report(owner, busy):
    count = owner.get(reverse("production_report") + "?period=week").context["count"]
    assert line(page(owner), "settings-production") == (
        settings_rows.production_line(count)
    )


def test_payments_figure_matches_report(owner, busy):
    total = owner.get(reverse("payments_report")).context["collect"]["total"]
    assert total > 0
    assert line(page(owner), "settings-payments") == settings_rows.payments_line(total)


def test_staff_report_figure_matches_report(owner, busy):
    card = owner.get(reverse("staff_report") + "?period=week").context["cards"][0]
    assert card["overtime_minutes"] > 0
    assert line(page(owner), "settings-staff-report") == (
        settings_rows.staff_report_line(
            card["name"], card["worked"], card["overtime_minutes"]
        )
    )


def test_staff_chip_is_unpaid_week(owner, busy, ali):
    headline = owner.get(reverse("staff_report") + "?period=week").context["headline"][
        "line"
    ]
    amount = re.search(r"₹[\d,]+(?= due)", headline).group()
    assert f"{amount} to pay" in page(owner)
    Payout.objects.create(
        employee=ali,
        week_start=week_start(timezone.localdate()),
        paid_on=timezone.localdate(),
        method="cash",
        amount=1,
        days=1,
        daily_wage=800,
        base_total=800,
        overtime_minutes=0,
        overtime_multiplier=1.5,
        overtime_total=0,
        calculated_total=800,
    )
    assert "to pay" not in page(owner)


def test_running_costs_figure(owner):
    s = ShopSettings.current()
    s.running_costs = [{"name": "Rent", "amount": "9500"}]
    s.working_hours = 200
    s.save()
    s = ShopSettings.current()
    assert line(page(owner), "settings-running") == settings_rows.running_line(
        s.monthly_total(), s.running_rate()
    )
    assert "₹9,500 a month" in page(owner)


def test_first_run_texts(owner):
    html = page(owner)
    assert line(html, "settings-sales") == "No sales yet"
    assert line(html, "settings-production") == "Nothing finished yet"
    assert line(html, "settings-payments") == "Nothing to collect"
    assert line(html, "settings-staff-report") == "No employees yet"
    assert line(html, "settings-staff") == "Add your first employee"
    assert line(html, "settings-running") == "Not set yet"
    tag = html[html.index('id="settings-staff"') :].split(">", 1)[0]
    assert f'href="{reverse("employee_add")}"' in tag


def test_mcp_row_links_to_assistants(owner):
    html = page(owner)
    assert "MCP server" in html and line(html, "settings-mcp") == "Off"
    assert re.search(r'<a[^>]*id="settings-mcp"[^>]*href="/settings/assistants/"', html)


def test_mcp_row_on(owner):
    ShopSettings.objects.update_or_create(pk=1, defaults={"mcp_on": True})
    AccessKey.objects.create(name="Claude", prefix="abcd1234", key_hash="a" * 64)
    assert line(page(owner), "settings-mcp") == "On · 1 app connected · only read"


def test_account_section(owner, client):
    user = User.objects.get(username="owner")
    user.username = "9845000000"
    user.save()
    html = page(owner)
    assert "Sabreen" in html and "Owner · 98450 00000" in html
    form = html[html.index('<form method="post"') :].split("</form>", 1)[0]
    assert f'action="{reverse("sign_out")}"' in form and "csrfmiddlewaretoken" in form
    assert owner.post(reverse("sign_out")).status_code == 302
    assert owner.get("/settings/").status_code == 302


def test_version_shown(owner):
    assert settings_rows.app_version() in page(owner)


def test_back_buttons_go_to_settings(owner, ali):
    for url in (
        "/settings/staff/",
        reverse("running_costs"),
        reverse("production_report") + "?from=settings",
        reverse("sales_report"),
        reverse("payments_report"),
        reverse("staff_report"),
        reverse("change_password"),
    ):
        assert owner.get(url).context["back_url"] == "/settings/", url
    assert owner.get(reverse("profit_report")).context["back_url"] == "/settings/"
    assert ali.client.get(reverse("change_password")).context["back_url"] == "/my-work/"
