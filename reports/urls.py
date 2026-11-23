from django.urls import path

from reports import views

urlpatterns = [
    path("settings/running-costs/", views.running_costs, name="running_costs"),
]
