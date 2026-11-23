from decimal import Decimal

from django.db import models
from django.db.models import Q

from reports import costing


class ShopSettings(models.Model):
    """The shop's own settings; always the single row with pk 1."""

    # [{"name": "Rent", "amount": "7000"}, ...], rupees a month.
    running_costs = models.JSONField(default=list, blank=True)
    working_hours = models.PositiveSmallIntegerField(default=costing.DEFAULT_HOURS)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "shop settings"
        constraints = [
            models.CheckConstraint(condition=Q(id=1), name="shopsettings_single_row"),
            models.CheckConstraint(
                condition=Q(working_hours__gt=0), name="shopsettings_hours_positive"
            ),
        ]

    def __str__(self):
        return "Shop settings"

    @classmethod
    def current(cls) -> ShopSettings:
        """The saved row, or an unsaved default (reading never writes)."""
        return cls.objects.filter(pk=1).first() or cls(pk=1)

    def monthly_total(self) -> Decimal:
        return costing.monthly_total(self.running_costs)

    def running_rate(self) -> Decimal | None:
        return costing.running_rate(self.monthly_total(), self.working_hours)
