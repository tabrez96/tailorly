from django.urls import path

from customers import views

urlpatterns = [
    path("customers/", views.customers, name="customers"),
    path("customers/new/", views.customer_sheet, name="customer_add"),
    path("customers/<int:pk>/", views.customer, name="customer"),
    path("customers/<int:pk>/edit/", views.customer_sheet, name="customer_edit"),
]
