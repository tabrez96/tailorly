from django import forms
from django.core.exceptions import ValidationError
from django.db.models.functions import Lower

from accounts.phones import is_valid_phone, normalize_phone
from catalog.models import Product
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


def garments_to_add(customer: Customer):
    """Active custom products the customer has no measurement set for."""
    return (
        Product.objects.filter(kind=Product.PRIMARY, type=Product.CUSTOM, active=True)
        .exclude(measurement_sets__customer=customer)
        .order_by(Lower("name"))
    )


class GarmentForm(forms.Form):
    product = forms.ModelChoiceField(
        queryset=Product.objects.none(),
        label="Garment",
        widget=forms.RadioSelect,
        empty_label=None,
        error_messages={
            "required": "Choose a garment.",
            "invalid_choice": "Choose a garment from the list.",
        },
    )

    def __init__(self, *args, customer: Customer, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = garments_to_add(customer)
