import re
from datetime import date, timedelta
from decimal import Decimal as D

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from customers.models import Customer
from orders.models import MaterialLine, Order, OrderItem, Rework
from orders.tests.conftest import make_employee, make_order
from production.models import TimeSession
from reports.models import ShopBill, ShopSettings
from staff.models import Payout

URL = "/reports/profit/"


def get(client, query=""):
    return client.get(URL + query).content.decode()


def text(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def finish(order):
    OrderItem.objects.filter(order=order).update(status=OrderItem.FINISHED)


def material(item=None, rework=None, cost="50", selling="0", on_bill=False):
    MaterialLine.objects.create(
        item=item,
        rework=rework,
        name="Lining",
        unit="m",
        quantity=D(1),
        cost_price=D(cost),
        selling_price=D(selling),
        on_bill=on_bill,
    )


def session(employee, *, item=None, rework=None, minutes=120):
    end = timezone.now() - timedelta(minutes=5)
    TimeSession.objects.create(
        employee=employee,
        item=item,
        rework=rework,
        started_at=end - timedelta(minutes=minutes),
        ended_at=end,
    )


@pytest.fixture
def ali(db):
    _, employee = make_employee("9000000002", "ali")
    employee.daily_wage = D(800)  # Rs 100 an hour
    employee.save()
    return employee


@pytest.fixture
def shop(db, ali):
    """A paid order, a free order, a rework, payouts and bills in and out of period."""
    asha = Customer.objects.create(name="Asha Rao", phone="9000000011")
    paid = make_order(asha, 1, price="1500")
    paid.assignee = ali
    paid.save()
    item = paid.items.get()
    session(ali, item=item, minutes=120)  # staff 200
    material(item=item, cost="60", selling="90", on_bill=True)  # cost 60, billed 90
    finish(paid)
    free = make_order(
        Customer.objects.create(name="Bina", phone="9000000012"), 2, free=True
    )
    material(item=free.items.get(), cost="50")
    session(ali, item=free.items.get(), minutes=60)  # staff 100
    finish(free)
    rework = Rework.objects.create(
        item=item, reason=Rework.FIT, assignee=ali, finished_at=timezone.now()
    )
    session(ali, rework=rework, minutes=60)  # staff 100
    material(rework=rework, cost="40")
    today = timezone.localdate()
    old = today - timedelta(days=90)
    Payout.objects.create(
        employee=ali,
        week_start=today,
        paid_on=today,
        method="cash",
        amount=D(500),
        days=1,
        daily_wage=D(800),
        base_total=D(500),
        overtime_minutes=0,
        overtime_multiplier=D(1),
        overtime_total=D(0),
        calculated_total=D(500),
    )
    Payout.objects.create(
        employee=ali,
        week_start=old,
        paid_on=old,
        method="cash",
        amount=D(999),
        days=1,
        daily_wage=D(800),
        base_total=D(999),
        overtime_minutes=0,
        overtime_multiplier=D(1),
        overtime_total=D(0),
        calculated_total=D(999),
    )
    ShopBill.objects.create(name="Rent", amount=D(700), date=today)
    ShopBill.objects.create(name="Old rent", amount=D(888), date=old)
    return {"paid": paid, "free": free, "customer": asha}


def test_profit_chip_shows_on_sales(owner_client):
    html = owner_client.get("/reports/sales/").content.decode()
    assert 'href="/reports/profit/?period=month"' in html


def test_shop_profit_figures(owner_client, shop):
    card = text(get(owner_client).split('id="shop-profit"')[1].split("</section>")[0])
    # Sales 1590 (1500 + billed lining 90); materials 60 + 50 free + 40 rework.
    assert "Sales ₹1,590" in card
    assert "Materials −₹150" in card
    assert "Staff pay −₹500" in card
    assert "Shop bills −₹700" in card
    assert "Profit ₹240" in card
    # Logged staff 200 + 100 free + 100 rework: 100 of pay is not logged.
    assert "₹100 of pay wasn&#x27;t logged to an order" in card


def test_running_costs_do_not_change_profit(owner_client, shop):
    def figures():
        html = get(owner_client)
        card = text(html.split('id="shop-profit"')[1].split("</section>")[0])
        free = text(html.split('id="free-work"')[1].split("</li>")[0])
        return card, free

    before_card, before_free = figures()
    ShopSettings.objects.create(
        pk=1, running_costs=[{"name": "Rent", "amount": "20800"}]
    )
    after_card, after_free = figures()
    assert after_card == before_card
    assert after_free != before_free


def test_free_order_not_in_sales_but_in_free_work(owner_client, shop):
    html = get(owner_client)
    free = text(html.split('id="free-work"')[1].split("</li>")[0])
    assert "1 order · usual price ₹1,000 not charged" in free
    assert "₹150 cost" in free  # materials 50 + staff 100, no running rate
    assert 'href="/orders/?show=free"' in html
    assert "Sales ₹1,590" in text(html)


def test_reworks_line(owner_client, shop):
    html = get(owner_client)
    line = text(html.split('id="reworks"')[1].split("</li>")[0])
    assert "1 rework · 60 min" in line
    assert "₹140" in line  # staff 100 + materials 40
    assert "Reworks: staff ₹100, materials ₹40, never invoiced." in html


def test_empty_lines_read_none_in_month(owner_client):
    html = get(owner_client)
    month = f"None in {timezone.localdate():%B %Y}"
    assert text(html.split('id="free-work"')[1].split("</li>")[0]).count(month) == 1
    assert text(html.split('id="reworks"')[1].split("</li>")[0]).count(month) == 1
    assert month in html.split('id="shop-bills"')[1]
    assert "No sales in" in html
    assert 'id="free-caption"' not in html


def test_custom_period_none_text(owner_client):
    html = get(owner_client, "?period=custom&from=2026-01-01&to=2026-01-07")
    assert "None in 1–7 Jan" in html


def test_add_bill_saves_and_shows(owner_client):
    today = timezone.localdate()
    response = owner_client.post(
        "/reports/profit/bills/new/?period=month",
        {"name": "Electricity", "amount": "1800", "date": today.isoformat()},
    )
    assert response.status_code == 204
    assert "/reports/profit/?period=month" in response["HX-Location"]
    html = get(owner_client)
    bills = text(html.split('id="shop-bills"')[1])
    assert "Electricity" in bills
    assert "₹1,800" in bills
    assert "Shop bills −₹1,800" in text(html)


def test_add_bill_sheet_renders(owner_client):
    html = owner_client.get("/reports/profit/bills/new/?period=month").content.decode()
    assert "Add bill" in html
    assert 'hx-post="/reports/profit/bills/new/?period=month"' in html


@pytest.mark.parametrize(
    "data",
    [
        {"name": "Rent", "amount": "-5", "date": "2026-11-01"},
        {"name": "", "amount": "5", "date": "2026-11-01"},
        {"name": "Rent", "amount": "abc", "date": "2026-11-01"},
        {"name": "x" * 61, "amount": "5", "date": "2026-11-01"},
        {"name": "Rent", "amount": "5", "date": "not a date"},
    ],
)
def test_add_bill_invalid_422(owner_client, data):
    response = owner_client.post("/reports/profit/bills/new/", data)
    assert response.status_code == 422
    assert "fixing before you can save this bill" in response.content.decode()
    assert not ShopBill.objects.exists()


def test_add_bill_negative_message(owner_client):
    response = owner_client.post(
        "/reports/profit/bills/new/",
        {"name": "Rent", "amount": "-5", "date": "2026-11-01"},
    )
    assert "greater than or equal to 0" in response.content.decode()


def test_shopbill_check_constraint(db):
    with pytest.raises(IntegrityError), transaction.atomic():
        ShopBill.objects.create(name="Bad", amount=D(-1), date=timezone.localdate())


def test_bill_outside_period_not_listed(owner_client):
    ShopBill.objects.create(
        name="Old rent", amount=D(5), date=timezone.localdate() - timedelta(days=90)
    )
    assert "Old rent" not in get(owner_client)


def test_profit_by_customer_and_sale(owner_client, shop):
    html = get(owner_client)
    rows = html.split('id="profit-rows"')[1]
    assert f'href="/customers/{shop["customer"].pk}/"' in rows
    assert "Asha Rao" in rows
    assert "Bina" not in rows  # free orders are not in Profit by
    # 1590 sale - 60 materials - 200 staff.
    assert "₹1,330" in text(rows)
    assert "1 order · sales ₹1,590" in text(rows)
    sale = get(owner_client, "?period=month&by=sale")
    rows = sale.split('id="profit-rows"')[1]
    assert f'href="/orders/{shop["paid"].pk}/"' in rows
    assert "#1 Asha Rao" in rows
    assert 'name="by" value="sale"' in sale
    assert "by=sale" in sale


def test_draft_orders_are_left_out(owner_client, shop):
    make_order(shop["customer"], 9, status="draft", price="777")
    assert "777" not in get(owner_client)


def test_requires_owner(client, db):
    from django.contrib.auth.models import User

    client.force_login(User.objects.create_user("emp", password="x"))
    assert client.get(URL).status_code == 302
    assert client.get("/reports/profit/bills/new/").status_code == 302


def test_order_status_untouched():
    assert Order.OPEN


def test_unfinished_unlogged_item_profit_ignores_estimate(owner_client, ali):
    """The estimate counts in staff costs shown elsewhere, never in profit."""
    order = make_order(
        Customer.objects.create(name="Chitra", phone="9000000013"), 5, price="1000"
    )
    order.assignee = ali
    order.save()
    OrderItem.objects.filter(order=order).update(estimate_minutes=60)
    html = get(owner_client)
    rows = text(html.split('id="profit-rows"')[1])
    assert "Chitra" in rows and "₹1,000" in rows
    assert "₹900" not in rows
    # No pay logged, so no unlogged-pay sentence and no phantom logged cost.
    assert "wasn&#x27;t logged" not in html


def test_reworks_link_opens_all_orders(owner_client, shop):
    assert 'href="/orders/?show=all"' in get(owner_client)


GARMENT = "?by=garment"


@pytest.fixture
def garments_shop(db, ali):
    """Two Blouses (one free) and a ready-made Kurta, all placed this month."""
    asha = Customer.objects.create(name="Asha Rao", phone="9000000011")
    paid = make_order(asha, 1, price="1600")
    paid.assignee = ali
    paid.save()
    session(ali, item=paid.items.get(), minutes=120)  # staff 200
    finish(paid)
    free = make_order(asha, 2, free=True, price="1600")
    free.assignee = ali
    free.save()
    session(ali, item=free.items.get(), minutes=120)
    finish(free)
    kurta = make_order(asha, 3)
    OrderItem.objects.filter(order=kurta).update(
        name="Kurta", type="ready_made", price=D(799)
    )


def save_rent(amount="9500"):
    ShopSettings.objects.create(
        pk=1, running_costs=[{"name": "Rent", "amount": amount}]
    )


def test_garment_view_lists_garments(owner_client, garments_shop):
    save_rent()
    html = get(owner_client, GARMENT)
    page = text(html)
    assert 'id="shop-profit"' not in html
    assert 'id="running-card"' in html
    assert "Blouse ×2" in page
    assert "Kurta ×1" in page
    # Blouse: price 800 average; staff 200, running 92 each; gain (1308 - 292) / 2
    assert (
        "Average price ₹800 · cost ₹292: staff ₹200, materials ₹0, running ₹92" in page
    )
    assert "₹508 · 64%" in page
    assert "Average price ₹799 · cost ₹0" in page
    assert "₹799 · 100%" in page
    assert 'href="/orders/?show=all"' in html


def test_garment_view_without_running_costs(owner_client, garments_shop):
    html = get(owner_client, GARMENT)
    page = text(html)
    assert (
        "Add your monthly running costs to see the full cost of each garment." in page
    )
    assert re.search(r'id="running-edit"[^>]*>\s*Add\s*<', html)
    assert 'id="no-rate-note"' in html
    assert "running ₹0" in page


def test_garment_view_with_running_costs(owner_client, garments_shop):
    save_rent()
    html = get(owner_client, GARMENT)
    page = text(html)
    assert "₹46 an hour of work" in page
    assert re.search(r'id="running-edit"[^>]*>\s*Edit\s*<', html)
    assert "no-rate-note" not in html


def test_period_form_keeps_garment(owner_client, db):
    assert 'name="by" value="garment"' in get(owner_client, GARMENT)


def bills_for_prefill():
    today = timezone.localdate()
    for back, amount in ((3, 9000), (2, 9600), (1, 9900)):
        index = today.year * 12 + today.month - 1 - back
        day = date(index // 12, index % 12 + 1, 5)
        ShopBill.objects.create(name="Rent", amount=D(amount), date=day)
    ShopBill.objects.create(name="Big", amount=D(50000), date=today)


def test_running_costs_prefilled_from_bills(owner_client, db):
    bills_for_prefill()
    html = owner_client.get("/settings/running-costs/?sheet=1").content.decode()
    assert re.search(r'value="Other"', html)
    assert 'value="9500"' in html
    assert "₹9,500 a month" in text(html)


def test_running_costs_not_prefilled_once_saved(owner_client, db):
    bills_for_prefill()
    ShopSettings.objects.create(pk=1, running_costs=[])
    html = owner_client.get("/settings/running-costs/?sheet=1").content.decode()
    assert 'value="Other"' not in html


def post_sheet(client, query):
    return client.post(
        "/settings/running-costs/" + query,
        {
            "cost_name": ["Rent"],
            "cost_amount": ["9500"],
            "cost_fixed": [""],
            "hours": "208",
        },
        HTTP_HX_REQUEST="true",
    )


def test_sheet_save_with_next_reloads_profit(owner_client, db):
    response = post_sheet(owner_client, "?sheet=1&next=/reports/profit/%3Fby%3Dgarment")
    assert response.status_code == 204
    assert "/reports/profit/?by=garment" in response["HX-Location"]


def test_sheet_save_ignores_foreign_next(owner_client, db):
    response = post_sheet(owner_client, "?sheet=1&next=https://example.com/")
    assert response["HX-Reswap"] == "none"
    assert "HX-Location" not in response
