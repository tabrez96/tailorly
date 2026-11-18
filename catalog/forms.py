from decimal import Decimal, InvalidOperation

from django import forms
from django.utils.html import format_html

from catalog.models import Product
from core.money import group_indian

KIND_CHOICES = [
    (Product.PRIMARY, "Primary: sold"),
    (Product.SECONDARY, "Secondary: material"),
]
AMOUNT_ERROR = "Enter an amount of 0 or more."


def parse_amount(text: str) -> Decimal | None:
    """'₹1,800', '1800.50', ' 120 ' -> Decimal.

    None when empty, not a number, negative, more than 2 decimals or more than
    10 whole digits (DecimalField(12, 2)).
    """
    cleaned = text.replace("₹", "").replace(",", "").replace(" ", "").strip()
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    if not value.is_finite() or value < 0:
        return None
    if value.as_tuple().exponent < -2 or value.adjusted() >= 10:
        return None
    return value


def amount_input(value: Decimal, *, rupee: bool = False) -> str:
    """Value shown in an amount input: whole rupees grouped, paise left plain."""
    if value != value.to_integral_value():
        return str(value)
    grouped = group_indian(str(int(value)))
    return f"₹{grouped}" if rupee else grouped


def _amount_field(label, required_message, **kwargs):
    return forms.CharField(
        label=label,
        error_messages={"required": required_message},
        widget=forms.TextInput(attrs={"inputmode": "decimal"}),
        **kwargs,
    )


def _clean_amount(value: str) -> Decimal:
    amount = parse_amount(value)
    if amount is None:
        raise forms.ValidationError(AMOUNT_ERROR)
    return amount


class _SheetForm(forms.ModelForm):
    """Shared by the product and material sheets."""

    kind_value = ""
    name = forms.CharField(
        label="Name",
        max_length=80,
        error_messages={"required": "Enter a name."},
    )
    kind = forms.ChoiceField(
        label="Kind", choices=KIND_CHOICES, widget=forms.RadioSelect
    )

    def clean_kind(self):
        kind = self.cleaned_data["kind"]
        if kind != self.kind_value:
            raise forms.ValidationError("Choose a kind.")
        return kind


class ProductForm(_SheetForm):
    kind_value = Product.PRIMARY
    usual_price = _amount_field("Price (₹)", "Enter a price.")
    type = forms.ChoiceField(
        label="Type", choices=Product.TYPES, widget=forms.RadioSelect
    )

    class Meta:
        model = Product
        fields = ["name", "type"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial = {"kind": Product.PRIMARY, "type": Product.CUSTOM} | self.initial
        if not self.is_bound and self.instance.pk:
            self.initial["usual_price"] = amount_input(self.instance.usual_price)

    def clean_usual_price(self):
        return _clean_amount(self.cleaned_data["usual_price"])

    def clean(self):
        cleaned = super().clean()
        used = self.instance.pk and self.instance.kind == Product.SECONDARY
        if used and self.instance.used_by_options.filter(product__active=True).exists():
            self.add_error(
                "kind",
                "Options on other products use this material. Change them first.",
            )
        return cleaned

    def save(self, commit=True):
        product = self.instance
        product.kind = Product.PRIMARY
        product.unit = ""
        product.usual_price = self.cleaned_data["usual_price"]
        if self.cleaned_data["type"] != Product.CUSTOM:
            product.measurement_fields = []
        return super().save(commit)


class MaterialForm(_SheetForm):
    kind_value = Product.SECONDARY
    unit = forms.ChoiceField(
        label="Sold and used by", choices=Product.UNITS, widget=forms.RadioSelect
    )
    cost_price = _amount_field(
        "Cost price", "Enter a cost price.", help_text="What you pay."
    )
    selling_price = _amount_field(
        "Selling price", "Enter a selling price.", help_text="If you bill it."
    )
    billed_by_default = forms.BooleanField(
        required=False,
        label="Bill it by default",
        help_text="Off: it comes with the garment price.",
    )

    class Meta:
        model = Product
        fields = ["name", "unit", "billed_by_default"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial = {
            "kind": Product.SECONDARY,
            "unit": "m",
            "billed_by_default": True,
        } | self.initial
        if not self.is_bound and self.instance.pk:
            self.initial["cost_price"] = amount_input(
                self.instance.cost_price, rupee=True
            )
            self.initial["selling_price"] = amount_input(
                self.instance.selling_price, rupee=True
            )
        unit = self.data.get("unit") if self.is_bound else self.initial["unit"]
        if unit not in dict(Product.UNITS):
            unit = "m"
        for name, text in (
            ("cost_price", "Cost price"),
            ("selling_price", "Selling price"),
        ):
            self.fields[name].label = format_html(
                '{} a <span x-text="unit">{}</span>', text, unit
            )

    def clean_cost_price(self):
        return _clean_amount(self.cleaned_data["cost_price"])

    def clean_selling_price(self):
        return _clean_amount(self.cleaned_data["selling_price"])

    def clean(self):
        cleaned = super().clean()
        if self.instance.pk and self.instance.kind == Product.PRIMARY:
            if self.instance.options.exists():
                self.add_error(
                    "kind", "Remove its options before you make it a material."
                )
        return cleaned

    def save(self, commit=True):
        product = self.instance
        product.kind = Product.SECONDARY
        product.type = ""
        product.measurement_fields = []
        product.cost_price = self.cleaned_data["cost_price"]
        product.selling_price = self.cleaned_data["selling_price"]
        return super().save(commit)
