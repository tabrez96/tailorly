from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class Product(models.Model):
    PRIMARY, SECONDARY = "primary", "secondary"
    KINDS = [(PRIMARY, "Primary"), (SECONDARY, "Secondary")]
    CUSTOM, READY_MADE = "custom", "ready_made"
    TYPES = [(CUSTOM, "Custom"), (READY_MADE, "Ready-made")]
    UNITS = [("m", "m"), ("pcs", "pcs"), ("pair", "pair"), ("set", "set")]

    name = models.CharField(max_length=80)
    kind = models.CharField(max_length=10, choices=KINDS)
    type = models.CharField(max_length=10, choices=TYPES, blank=True)  # primary only
    usual_price = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )  # primary
    measurement_fields = models.JSONField(
        default=list, blank=True
    )  # ordered names; custom only
    unit = models.CharField(max_length=4, choices=UNITS, blank=True)  # secondary only
    cost_price = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )  # secondary, per unit
    selling_price = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )  # secondary, per unit
    billed_by_default = models.BooleanField(default=True)  # secondary
    active = models.BooleanField(
        default=True
    )  # deactivated, never deleted: orders keep snapshots
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(kind="primary", type__in=["custom", "ready_made"], unit="")
                | Q(kind="secondary", type="", unit__in=["m", "pcs", "pair", "set"]),
                name="product_kind_fields",
            ),
            models.CheckConstraint(
                condition=Q(usual_price__gte=0), name="product_usual_price_not_negative"
            ),
            models.CheckConstraint(
                condition=Q(cost_price__gte=0), name="product_cost_price_not_negative"
            ),
            models.CheckConstraint(
                condition=Q(selling_price__gte=0),
                name="product_selling_price_not_negative",
            ),
            models.CheckConstraint(
                condition=Q(type="custom") | Q(measurement_fields=[]),
                name="product_measurements_custom_only",
            ),
        ]

    def __str__(self):
        return self.name


class ProductOption(models.Model):
    YES_NO, CHOICE = "yes_no", "choice"
    ANSWERS = [(YES_NO, "Yes or no"), (CHOICE, "Choice")]
    AT_ORDER, WHEN_DONE = "at_order", "when_done"
    ASKED = [(AT_ORDER, "At order"), (WHEN_DONE, "When done")]

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="options"
    )
    name = models.CharField(max_length=60)
    answer = models.CharField(max_length=10, choices=ANSWERS, default=YES_NO)
    choices = models.JSONField(default=list, blank=True)  # Choice only
    material = models.ForeignKey(
        Product,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="used_by_options",
        limit_choices_to={"kind": "secondary"},
    )
    asks_quantity = models.BooleanField(default=False)
    asks_notes = models.BooleanField(default=False)
    asked_when = models.CharField(max_length=10, choices=ASKED, default=AT_ORDER)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(answer__in=["yes_no", "choice"]), name="option_answer_valid"
            ),
            models.CheckConstraint(
                condition=Q(asked_when__in=["at_order", "when_done"]),
                name="option_asked_when_valid",
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        # A database check can't look at another row, so check the material's kind here.
        if self.material_id and self.material.kind != Product.SECONDARY:
            raise ValidationError(
                {"material": "Choose a material (a secondary product)."}
            )
