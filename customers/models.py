from django.db import models


class Customer(models.Model):
    name = models.CharField(max_length=80)
    # 10 digits, normalised; "" when none. Not unique: family members share a number.
    phone = models.CharField(max_length=10, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name
