from django.contrib import admin

from staff.models import Employee, Payout


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "daily_wage", "active")


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ["employee", "week_start", "paid_on", "method", "amount"]
