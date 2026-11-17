from django.contrib import admin
from django.urls import path

from core import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("styleguide/", views.styleguide, name="styleguide"),
    path("manifest.webmanifest", views.manifest, name="manifest"),
]
