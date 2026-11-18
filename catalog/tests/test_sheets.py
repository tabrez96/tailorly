import json

from django.contrib.auth.models import User
from django.test import Client

from catalog.models import Product


def pk(name):
    return Product.objects.get(name=name).pk


def test_add_sheet_is_empty_product_sheet(owner_client):
    html = owner_client.get("/products/new/").content.decode()
    assert "Add product" in html
    assert 'name="usual_price"' in html
    assert "Remove" not in html


def test_add_material_sheet(owner_client):
    html = owner_client.get("/products/new/?kind=secondary").content.decode()
    assert "Add material" in html
    for unit in ("m", "pcs", "pair", "set"):
        assert f'value="{unit}"' in html


def test_kind_switch_keeps_name(owner_client):
    html = owner_client.get(
        "/products/new/?kind=secondary&name=Lining+silk"
    ).content.decode()
    assert 'value="Lining silk"' in html
    assert "Add material" in html


def test_edit_sheet_shows_product(owner_client, demo_catalog):
    html = owner_client.get(f"/products/{pk('Blouse')}/").content.decode()
    assert "Edit Blouse" in html
    assert "Changes apply to new orders only." in html
    assert 'value="1,800"' in html
    assert 'hx-confirm="Remove Blouse? Past orders keep it."' in html


def test_edit_material_subtitle(owner_client, demo_catalog):
    html = owner_client.get(f"/products/{pk('Lining, cotton cream')}/").content.decode()
    assert (
        "Used by the Lining option on Blouse, Chudidar, Lehenga blouse and Salwar suit."
        in html
    )
    assert 'value="₹120"' in html


def test_save_returns_location_and_toast(owner_client):
    response = owner_client.post(
        "/products/new/",
        {
            "name": "Sherwani",
            "kind": "primary",
            "type": "custom",
            "usual_price": "5200",
        },
    )
    assert response.status_code == 204
    assert json.loads(response["HX-Location"])["path"] == "/products/"
    trigger = json.loads(response["HX-Trigger"])
    assert trigger["sheet:close"] is True
    assert trigger["toast"]["message"] == "Sherwani added"


def test_edit_saves_changes(owner_client, demo_catalog):
    response = owner_client.post(
        f"/products/{pk('Kurta')}/",
        {"name": "Kurta", "kind": "primary", "type": "custom", "usual_price": "1,300"},
    )
    assert json.loads(response["HX-Trigger"])["toast"]["message"] == "Kurta saved"
    assert Product.objects.get(name="Kurta").usual_price == 1300


def test_save_material_lists_under_materials_only(owner_client):
    response = owner_client.post(
        "/products/new/",
        {
            "name": "Lining silk",
            "kind": "secondary",
            "unit": "m",
            "cost_price": "₹200",
            "selling_price": "250",
            "billed_by_default": "on",
        },
    )
    assert json.loads(response["HX-Location"])["path"] == "/products/?kind=materials"
    assert (
        "Lining silk" in owner_client.get("/products/?kind=materials").content.decode()
    )
    assert "Lining silk" not in owner_client.get("/products/").content.decode()


def test_invalid_post_keeps_sheet(owner_client):
    response = owner_client.post(
        "/products/new/",
        {"name": "", "kind": "primary", "type": "custom", "usual_price": "10"},
    )
    html = response.content.decode()
    assert response.status_code == 422
    assert 'aria-invalid="true"' in html
    assert "Enter a name." in html
    assert "1 thing needs fixing before you can save this product." in html
    assert not Product.objects.exists()


def test_remove_deactivates(owner_client, demo_catalog):
    blouse = pk("Blouse")
    response = owner_client.post(f"/products/{blouse}/remove/")
    assert response.status_code == 204
    assert json.loads(response["HX-Trigger"])["toast"]["message"] == "Blouse removed"
    assert Product.objects.get(pk=blouse).active is False
    assert f'id="row-{blouse}"' not in owner_client.get("/products/").content.decode()
    assert owner_client.get(f"/products/{blouse}/").status_code == 404


def test_remove_requires_post(owner_client, demo_catalog):
    assert owner_client.get(f"/products/{pk('Blouse')}/remove/").status_code == 405


def test_list_wires_sheets(owner_client, demo_catalog):
    html = owner_client.get("/products/").content.decode()
    assert 'id="products-add"' in html
    assert 'hx-get="/products/new/"' in html
    assert f'hx-get="/products/{pk("Blouse")}/"' in html
    materials = owner_client.get("/products/?kind=materials").content.decode()
    assert 'hx-get="/products/new/?kind=secondary"' in materials
    assert 'hx-trigger="load"' in owner_client.get("/products/?add=1").content.decode()
    assert 'hx-trigger="load"' not in html


def test_add_it_button_carries_search(owner_client, demo_catalog):
    html = owner_client.get("/products/?q=sherwani").content.decode()
    assert 'hx-get="/products/new/?name=sherwani"' in html


def test_employee_cannot_open_sheet(db):
    user = User.objects.create_user("emp", password="x")
    client = Client()
    client.force_login(user)
    assert client.get("/products/new/").status_code == 302
    assert client.post("/products/1/remove/").status_code == 302


def test_empty_state_add_matches_kind(owner_client, db):
    materials = owner_client.get("/products/?kind=materials").content.decode()
    assert "+ Add material" in materials
    assert "+ Add product" not in materials
    assert 'hx-get="/products/new/?kind=secondary"' in materials
    products = owner_client.get("/products/").content.decode()
    assert "+ Add product" in products
    assert "+ Add material" not in products
