from django.contrib import admin
from django.contrib.auth.views import LoginView
from django.urls import path

from core import views
from production import views as production_views
from staff import views as staff_views
from today import views as today_views

urlpatterns = [
    path("", today_views.today, name="today"),
    path("my-work/", production_views.my_work, name="my_work"),
    path("my-pay/", staff_views.my_pay, name="my_pay"),
    path(
        "sign-in/",
        LoginView.as_view(template_name="accounts/sign_in.html"),
        name="sign_in",
    ),
    path("admin/", admin.site.urls),
    path("styleguide/", views.styleguide, name="styleguide"),
    path("styleguide/shell/", views.shell_check, name="shell_check"),
    path("styleguide/sheet/", views.sample_sheet, name="sample_sheet"),
    path("manifest.webmanifest", views.manifest, name="manifest"),
]
