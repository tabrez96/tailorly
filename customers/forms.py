from django import forms
from django.core.exceptions import ValidationError

from accounts.phones import is_valid_phone, normalize_phone
from customers.models import Customer


class CustomerForm(forms.ModelForm):
    # Declared here so pasted numbers like "+91 98450-12345" pass the 10-character
    # model limit until clean_phone normalizes them.
    phone = forms.CharField(
        label="Phone (optional)",
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "off"}),
    )

    class Meta:
        model = Customer
        fields = ["name", "phone", "notes"]
        labels = {"name": "Name", "notes": "Notes (optional)"}
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}
        error_messages = {"name": {"required": "Enter a name."}}

    def clean_phone(self) -> str:
        raw = self.cleaned_data["phone"].strip()
        if not raw:
            return ""
        phone = normalize_phone(raw)
        if not is_valid_phone(phone):
            raise ValidationError("Enter a 10-digit mobile number.")
        return phone
