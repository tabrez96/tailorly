"""Usual time for a product: what the queue and the assign sheet start from."""

from django.db.models import F

from orders.models import OrderItem, Rework

USUAL_MINUTES = 120
REWORK_MINUTES = 45
SAMPLE = 10
MIN_FINISHED = 3
FETCH = 30  # items without timing are skipped, so look at more than SAMPLE


def average_minutes(logged: list[int], fallback: int = USUAL_MINUTES) -> int:
    """Average of the newest SAMPLE times (newest first); the fallback until 3."""
    recent = [m for m in logged if m > 0][:SAMPLE]
    if len(recent) < MIN_FINISHED:
        return fallback
    return max(1, round(sum(recent) / len(recent)))


def usual_minutes(product) -> int:
    return usual(product)[0]


def usual(product) -> tuple[int, int]:
    """(minutes, how many logged times they average); 0 samples means the fallback."""
    from production.timing import session_seconds  # timing imports this module

    if product is None:
        return USUAL_MINUTES, 0
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
    samples = len([m for m in logged if m > 0][:SAMPLE])
    return average_minutes(logged), samples if samples >= MIN_FINISHED else 0


def rework_minutes() -> int:
    """Usual rework time: 45m until 3 finished reworks, then the last 10 averaged."""
    from production.timing import session_seconds  # timing imports this module

    reworks = (
        Rework.objects.filter(finished_at__isnull=False)
        .order_by("-finished_at", "-id")
        .prefetch_related("sessions")[:FETCH]
    )
    logged = [
        sum(
            session_seconds(s.started_at, s.ended_at, s.ended_at)
            for s in r.sessions.all()
            if s.ended_at
        )
        // 60
        for r in reworks
    ]
    return average_minutes(logged, REWORK_MINUTES)
