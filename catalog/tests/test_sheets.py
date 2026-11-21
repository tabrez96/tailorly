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
    assert "hx-confirm" not in html


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


def editor_json(html):
    marker = 'id="product-editor-data" type="application/json">'
    start = html.index(marker) + len(marker)
    return json.loads(html[start : html.index("</script>", start)])


def blouse_post(demo_catalog, **extra):
    return {
        "name": "Blouse",
        "kind": "primary",
        "type": "custom",
        "usual_price": "1800",
    } | extra


def test_edit_sheet_has_editor_state(owner_client, demo_catalog):
    html = owner_client.get(f"/products/{pk('Blouse')}/").content.decode()
    state = editor_json(html)
    assert len(state["measurements"]) == 9
    assert [o["name"] for o in state["options"]] == [
        "Lining",
        "Sleeve style",
        "Padding",
    ]
    assert state["options"][0]["material"] == pk("Lining, cotton cream")
    assert len(state["materials"]) == 6


def test_save_measurements_and_options_in_order(owner_client, demo_catalog):
    lining = pk("Lining, cotton cream")
    options = [
        {"name": "Sleeve style", "answer": "choice", "choices": ["Full", "Short"]},
        {
            "name": "Lining",
            "material": lining,
            "asks_quantity": True,
            "asked_when": "when_done",
        },
    ]
    response = owner_client.post(
        f"/products/{pk('Blouse')}/",
        blouse_post(
            demo_catalog,
            measurements_json=json.dumps(["Bust", "Waist"]),
            options_json=json.dumps(options),
        ),
    )
    assert response.status_code == 204
    blouse = Product.objects.get(name="Blouse")
    assert blouse.measurement_fields == ["Bust", "Waist"]
    saved = list(blouse.options.all())
    assert [(o.name, o.position) for o in saved] == [("Sleeve style", 0), ("Lining", 1)]
    assert saved[0].choices == ["Full", "Short"]
    assert saved[1].material_id == lining
    assert saved[1].asks_quantity
    assert saved[1].asked_when == "when_done"


def test_save_removes_dropped_options(owner_client, demo_catalog):
    response = owner_client.post(
        f"/products/{pk('Blouse')}/",
        blouse_post(demo_catalog, options_json=json.dumps([{"name": "Lining"}])),
    )
    assert response.status_code == 204
    assert Product.objects.get(name="Blouse").options.count() == 1


def test_ready_made_clears_measurements(owner_client, demo_catalog):
    owner_client.post(
        f"/products/{pk('Blouse')}/",
        blouse_post(
            demo_catalog, type="ready_made", measurements_json=json.dumps(["Bust"])
        ),
    )
    assert Product.objects.get(name="Blouse").measurement_fields == []


def test_missing_json_fields_keep_saved_data(owner_client, demo_catalog):
    response = owner_client.post(
        f"/products/{pk('Blouse')}/",
        {"name": "Blouse", "kind": "primary", "type": "custom", "usual_price": "900"},
    )
    assert response.status_code == 204
    blouse = Product.objects.get(name="Blouse")
    assert len(blouse.measurement_fields) == 9
    assert blouse.options.count() == 3


def test_explicit_empty_lists_clear_saved_data(owner_client, demo_catalog):
    owner_client.post(
        f"/products/{pk('Blouse')}/",
        blouse_post(demo_catalog, measurements_json="[]", options_json="[]"),
    )
    blouse = Product.objects.get(name="Blouse")
    assert blouse.measurement_fields == []
    assert blouse.options.count() == 0


def test_ready_made_ignores_bad_measurements(owner_client, demo_catalog):
    response = owner_client.post(
        f"/products/{pk('Blouse')}/",
        blouse_post(
            demo_catalog,
            type="ready_made",
            measurements_json=json.dumps(["Bust", "bust"]),
        ),
    )
    assert response.status_code == 204
    assert Product.objects.get(name="Blouse").measurement_fields == []


def test_too_many_options_marks_add_button(owner_client, demo_catalog):
    many = [{"name": f"Option {i}"} for i in range(21)]
    response = owner_client.post(
        f"/products/{pk('Blouse')}/",
        blouse_post(demo_catalog, options_json=json.dumps(many)),
    )
    assert response.status_code == 422
    assert "Use 20 options or fewer." in response.content.decode()


def test_choice_with_one_choice_keeps_sheet(owner_client, demo_catalog):
    bad = [{"name": "Fall", "answer": "choice", "choices": ["Plain"]}]
    response = owner_client.post(
        f"/products/{pk('Blouse')}/",
        blouse_post(demo_catalog, options_json=json.dumps(bad)),
    )
    assert response.status_code == 422
    html = response.content.decode()
    assert "Fix the options marked below." in html
    state = editor_json(html)
    assert state["errors"]["option"] == [{"choices": "Add at least 2 choices."}]
    assert state["options"][0]["name"] == "Fall"
    assert Product.objects.get(name="Blouse").options.count() == 3


def test_unreadable_measurements_keep_sheet(owner_client, demo_catalog):
    response = owner_client.post(
        f"/products/{pk('Blouse')}/",
        blouse_post(demo_catalog, measurements_json="{", options_json="{"),
    )
    assert response.status_code == 422
    state = editor_json(response.content.decode())
    assert (
        state["errors"]["measurements"] == "Measurements could not be read. Try again."
    )
    assert state["errors"]["options"] == "Options could not be read. Try again."
    assert state["measurements"] == [] and state["options"] == []


def test_material_must_be_secondary(owner_client, demo_catalog):
    bad = [{"name": "Lining", "material": pk("Kurta")}]
    response = owner_client.post(
        f"/products/{pk('Blouse')}/",
        blouse_post(demo_catalog, options_json=json.dumps(bad)),
    )
    assert response.status_code == 422
    assert "Choose a material from the list." in response.content.decode()


def test_inactive_material_still_allowed_for_its_product(owner_client, demo_catalog):
    Product.objects.filter(name="Padding cups").update(active=False)
    cups = pk("Padding cups")
    kept = [{"name": "Padding", "material": cups}]
    response = owner_client.post(
        f"/products/{pk('Blouse')}/",
        blouse_post(demo_catalog, options_json=json.dumps(kept)),
    )
    assert response.status_code == 204
    state = editor_json(owner_client.get(f"/products/{pk('Kurta')}/").content.decode())
    assert "Padding cups" not in [m["name"] for m in state["materials"]]


def test_new_material_return_to_redirects_back(owner_client):
    form = {
        "kind": "secondary",
        "name": "Canvas",
        "unit": "m",
        "cost_price": "80",
        "selling_price": "100",
        "return_to": "/orders/1/items/2/materials/new/?on=order",
    }
    response = owner_client.post("/products/new/", form, HTTP_HX_REQUEST="true")
    product = Product.objects.get(name="Canvas")
    assert response.status_code == 302
    assert response["Location"] == (
        f"/orders/1/items/2/materials/new/?on=order&material={product.pk}"
    )


def test_new_material_off_site_return_to_is_ignored(owner_client):
    form = {
        "kind": "secondary",
        "name": "Canvas",
        "unit": "m",
        "cost_price": "80",
        "selling_price": "100",
        "return_to": "//evil.example/orders/",
    }
    response = owner_client.post("/products/new/", form, HTTP_HX_REQUEST="true")
    assert response.status_code == 204
    assert "HX-Location" in response
    assert "evil" not in response["HX-Location"]
