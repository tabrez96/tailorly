from django.db import models
from django.db.models import F, Q


class TimeSession(models.Model):
    employee = models.ForeignKey(
        "staff.Employee", on_delete=models.CASCADE, related_name="sessions"
    )
    item = models.ForeignKey(
        "orders.OrderItem",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="sessions",
    )
    rework = models.ForeignKey(
        "orders.Rework",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="sessions",
    )
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)  # null while running

    class Meta:
        ordering = ["started_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee"],
                condition=Q(ended_at__isnull=True),
                name="timesession_one_open_per_employee",
            ),
            models.CheckConstraint(
                condition=Q(item__isnull=False, rework__isnull=True)
                | Q(item__isnull=True, rework__isnull=False),
                name="timesession_item_or_rework",
            ),
            models.CheckConstraint(
                condition=Q(ended_at__isnull=True) | Q(ended_at__gte=F("started_at")),
                name="timesession_end_after_start",
            ),
        ]

    def __str__(self):
        return f"{self.employee} {self.item or self.rework}"
