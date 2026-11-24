from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone

from customers.models import Customer
from orders.tests.conftest import make_order


def get(client, query=""):
    return client.get("/reports/sales/" + query)


def test_sales_requires_owner(client, db):
    client.force_login(User.objects.create_user("emp", password="x"))
    response = get(client)
    assert response.status_code == 302
    assert response["Location"] == "/my-work/"


def test_sales_page_renders(owner_client):
    customer = Customer.objects.create(name="Asha Rao", phone="9000000011")
    make_order(customer, 1)
    html = get(owner_client).content.decode()
    today = timezone.localdate()
    assert "Reports" in html
    assert f"Sales, 1{chr(0x2013)}{today.day} {today:%b}" in html or (
        f"Sales, 1 {today:%b}" in html
    )
    assert 'id="report-sales_report"' in html
    assert 'aria-current="true"' in html
    assert "period=month" in html
    assert "Asha Rao" in html
    assert "1 order" in html


def test_sales_empty_period(owner_client):
    html = get(owner_client).content.decode()
    today = timezone.localdate()
    assert f"No sales in {today:%B} {today.year}." in html


def test_sales_by_garment_query(owner_client):
    make_order(Customer.objects.create(name="Asha Rao", phone="9000000011"), 1)
    html = get(owner_client, "?group=garment").content.decode()
    assert "1 piece" in html
    assert "Blouse" in html
    assert 'name="group" value="garment"' in html


def test_custom_period_shows_dates(owner_client):
    html = get(owner_client, "?period=custom").content.decode()
    assert 'id="period-from"' in html
    assert 'id="period-to"' in html


def test_no_bottom_nav(owner_client):
    assert 'data-subpage="1"' in get(owner_client).content.decode()


def test_order_outside_period_is_left_out(owner_client):
    from orders.models import Order

    order = make_order(Customer.objects.create(name="Old", phone="9000000033"), 1)
    Order.objects.filter(pk=order.pk).update(
        created_at=timezone.now() - timedelta(days=90)
    )
    assert "No sales in" in get(owner_client).content.decode()
