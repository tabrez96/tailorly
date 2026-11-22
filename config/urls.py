from django.contrib import admin
from django.urls import include, path

from catalog import views as catalog_views
from core import views
from production import views as production_views
from staff import views as staff_views
from today import views as today_views

urlpatterns = [
    path("", today_views.today, name="today"),
    path("my-work/", production_views.my_work, name="my_work"),
    path("production/plan/", production_views.work_plan, name="work_plan"),
    path(
        "my-work/items/<int:pk>/start/", production_views.work_start, name="work_start"
    ),
    path(
        "my-work/items/<int:pk>/finish/",
        production_views.work_finish,
        name="work_finish",
    ),
    path(
        "my-work/items/<int:pk>/details/",
        production_views.item_details,
        name="work_item_details",
    ),
    path(
        "my-work/reworks/<int:pk>/start/",
        production_views.rework_start,
        name="work_rework_start",
    ),
    path(
        "my-work/reworks/<int:pk>/finish/",
        production_views.rework_finish,
        name="work_rework_finish",
    ),
    path(
        "my-work/reworks/<int:pk>/details/",
        production_views.rework_details,
        name="work_rework_details",
    ),
    path("my-work/pause/", production_views.work_pause, name="work_pause"),
    path("my-work/day/start/", staff_views.start_my_day, name="start_my_day"),
    path("my-work/day/end/", staff_views.end_my_day, name="end_my_day"),
    path("my-pay/", staff_views.my_pay, name="my_pay"),
    path("products/", catalog_views.products, name="products"),
    path("products/new/", catalog_views.product_sheet, name="product_add"),
    path("products/<int:pk>/", catalog_views.product_sheet, name="product_edit"),
    path(
        "products/<int:pk>/remove/", catalog_views.product_remove, name="product_remove"
    ),
    path("", include("accounts.urls")),
    path("", include("staff.urls")),
    path("", include("customers.urls")),
    path("", include("orders.urls")),
    path("admin/", admin.site.urls),
    path("styleguide/", views.styleguide, name="styleguide"),
    path("styleguide/shell/", views.shell_check, name="shell_check"),
    path("styleguide/sheet/", views.sample_sheet, name="sample_sheet"),
    path("manifest.webmanifest", views.manifest, name="manifest"),
]
