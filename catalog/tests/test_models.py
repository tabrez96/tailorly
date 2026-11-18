import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from catalog.models import Product, ProductOption


def make(**fields):
    base = {"name": "X", "kind": "primary", "type": "custom"}
    return Product.objects.create(**{**base, **fields})


def fails(**fields):
    with pytest.raises(IntegrityError), transaction.atomic():
        make(**fields)


@pytest.mark.django_db
def test_primary_needs_type():
    fails(type="")


@pytest.mark.django_db
def test_primary_rejects_unit():
    fails(unit="m")


@pytest.mark.django_db
def test_secondary_needs_unit():
    fails(kind="secondary", type="", unit="")


@pytest.mark.django_db
def test_secondary_rejects_type():
    fails(kind="secondary", type="custom", unit="m")


@pytest.mark.django_db
@pytest.mark.parametrize("field", ["usual_price", "cost_price", "selling_price"])
def test_negative_prices_rejected(field):
    fails(**{field: -1})


@pytest.mark.django_db
def test_measurement_fields_custom_only():
    fails(type="ready_made", measurement_fields=["Chest"])
    product = make(measurement_fields=["Chest", "Waist"])
    product.refresh_from_db()
    assert product.measurement_fields == ["Chest", "Waist"]


@pytest.mark.django_db
def test_option_answer_and_asked_when_checked():
    product = make()
    for bad in ({"answer": "maybe"}, {"asked_when": "later"}):
        with pytest.raises(IntegrityError), transaction.atomic():
            ProductOption.objects.create(product=product, name="O", **bad)


@pytest.mark.django_db
def test_option_material_must_be_secondary():
    option = ProductOption(product=make(), name="O", material=make(name="Y"))
    with pytest.raises(ValidationError) as error:
        option.full_clean()
    assert "material" in error.value.message_dict


@pytest.mark.django_db
def test_material_in_use_is_protected():
    material = make(kind="secondary", type="", unit="m")
    ProductOption.objects.create(product=make(name="Y"), name="O", material=material)
    with pytest.raises(ProtectedError):
        material.delete()
