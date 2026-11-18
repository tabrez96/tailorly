import re

import pytest
from django.contrib.auth.models import User
from django.test import Client

from customers.models import Customer
from customers.tests.conftest import PARTIAL


def test_list_alphabetical(owner_client):
    for name in ("arjun", "Anjali", "Meera"):
        Customer.objects.create(name=name)
    html = owner_client.get("/customers/").content.decode()
    names = re.findall(r'prow__title">([^<]+)<', html)
    assert names == ["Anjali", "arjun", "Meera"]
    assert html.count("Paid up") == 3


def test_list_empty_state(owner_client):
    html = owner_client.get("/customers/").content.decode()
    assert "No customers yet" in html
    assert 'id="empty-add"' in html
    assert "customers-add" not in html


def test_search_no_results(owner_client, meera):
    html = owner_client.get('/customers/?q=Z"<b>').content.decode()
    assert 'No customer matches "Z&quot;&lt;b&gt;".' in html
    assert "<b>" not in html
    html = owner_client.get("/customers/?q=Zed").content.decode()
    assert 'No customer matches "Zed".' in html
    assert '+ Add "Zed" as a customer' in html
    assert 'hx-get="/customers/new/?q=Zed"' in html


def test_search_partial(owner_client, meera):
    Customer.objects.create(name="Arjun", phone="9900177345")
    response = owner_client.get("/customers/?q=22110", headers=PARTIAL)
    html = response.content.decode()
    assert "Meera Iyer" in html
    assert "Arjun" not in html
    assert 'class="nav"' not in html
    full = owner_client.get("/customers/?q=mee").content.decode()
    assert 'value="mee"' in full
    assert "Arjun" not in full


def test_add_param_opens_sheet(owner_client, meera):
    html = owner_client.get("/customers/?add=1").content.decode()
    assert 'hx-get="/customers/new/"' in html
    assert 'hx-trigger="load"' in html


def test_add_customer(owner_client, db):
    response = owner_client.post(
        "/customers/new/", {"name": "Meera Iyer", "phone": "+91 98450-22110"}
    )
    assert response.status_code == 204
    c = Customer.objects.get()
    assert c.phone == "9845022110"
    assert f'"path": "/customers/{c.pk}/"' in response["HX-Location"]
    assert "Meera Iyer added" in response["HX-Trigger"]


def test_add_invalid_phone_422(owner_client, db):
    response = owner_client.post("/customers/new/", {"name": "A", "phone": "123"})
    assert response.status_code == 422
    assert "Enter a 10-digit mobile number." in response.content.decode()
    assert not Customer.objects.exists()


def test_add_sheet_prefill(owner_client, db):
    html = owner_client.get("/customers/new/?q=Zed").content.decode()
    assert re.search(r'name="name"[^>]*value="Zed"', html) or re.search(
        r'value="Zed"[^>]*name="name"', html
    )
    html = owner_client.get("/customers/new/?q=98450 22110").content.decode()
    assert 'value="9845022110"' in html


def test_detail(owner_client, meera):
    html = owner_client.get(f"/customers/{meera.pk}/").content.decode()
    assert "98450 22110" in html
    assert 'href="tel:+919845022110"' in html
    assert "Customer since" in html
    assert "Prefers loose sleeves.<br>Sundays." in html
    assert html.count("₹0") == 2
    assert f'href="/orders/new/?customer={meera.pk}"' in html
    assert "+ New order for Meera" in html


def test_detail_without_phone_or_notes(owner_client, db):
    c = Customer.objects.create(name="Zed")
    html = owner_client.get(f"/customers/{c.pk}/").content.decode()
    assert "tel:" not in html
    assert "customer-card__notes" not in html


def test_edit_customer(owner_client, meera):
    response = owner_client.post(
        f"/customers/{meera.pk}/edit/",
        {"name": "Meera Rao", "phone": "9000011111", "notes": "New"},
    )
    assert response.status_code == 204
    meera.refresh_from_db()
    assert (meera.name, meera.phone, meera.notes) == ("Meera Rao", "9000011111", "New")
    assert "Meera Rao saved" in response["HX-Trigger"]
    html = owner_client.get(f"/customers/{meera.pk}/edit/").content.decode()
    assert "Edit Meera Rao" in html


def test_owner_only(meera, db):
    employee = Client()
    employee.force_login(User.objects.create_user("emp", password="x"))
    for client in (employee, Client()):
        assert client.get("/customers/").status_code == 302
        assert client.get(f"/customers/{meera.pk}/").status_code == 302
        assert client.post("/customers/new/", {"name": "X"}).status_code == 302
    assert Customer.objects.count() == 1


def test_edit_pk_zero_404_creates_nothing(owner_client, db):
    response = owner_client.post("/customers/0/edit/", {"name": "Ghost"})
    assert response.status_code == 404
    assert Customer.objects.count() == 0


@pytest.mark.parametrize("path", ["/customers/999/", "/customers/999/edit/"])
def test_unknown_pk_404(owner_client, path):
    assert owner_client.get(path).status_code == 404
