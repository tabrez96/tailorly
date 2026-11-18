import pytest
from django.db import IntegrityError, transaction

from staff.models import Employee


def test_defaults(db):
    e = Employee.objects.create(name="Asha", phone="9000011111")
    assert e.overtime_multiplier == 1
    assert e.active
    assert str(e) == "Asha"


def test_negative_wage_rejected(db):
    with pytest.raises(IntegrityError), transaction.atomic():
        Employee.objects.create(name="A", phone="9000011112", daily_wage=-1)


def test_zero_multiplier_rejected(db):
    with pytest.raises(IntegrityError), transaction.atomic():
        Employee.objects.create(name="A", phone="9000011113", overtime_multiplier=0)
