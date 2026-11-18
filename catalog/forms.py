from dataclasses import asdict
from decimal import Decimal, InvalidOperation

from django import forms
from django.db import transaction
from django.utils.html import format_html

from catalog.editor import (
    OPTIONS_FIX,
    EditorError,
    OptionData,
    load_list,
    option_to_dict,
    parse_measurements,
    parse_options,
)
from catalog.models import Product, ProductOption
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


def _option_fields(option: OptionData) -> dict:
    fields = asdict(option)
    fields["material_id"] = fields.pop("material")
    return fields


class ProductForm(_SheetForm):
    kind_value = Product.PRIMARY
    usual_price = _amount_field("Price (₹)", "Enter a price.")
    type = forms.ChoiceField(
        label="Type", choices=Product.TYPES, widget=forms.RadioSelect
    )
    measurements_json = forms.CharField(required=False, widget=forms.HiddenInput)
    options_json = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Product
        fields = ["name", "type"]

    def __init__(self, *args, materials=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.materials = list(materials)
        self.option_errors: list[dict] = []
        self.initial = {"kind": Product.PRIMARY, "type": Product.CUSTOM} | self.initial
        if not self.is_bound and self.instance.pk:
            self.initial["usual_price"] = amount_input(self.instance.usual_price)

    def clean_usual_price(self):
        return _clean_amount(self.cleaned_data["usual_price"])

    def _omitted(self, name: str) -> bool:
        """True when the post left the field out or blank (keep the saved list)."""
        return not self.data.get(name, "").strip()

    def clean_measurements_json(self):
        if self.data.get("type") == Product.READY_MADE:
            return []
        if self._omitted("measurements_json"):
            return None
        try:
            return parse_measurements(self.cleaned_data["measurements_json"])
        except EditorError as e:
            raise forms.ValidationError(e.message) from None

    def clean_options_json(self):
        if self._omitted("options_json"):
            return None
        try:
            options, errors = parse_options(
                self.cleaned_data["options_json"], {m.pk for m in self.materials}
            )
        except EditorError as e:
            raise forms.ValidationError(e.message) from None
        if any(errors):
            self.option_errors = errors
            raise forms.ValidationError(OPTIONS_FIX)
        return options

    def editor_state(self) -> dict:
        """What the measurement and option editors start from (for json_script)."""
        if self.is_bound:
            # Echo what was posted so nothing typed is lost.
            measurements = self._posted_list("measurements_json")
            options = self._posted_list("options_json")
        elif self.instance.pk:
            measurements = self.instance.measurement_fields
            options = [option_to_dict(o) for o in self.instance.options.all()]
        else:
            measurements, options = [], []
        return {
            "measurements": measurements,
            "options": options,
            "materials": [
                {"id": m.pk, "name": m.name, "unit": m.unit} for m in self.materials
            ],
            "errors": {
                "measurements": " ".join(self.errors.get("measurements_json", [])),
                "options": " ".join(self.errors.get("options_json", [])),
                "option": self.option_errors,
            },
        }

    def _posted_list(self, name: str) -> list:
        try:
            return load_list(self.data.get(name, ""))
        except ValueError:
            return []

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
        custom = self.cleaned_data["type"] == Product.CUSTOM
        measurements = self.cleaned_data["measurements_json"]
        if not custom:
            product.measurement_fields = []
        elif measurements is not None:
            product.measurement_fields = measurements
        options = self.cleaned_data["options_json"]
        with transaction.atomic():
            product = super().save(commit)
            if commit and options is not None:
                product.options.all().delete()
                ProductOption.objects.bulk_create(
                    ProductOption(
                        product=product,
                        position=i,
                        **_option_fields(o),
                    )
                    for i, o in enumerate(options)
                )
        return product


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
