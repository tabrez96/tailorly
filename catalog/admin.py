from django.contrib import admin

from catalog.models import Product, ProductOption


class ProductOptionInline(admin.TabularInline):
    model = ProductOption
    fk_name = "product"
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "kind", "type", "unit", "active"]
    list_filter = ["kind", "type", "active"]
    inlines = [ProductOptionInline]

    def has_delete_permission(self, request, obj=None):
        # Products are deactivated, never deleted: orders keep their snapshots.
        return False
