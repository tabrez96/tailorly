from django.db import models


class Customer(models.Model):
    name = models.CharField(max_length=80)
    # 10 digits, normalised; "" when none. Not unique: family members share a number.
    phone = models.CharField(max_length=10, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name


class MeasurementSet(models.Model):
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="measurement_sets"
    )
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.PROTECT, related_name="measurement_sets"
    )
    # Ordered [{"name": "Bust", "value": "34.5"}, ...]; inches as decimal strings.
    values = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "product"], name="one_measurement_set_per_garment"
            )
        ]

    def __str__(self) -> str:
        return f"{self.customer} / {self.product}"
