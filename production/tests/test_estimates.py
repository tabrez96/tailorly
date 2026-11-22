from datetime import UTC, datetime, timedelta

import pytest

from catalog.models import Product
from orders.models import OrderItem
from production.estimates import average_minutes, usual_minutes
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
