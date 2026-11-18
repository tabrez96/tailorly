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
    path("my-pay/", staff_views.my_pay, name="my_pay"),
    path("products/", catalog_views.products, name="products"),
    path("", include("accounts.urls")),
    path("admin/", admin.site.urls),
    path("styleguide/", views.styleguide, name="styleguide"),
    path("styleguide/shell/", views.shell_check, name="shell_check"),
    path("styleguide/sheet/", views.sample_sheet, name="sample_sheet"),
    path("manifest.webmanifest", views.manifest, name="manifest"),
]
