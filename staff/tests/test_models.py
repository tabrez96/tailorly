from datetime import date, timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from staff.models import DayRecord, Employee


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


def test_second_day_record_same_date_rejected(db):
    e = Employee.objects.create(name="Asha", phone="9000011114")
    start = timezone.now()
    DayRecord.objects.create(employee=e, date=date(2026, 11, 12), start=start)
    with pytest.raises(IntegrityError), transaction.atomic():
        DayRecord.objects.create(employee=e, date=date(2026, 11, 12), start=start)


def test_end_before_start_rejected(db):
    e = Employee.objects.create(name="Asha", phone="9000011115")
    start = timezone.now()
    with pytest.raises(IntegrityError), transaction.atomic():
        DayRecord.objects.create(
            employee=e,
            date=date(2026, 11, 12),
            start=start,
            end=start - timedelta(minutes=1),
        )
