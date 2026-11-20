import re
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

from customers.models import Customer
from orders.models import Payment
from orders.tests.conftest import make_order

PARTIAL = {"HX-Request": "true", "HX-Request-Type": "partial"}


def test_orders_requires_owner(db):
    employee = Client()
    employee.force_login(User.objects.create_user("emp", password="x"))
    for client in (employee, Client()):
        assert client.get("/orders/").status_code == 302


def test_orders_empty_state(owner_client, customer):
    make_order(customer, None, status="draft")
    html = owner_client.get("/orders/").content.decode()
    assert "No orders yet" in html
    assert 'id="empty-new"' in html
    assert 'href="/orders/new/"' in html


def test_orders_default_open_lists_rows_and_counts(owner_client, customer):
    today = timezone.localdate()
    make_order(customer, None, status="draft")
    make_order(customer, 1, due=today + timedelta(days=3), price="1200")
    make_order(customer, 2, status="ready")
    make_order(customer, 3, status="delivered")
    html = owner_client.get("/orders/").content.decode()
    assert "Open <span" in html and "(1)" in html
    assert re.search(r"Ready <span[^>]*>\(1\)", html)
    assert re.search(r"Open <span[^>]*>\(1\)", html)
    assert "#1 · Asha Rao" in html
    assert "#2 ·" not in html and "#3 ·" not in html
    assert "Not started" in html
    assert "₹1,200 due" in html
    assert "Blouse" in html
    assert "Due " in html


def test_orders_filter_in_url_survives_reload(owner_client, customer):
    make_order(customer, 1)
    make_order(customer, 2, free=True)
    html = owner_client.get("/orders/?show=free").content.decode()
    assert "<html" in html
    assert re.search(r'id="chip-free"[^>]*aria-current="true"', html)
    assert "#2 ·" in html and "#1 ·" not in html
    assert re.search(r'name="show"\s+value="free"', html)


def test_orders_no_search_match(owner_client, customer):
    make_order(customer, 1)
    html = owner_client.get("/orders/?q=zzz").content.decode()
    assert 'No orders match "zzz".' in html
    assert 'id="clear-search"' in html
    assert 'href="/orders/"' in html
    html = owner_client.get("/orders/?show=ready&q=zzz").content.decode()
    assert 'href="/orders/?show=ready"' in html


def test_orders_partial_has_results_and_chips_keep_search(owner_client, customer):
    make_order(customer, 1)
    html = owner_client.get("/orders/?q=asha", headers=PARTIAL).content.decode()
    assert 'id="orders-results"' in html
    assert "/orders/?show=ready&amp;q=asha" in html


def test_orders_late_row_says_overdue(owner_client, customer):
    make_order(customer, 1, due=timezone.localdate() - timedelta(days=2))
    html = owner_client.get("/orders/").content.decode()
    assert "Overdue" in html
    assert "orow__due--late" in html
    assert 'id="chip-late"' in html
    html = owner_client.get("/orders/?show=late").content.decode()
    assert "#1 ·" in html


def test_orders_empty_filter_messages(owner_client, customer):
    make_order(customer, 1)
    assert (
        "No ready orders." in owner_client.get("/orders/?show=ready").content.decode()
    )


def test_orders_query_count(owner_client, customer, django_assert_max_num_queries):
    for n in range(1, 11):
        make_order(customer, n)
    with django_assert_max_num_queries(14):
        assert owner_client.get("/orders/").status_code == 200


def test_customer_page_lists_orders_newest_first(owner_client, customer):
    other = Customer.objects.create(name="Meera Iyer", phone="9845099999")
    first = make_order(customer, 1, price="1000")
    second = make_order(customer, 2, price="500")
    make_order(customer, None, status="draft")
    make_order(other, 4)
    Payment.objects.create(
        order=first, amount=Decimal("400"), date=timezone.localdate(), method="cash"
    )
    html = owner_client.get(f"/customers/{customer.pk}/").content.decode()
    hrefs = re.findall(r'href="(/orders/\d+/)"', html)
    assert hrefs == [f"/orders/{second.pk}/", f"/orders/{first.pk}/"]
    assert "₹1,500" in html  # spent
    assert "₹1,100" in html  # to collect: 600 + 500


def test_customer_page_no_orders(owner_client, customer):
    html = owner_client.get(f"/customers/{customer.pk}/").content.decode()
    assert "No orders yet." in html
