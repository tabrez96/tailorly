"""Usual time for a product: what the queue and the assign sheet start from."""

from django.db.models import F

from orders.models import OrderItem

USUAL_MINUTES = 120
SAMPLE = 10
MIN_FINISHED = 3
FETCH = 30  # items without timing are skipped, so look at more than SAMPLE


def average_minutes(logged: list[int]) -> int:
    """Average of the newest SAMPLE times (newest first); USUAL_MINUTES until 3."""
    recent = [m for m in logged if m > 0][:SAMPLE]
    if len(recent) < MIN_FINISHED:
        return USUAL_MINUTES
    return max(1, round(sum(recent) / len(recent)))


def usual_minutes(product) -> int:
    from production.timing import session_seconds  # timing imports this module

    if product is None:
        return USUAL_MINUTES
    items = (
        OrderItem.objects.filter(product=product, status=OrderItem.FINISHED)
        .order_by(F("finished_at").desc(nulls_last=True), "-id")
        .prefetch_related("sessions")[:FETCH]
    )
    logged = [
        sum(
            session_seconds(s.started_at, s.ended_at, s.ended_at)
            for s in item.sessions.all()
            if s.ended_at
        )
        // 60
        for item in items
    ]
    return average_minutes(logged)
