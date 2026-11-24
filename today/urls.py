from django.urls import path

from today import views

urlpatterns = [
    path("today/hero/", views.today_hero, name="today_hero"),
    path(
        "today/employees/<int:pk>/day/start/",
        views.today_start_day,
        name="today_start_day",
    ),
    path(
        "today/employees/<int:pk>/day/end/",
        views.today_end_day,
        name="today_end_day",
    ),
]
