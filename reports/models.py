from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from reports import costing


class ShopSettings(models.Model):
    """The shop's own settings; always the single row with pk 1."""

    # [{"name": "Rent", "amount": "7000"}, ...], rupees a month.
    running_costs = models.JSONField(default=list, blank=True)
    working_hours = models.PositiveSmallIntegerField(default=costing.DEFAULT_HOURS)
    hold_tip_seen = models.BooleanField(default=False)  # Got it on the S02 hold tip
    costs_saved = models.BooleanField(
        default=False
    )  # running costs saved at least once
    mcp_on = models.BooleanField(default=False)
    mcp_orders = models.BooleanField(default=True)  # orders and customers
    mcp_measurements = models.BooleanField(default=True)  # measurements and photos
    mcp_money = models.BooleanField(default=True)  # invoices, payments, costs, gains
    mcp_staff = models.BooleanField(default=False)  # attendance, overtime, payouts
    mcp_can_change = models.BooleanField(default=False)  # False: only read
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


class ShopBill(models.Model):
    """Rent, electricity and other shop costs, counted on the day they are dated."""

    name = models.CharField(max_length=60)
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gte=0), name="shopbill_amount_not_negative"
            ),
        ]

    def __str__(self):
        return self.name
