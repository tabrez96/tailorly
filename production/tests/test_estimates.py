from datetime import UTC, datetime, timedelta

import pytest

from catalog.models import Product
from orders.models import OrderItem, Rework
from production.estimates import average_minutes, rework_minutes, usual, usual_minutes
from production.models import TimeSession

T0 = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)


def test_average_needs_three():
    assert average_minutes([60, 90]) == 120
    assert average_minutes([60, 90, 120]) == 90


def test_average_uses_newest_ten():
    assert average_minutes([60] * 10 + [600, 600]) == 60


def test_average_skips_zero():
    assert average_minutes([0, 0, 60, 60]) == 120


def finish(ali, make_item, minutes, n):
    item = make_item(ali)
    item.status = OrderItem.FINISHED
    item.finished_at = T0 + timedelta(days=n)
    item.save()
    start = T0 + timedelta(days=n)
    TimeSession.objects.create(
        employee=ali,
        item=item,
        started_at=start,
        ended_at=start + timedelta(minutes=minutes),
    )


@pytest.mark.django_db
def test_usual_minutes_from_db(ali, make_item):
    product = Product.objects.get()
    for n, minutes in enumerate([60, 90]):
        finish(ali, make_item, minutes, n)
    assert usual_minutes(product) == 120
    finish(ali, make_item, 120, 2)
    assert usual_minutes(product) == 90
    assert usual_minutes(None) == 120


@pytest.mark.django_db
def test_usual_counts_samples(ali, make_item):
    product = Product.objects.get()
    assert usual(None) == (120, 0)
    for n, minutes in enumerate([60, 90]):
        finish(ali, make_item, minutes, n)
    assert usual(product) == (120, 0)
    finish(ali, make_item, 120, 2)
    assert usual(product) == (90, 3)


def test_average_minutes_fallback():
    assert average_minutes([30, 40], 45) == 45
    assert average_minutes([30, 40, 50], 45) == 40


def finish_rework(ali, make_item, minutes, n, finished=True):
    item = make_item(ali)
    rework = Rework.objects.create(
        item=item,
        reason=Rework.FIT,
        assignee=ali,
        finished_at=T0 + timedelta(days=n) if finished else None,
    )
    start = T0 + timedelta(days=n)
    TimeSession.objects.create(
        employee=ali,
        rework=rework,
        started_at=start,
        ended_at=start + timedelta(minutes=minutes),
    )


@pytest.mark.django_db
def test_rework_minutes_45_until_three_finished(ali, make_item):
    assert rework_minutes() == 45
    finish_rework(ali, make_item, 20, 0)
    finish_rework(ali, make_item, 30, 1)
    finish_rework(ali, make_item, 600, 2, finished=False)
    assert rework_minutes() == 45
    finish_rework(ali, make_item, 70, 3)
    assert rework_minutes() == 40


@pytest.mark.django_db
def test_rework_minutes_last_ten(ali, make_item):
    for n in range(2):
        finish_rework(ali, make_item, 600, n)
    for n in range(2, 12):
        finish_rework(ali, make_item, 30, n)
    assert rework_minutes() == 30
