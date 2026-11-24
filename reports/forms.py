from django import forms

from reports.models import ShopBill


class ShopBillForm(forms.ModelForm):
    class Meta:
        model = ShopBill
        fields = ["name", "amount", "date"]
        labels = {"name": "Name", "amount": "Amount (₹)", "date": "Date"}
        widgets = {"date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}
