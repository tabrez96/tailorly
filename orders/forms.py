from django import forms
from django.utils import timezone

from catalog.models import Product, ProductOption
from core.formats import format_duration
from orders.items import item_products, material_hint, price_hint, price_message
from orders.making import parse_duration
from orders.models import Order, OrderItem, Payment
from production.estimates import usual_minutes
from staff.attendance import parse_decimal
from staff.models import Employee

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
        self,
        *args,
        type_: str,
        product: Product | None,
        options=(),
        keep_pk: int | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.chosen = product
        self.options = list(options)
        self.fields["product"].queryset = item_products(type_, keep_pk)
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


class OrderEditForm(forms.Form):
    """The due date of a placed order; items are edited on their own pages."""

    due_date = forms.DateField(
        label="Due date",
        required=False,
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )

    def __init__(self, *args, order, **kwargs):
        super().__init__(*args, **kwargs)
        self.order = order
        self.custom = order.items.filter(type=Product.CUSTOM).exists()
        if not self.custom:
            del self.fields["due_date"]  # ready-made sales have no due date

    def clean_due_date(self):
        due = self.cleaned_data["due_date"]
        if due is None:
            raise forms.ValidationError("Choose a due date.")
        # An overdue order may keep its date; a new date can't be in the past.
        if due != self.order.due_date and due < timezone.localdate():
            raise forms.ValidationError("Choose today or a later date.")
        return due


class PlaceForm(forms.Form):
    """Who pays, making it and payment: all Create order needs besides the items."""

    paid_by = forms.ChoiceField(choices=Order.PAID_BY, initial=Order.CUSTOMER)
    due_date = forms.DateField(
        label="Due date",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    assignee = forms.ModelChoiceField(
        Employee.objects.filter(active=True),
        required=False,
        empty_label="Not assigned yet",
        label="Assign to",
    )
    advance = RupeeField(
        label="Advance received (₹)",
        required=False,
        min_value=0,
        max_digits=12,
        decimal_places=2,
        widget=forms.TextInput(
            attrs={"inputmode": "decimal", "autocomplete": "off", "x-model": "advance"}
        ),
        error_messages={
            "invalid": PRICE_INVALID,
            "max_digits": PRICE_INVALID,
            "max_decimal_places": PRICE_INVALID,
            "max_whole_digits": PRICE_INVALID,
            "min_value": "Enter an amount of ₹0 or more.",
        },
    )
    method = forms.ChoiceField(
        choices=Payment.METHODS,
        initial=Payment.CASH,
        widget=forms.RadioSelect,
        label="Method",
    )

    def __init__(self, *args, order, items, total, **kwargs):
        if args and args[0] is not None and args[0].get("paid_by") == Order.FREE:
            # Free orders ignore the payment inputs, even if hidden fields post junk.
            data = args[0].copy()
            data.pop("advance", None)
            data.pop("method", None)
            args = (data, *args[1:])
        super().__init__(*args, **kwargs)
        if self.is_bound and self.data.get("paid_by") == Order.FREE:
            self.fields["method"].required = False
        self.total = total
        self.customer_error = ""
        self.items_error = ""
        self.estimates: dict[int, int | None] = {}
        self.custom = any(i.type == Product.CUSTOM for i in items)
        self._has_customer = order.customer_id is not None
        self._has_items = bool(items)
        self._estimate_items = {}
        for n, item in enumerate(items, 1):
            if item.type != Product.CUSTOM:
                continue
            name = f"estimate_{item.pk}"
            self.fields[name] = forms.CharField(
                required=False,
                label=f"{n} {item.name}",
                initial=format_duration(
                    item.estimate_minutes or usual_minutes(item.product)
                ),
            )
            self._estimate_items[name] = item.pk
        self.estimate_names = list(self._estimate_items)

    def clean(self):
        data = super().clean()
        if not self._has_customer:
            self.customer_error = "Choose a customer, or add a new one."
        if not self._has_items:
            self.items_error = "Add at least one item."
        for name, pk in self._estimate_items.items():
            if name in self.errors:
                continue
            try:
                self.estimates[pk] = parse_duration(data.get(name, ""))
            except ValueError as e:
                self.add_error(name, str(e))
        if self.custom and "due_date" not in self.errors:
            due = data.get("due_date")
            if due is None:
                self.add_error("due_date", "Choose a due date.")
            elif due < timezone.localdate():
                self.add_error("due_date", "Choose today or a later date.")
        advance = data.get("advance")
        if (
            data.get("paid_by") == Order.CUSTOMER
            and advance is not None
            and "advance" not in self.errors
            and advance > self.total
        ):
            self.add_error("advance", "The advance can't be more than the total.")
        return data

    def ready(self) -> bool:
        return self.is_valid() and not self.customer_error and not self.items_error

    def error_count(self) -> int:
        """Things to fix (after is_valid())."""
        return len(self.errors) + bool(self.customer_error) + bool(self.items_error)


class PaymentForm(forms.Form):
    amount = forms.CharField(
        label="Amount (₹)", widget=forms.TextInput(attrs={"inputmode": "decimal"})
    )
    date = forms.DateField(
        label="Date",
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    method = forms.ChoiceField(
        label="Method", choices=Payment.METHODS, widget=forms.RadioSelect
    )

    def clean_amount(self):
        value = parse_decimal(self.cleaned_data["amount"].replace(",", ""))
        if (
            value is None
            or value <= 0
            or value.adjusted() >= 10
            or value.as_tuple().exponent < -2
        ):
            raise forms.ValidationError("Enter an amount above zero.")
        return value

    def clean_date(self):
        date = self.cleaned_data["date"]
        if date > timezone.localdate():
            raise forms.ValidationError("Pick today or an earlier date.")
        return date


class MaterialLineForm(forms.Form):
    """Validation and errors for the add/edit material sheet (inputs are hand-made)."""

    item = forms.ModelChoiceField(
        OrderItem.objects.none(), widget=forms.RadioSelect, empty_label=None
    )
    material = forms.ModelChoiceField(
        Product.objects.none(),
        required=False,
        error_messages={
            "required": "Choose a material.",
            "invalid_choice": "Choose a material.",
        },
    )
    qty = forms.CharField(required=False)
    cost = forms.CharField(required=False)
    sell = forms.CharField(required=False)
    on_bill = forms.BooleanField(required=False)
    bought_on = forms.DateField(
        label="Bought on",
        required=False,
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )

    def __init__(self, *args, order, adding: bool, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item"].queryset = order.items.all()
        self.fields["material"].queryset = Product.objects.filter(
            kind=Product.SECONDARY, active=True
        )
        self.fields["material"].required = adding
        self.amounts = None

    def clean(self):
        from orders import finishing  # finishing imports this module

        cd = super().clean()
        answer, errors = finishing.clean_answer(
            cd.get("qty", ""),
            cd.get("cost", ""),
            cd.get("sell", ""),
            cost_optional=True,
        )
        for field, message in errors.items():
            self.add_error(field, message)
        if answer:
            self.amounts = answer
        return cd
