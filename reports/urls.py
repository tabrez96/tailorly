from django.urls import path

from reports import views

urlpatterns = [
    path("settings/running-costs/", views.running_costs, name="running_costs"),
    path("reports/sales/", views.sales_report, name="sales_report"),
    path("reports/profit/", views.profit_report, name="profit_report"),
    path("reports/payments/", views.payments_report, name="payments_report"),
    path("reports/staff/", views.staff_report, name="staff_report"),
    path("reports/profit/bills/new/", views.bill_new, name="bill_new"),
]
