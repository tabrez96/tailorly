from django import forms

from catalog.models import Product, ProductOption
from orders.items import material_hint, price_hint, price_message, products_for

PRICE_INVALID = "Enter a price in rupees, like 1800."


class RupeeField(forms.DecimalField):
    """A price that accepts commas and the rupee sign."""

    def to_python(self, value):
        if isinstance(value, str):
            value = value.replace(",", "").replace("₹", "").strip()
        return super().to_python(value)


class ItemForm(forms.Form):
    type = forms.ChoiceField(
        label="Type",
        choices=Product.TYPES,
        widget=forms.RadioSelect,
        error_messages={
            "required": "Choose Custom or Ready-made.",
            "invalid_choice": "Choose Custom or Ready-made.",
        },
    )
    product = forms.ModelChoiceField(
        label="Product",
        queryset=Product.objects.none(),
        widget=forms.RadioSelect,
        empty_label=None,
        error_messages={
            "required": "Choose a product.",
            "invalid_choice": "Choose a product from the list.",
        },
    )
    price = RupeeField(
        label="Price (₹)",
        required=False,
        max_digits=12,
        decimal_places=2,
        min_value=0,
        widget=forms.TextInput(
            attrs={"inputmode": "decimal", "autocomplete": "off", "x-model": "price"}
        ),
        error_messages={
            "invalid": PRICE_INVALID,
            "max_digits": PRICE_INVALID,
            "max_decimal_places": PRICE_INVALID,
            "max_whole_digits": PRICE_INVALID,
            "min_value": "Enter a price of ₹0 or more.",
        },
    )
    notes = forms.CharField(
        label="Notes for this item",
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 3, "placeholder": "Colour, size or anything to remember"}
        ),
    )

    def __init__(
        self, *args, type_: str, product: Product | None, options=(), **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.chosen = product
        self.options = list(options)
        self.fields["product"].queryset = products_for(type_)
        if product:
            self.fields["price"].help_text = price_hint(product)
        for o in self.options:
            if o.answer == ProductOption.YES_NO:
                self.fields[f"opt_{o.pk}"] = forms.ChoiceField(
                    label=o.name,
                    required=False,
                    choices=[("No", "No"), ("Yes", "Yes")],
                    initial="No",
                    widget=forms.RadioSelect(attrs={"class": "seg__input"}),
                )
            else:
                self.fields[f"opt_{o.pk}"] = forms.ChoiceField(
                    label=o.name,
                    required=False,
                    choices=[(c, c) for c in o.choices],
                    widget=forms.RadioSelect(attrs={"class": "ochip__input"}),
                )

    def clean(self):
        data = super().clean()
        if "price" not in self.errors and data.get("price") is None:
            self.add_error("price", price_message(data.get("product") or self.chosen))
        return data

    def answers(self) -> list[dict]:
        """The option answers, in option order (after is_valid())."""
        result = []
        for o in self.options:
            value = self.cleaned_data.get(f"opt_{o.pk}")
            if o.answer == ProductOption.YES_NO:
                value = value or "No"
            if value:
                result.append({"name": o.name, "answer": value})
        return result

    def option_rows(self) -> list[dict]:
        return [
            {
                "field": self[f"opt_{o.pk}"],
                "yes_no": o.answer == ProductOption.YES_NO,
                "hint": material_hint(o),
            }
            for o in self.options
        ]
