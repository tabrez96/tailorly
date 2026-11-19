import json
from datetime import UTC, datetime

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import Client

from catalog.models import Product
from customers.models import MeasurementSet
from customers.tests.conftest import PARTIAL


def _product(name, fields=(), **kw):
    kw.setdefault("type", "custom")
    return Product.objects.create(
        name=name,
        kind="primary",
        usual_price=1000,
        measurement_fields=list(fields),
        **kw,
    )


@pytest.fixture
def blouse(db):
    return _product("Blouse", ["Bust", "Waist"])


@pytest.fixture
def kurta(db):
    return _product("Kurta", ["Chest", "Length"])


def _url(meera, product):
    return f"/customers/{meera.pk}/measurements/{product.pk}/"


def _set(meera, product, values):
    return MeasurementSet.objects.create(customer=meera, product=product, values=values)


def test_one_set_per_garment(meera, blouse):
    _set(meera, blouse, [])
    with pytest.raises(IntegrityError):
        _set(meera, blouse, [])


def test_detail_empty_measurements(owner_client, meera):
    html = owner_client.get(f"/customers/{meera.pk}/").content.decode()
    assert "No measurements yet." in html
    assert "+ Add garment" in html


def test_detail_tabs_and_tiles(owner_client, meera, blouse, kurta):
    _set(meera, kurta, [{"name": "Length", "value": "40"}])
    b = _set(
        meera,
        blouse,
        [{"name": "Waist", "value": "28"}, {"name": "Bust", "value": "34"}],
    )
    MeasurementSet.objects.filter(pk=b.pk).update(
        updated_at=datetime(2026, 11, 2, 9, tzinfo=UTC)
    )
    html = owner_client.get(f"/customers/{meera.pk}/").content.decode()
    assert html.index("Blouse</button>") < html.index("Kurta</button>")
    assert "Updated 2 Nov 2026" in html
    assert html.index("Bust") < html.index("Waist")
    assert f'id="mtab-{blouse.pk}"' in html
    selected = owner_client.get(f"/customers/{meera.pk}/?g={kurta.pk}").content.decode()
    tab = selected.split(f'id="mtab-{kurta.pk}"')[1].split(">")[0]
    assert 'aria-selected="true"' in tab


def test_detail_unknown_garment_selects_first(owner_client, meera, blouse):
    _set(meera, blouse, [])
    html = owner_client.get(f"/customers/{meera.pk}/?g=junk").content.decode()
    tab = html.split(f'id="mtab-{blouse.pk}"')[1].split(">")[0]
    assert 'aria-selected="true"' in tab


def test_edit_shows_product_and_custom_fields(owner_client, meera, blouse):
    _set(
        meera, blouse, [{"name": "Bust", "value": "34"}, {"name": "Hip", "value": "38"}]
    )
    html = owner_client.get(_url(meera, blouse)).content.decode()
    assert 'value="34"' in html and 'value="38"' in html
    assert html.index(">Bust<") < html.index(">Waist<") < html.index(">Hip<")


def test_edit_new_garment_starts_from_product_fields(owner_client, meera, kurta):
    html = owner_client.get(_url(meera, kurta)).content.decode()
    assert ">Chest<" in html and ">Length<" in html


def test_save_changes_only_that_set(owner_client, meera, blouse, kurta):
    _set(meera, kurta, [{"name": "Chest", "value": "40"}])
    response = owner_client.post(
        _url(meera, blouse),
        {"field": ["Bust", "Waist"], "value": ["34", ""], "unit": "in"},
        headers=PARTIAL,
    )
    assert response.status_code == 204
    assert (
        json.loads(response["HX-Location"])["path"]
        == f"/customers/{meera.pk}/?g={blouse.pk}"
    )
    assert "Blouse measurements saved" in response["HX-Trigger"]
    assert MeasurementSet.objects.get(product=blouse).values == [
        {"name": "Bust", "value": "34"}
    ]
    assert MeasurementSet.objects.get(product=kurta).values == [
        {"name": "Chest", "value": "40"}
    ]


def test_save_without_htmx_redirects(owner_client, meera, blouse):
    response = owner_client.post(
        _url(meera, blouse), {"field": ["Bust"], "value": ["34"]}
    )
    assert response.status_code == 302


def test_save_twice_updates_one_set(owner_client, meera, blouse):
    for v in ("34", "35"):
        owner_client.post(_url(meera, blouse), {"field": ["Bust"], "value": [v]})
    assert MeasurementSet.objects.filter(customer=meera).count() == 1


def test_save_in_cm_stores_inches(owner_client, meera, blouse):
    owner_client.post(
        _url(meera, blouse), {"field": ["Bust"], "value": ["86.36"], "unit": "cm"}
    )
    assert MeasurementSet.objects.get().values == [{"name": "Bust", "value": "34"}]
    html = owner_client.get(f"/customers/{meera.pk}/").content.decode()
    assert "tile__value" in html and "34" in html


def test_add_measurement_saved_and_shown(owner_client, meera, blouse):
    owner_client.post(
        _url(meera, blouse),
        {"field": ["Bust"], "value": ["34"], "new_name": ["Hip"], "new_value": ["38"]},
    )
    assert MeasurementSet.objects.get().values[-1] == {"name": "Hip", "value": "38"}
    html = owner_client.get(f"/customers/{meera.pk}/").content.decode()
    assert ">Hip<" in html


def test_invalid_value_422_nothing_saved(owner_client, meera, blouse):
    response = owner_client.post(
        _url(meera, blouse),
        {
            "field": ["Bust"],
            "value": ["abc"],
            "new_name": ["Hip"],
            "new_value": ["5"],
            "unit": "cm",
        },
    )
    html = response.content.decode()
    assert response.status_code == 422
    assert "Enter a number, like 34 or 11.5." in html
    assert "1 thing needs fixing before you can save these measurements." in html
    assert 'value="abc"' in html and 'value="Hip"' in html
    assert 'value="cm"\n                           checked' in html
    assert not MeasurementSet.objects.exists()


def test_edit_404s(owner_client, meera, blouse):
    ready = _product("Saree", type="ready_made")
    material = Product.objects.create(
        name="Silk", kind="secondary", unit="m", cost_price=1, selling_price=2
    )
    inactive = _product("Old", active=False)
    assert owner_client.get(_url(meera, ready)).status_code == 404
    assert owner_client.get(_url(meera, material)).status_code == 404
    assert (
        owner_client.get(f"/customers/999/measurements/{blouse.pk}/").status_code == 404
    )
    assert owner_client.get(_url(meera, inactive)).status_code == 404
    _set(meera, inactive, [])
    assert owner_client.get(_url(meera, inactive)).status_code == 200


def test_garment_add_lists_unmeasured_custom_only(owner_client, meera, blouse, kurta):
    _product("Saree", type="ready_made")
    _set(meera, blouse, [])
    html = owner_client.get(f"/customers/{meera.pk}/measurements/add/").content.decode()
    assert "Kurta" in html and "Saree" not in html and ">Blouse<" not in html


def test_garment_add_messages_when_nothing_to_add(owner_client, meera, blouse):
    _set(meera, blouse, [])
    url = f"/customers/{meera.pk}/measurements/add/"
    assert (
        "Every custom garment already has measurements"
        in owner_client.get(url).content.decode()
    )


def test_garment_add_without_products(owner_client, meera):
    html = owner_client.get(f"/customers/{meera.pk}/measurements/add/").content.decode()
    assert "Add a custom product in Products first." in html


def test_garment_add_post_redirects_to_edit(owner_client, meera, kurta):
    response = owner_client.post(
        f"/customers/{meera.pk}/measurements/add/", {"product": kurta.pk}
    )
    assert response.status_code == 204
    assert json.loads(response["HX-Location"])["path"] == _url(meera, kurta)
    assert "toast" not in response["HX-Trigger"]
    assert not MeasurementSet.objects.exists()


def test_garment_add_rejects_existing(owner_client, meera, kurta):
    _set(meera, kurta, [])
    response = owner_client.post(
        f"/customers/{meera.pk}/measurements/add/", {"product": kurta.pk}
    )
    assert response.status_code == 422
    assert "Choose a garment from the list." in response.content.decode()


def test_garment_add_requires_choice(owner_client, meera, kurta):
    response = owner_client.post(f"/customers/{meera.pk}/measurements/add/", {})
    assert response.status_code == 422


def test_employee_cannot_edit_measurements(meera, blouse):
    employee = Client()
    employee.force_login(User.objects.create_user("emp", password="x"))
    for client in (employee, Client()):
        assert client.get(_url(meera, blouse)).status_code == 302
        assert (
            client.post(
                _url(meera, blouse), {"field": ["Bust"], "value": ["34"]}
            ).status_code
            == 302
        )
        assert client.get(f"/customers/{meera.pk}/measurements/add/").status_code == 302
    assert not MeasurementSet.objects.exists()


def test_saved_set_editable_after_product_becomes_ready_made(
    owner_client, meera, blouse
):
    _set(meera, blouse, [{"name": "Bust", "value": "34"}])
    Product.objects.filter(pk=blouse.pk).update(
        type="ready_made", measurement_fields=[]
    )
    assert owner_client.get(_url(meera, blouse)).status_code == 200


def test_new_row_value_error_marks_value_input(owner_client, meera, blouse):
    response = owner_client.post(
        _url(meera, blouse),
        {"field": ["Bust"], "value": ["34"], "new_name": ["Hip"], "new_value": ["abc"]},
    )
    html = response.content.decode()
    assert response.status_code == 422
    assert 'aria-describedby="new-value-s2_error"' in html
    assert "new-name-s2_error" not in html
