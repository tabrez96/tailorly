from django.urls import path

from staff import views

urlpatterns = [
    path("settings/staff/", views.staff, name="staff"),
    path("settings/staff/add/", views.employee_add, name="employee_add"),
    path("settings/staff/<int:pk>/edit/", views.employee_edit, name="employee_edit"),
    path("settings/staff/<int:pk>/photo/", views.employee_photo, name="employee_photo"),
    path("settings/staff/<int:pk>/days/<str:day>/", views.day_sheet, name="day_sheet"),
    path("settings/staff/<int:pk>/days/<str:day>/end/", views.day_end, name="day_end"),
]
