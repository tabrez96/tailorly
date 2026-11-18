from django.contrib import admin

from customers.forms import CustomerForm
from customers.models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    form = CustomerForm
    list_display = ("name", "phone", "created_at")
    search_fields = ("name", "phone")
