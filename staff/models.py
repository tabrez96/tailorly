from django.conf import settings
from django.db import models
from django.db.models import F, Q


class Employee(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="employee",
    )
    name = models.CharField(max_length=80)
    phone = models.CharField(max_length=10, unique=True)  # same as user.username
    photo = models.ImageField(upload_to="staff/", blank=True)
    daily_wage = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overtime_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=1)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(daily_wage__gte=0), name="employee_wage_not_negative"
            ),
            models.CheckConstraint(
                condition=Q(overtime_multiplier__gt=0), name="employee_ot_positive"
            ),
        ]

    def __str__(self):
        return self.name


class DayRecord(models.Model):
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="days"
    )
    date = models.DateField()  # local (Asia/Kolkata) date of the start
    start = models.DateTimeField()
    end = models.DateTimeField(null=True, blank=True)  # null while the day is going
    edited_by_owner = models.BooleanField(default=False)

    class Meta:
        ordering = ["date"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "date"], name="dayrecord_one_per_day"
            ),
            models.CheckConstraint(
                condition=Q(end__isnull=True) | Q(end__gte=F("start")),
                name="dayrecord_end_after_start",
            ),
        ]

    def __str__(self):
        return f"{self.employee} {self.date}"
