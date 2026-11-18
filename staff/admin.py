from django.contrib import admin

from staff.models import Employee


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "daily_wage", "active")
