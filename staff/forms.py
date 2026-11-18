from django import forms
from django.contrib.auth.models import User
from django.db import transaction
from PIL import Image

from accounts.phones import is_valid_phone, normalize_phone
from accounts.roles import EMPLOYEE, add_to_role
from staff.attendance import first_name, overtime_hint, parse_decimal, wage_hint
from staff.models import Employee
from staff.photos import resize_photo


class EmployeeForm(forms.ModelForm):
    # Declared here so pasted numbers like "+91 98450-12345" pass the 10-character
    # model limit until clean_phone normalizes them.
    phone = forms.CharField(
        label="Phone number",
        widget=forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "off"}),
    )
    password = forms.CharField(
        label="Password",
        required=False,
        min_length=6,
        strip=False,
        widget=forms.PasswordInput(
            render_value=False, attrs={"autocomplete": "new-password"}
        ),
    )

    class Meta:
        model = Employee
        fields = ["name", "phone", "daily_wage", "overtime_multiplier", "photo"]
        labels = {
            "name": "Name",
            "daily_wage": "Daily wage (₹)",
            "overtime_multiplier": "Overtime multiplier",
            "photo": "Photo (optional)",
        }
        widgets = {
            "daily_wage": forms.TextInput(attrs={"inputmode": "decimal"}),
            "overtime_multiplier": forms.TextInput(attrs={"inputmode": "decimal"}),
            "photo": forms.FileInput(attrs={"accept": "image/*"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        adding = self.instance.pk is None
        self.fields["password"].required = self.instance.user_id is None
        wage, multiplier = (
            self._current("daily_wage"),
            self._current("overtime_multiplier"),
        )
        self.fields["phone"].help_text = (
            "Your employee signs in with this number."
            if adding
            else f"{first_name(self.instance.name)} signs in with this number."
        )
        self.fields["daily_wage"].help_text = wage_hint(wage)
        self.fields["overtime_multiplier"].help_text = overtime_hint(wage, multiplier)
        if self.instance.user_id is not None:
            self.fields[
                "password"
            ].help_text = "Leave empty to keep the current password."

    def _current(self, name):
        """The posted value when it is a number, else the saved one (None on add)."""
        if self.is_bound:
            value = parse_decimal(self.data.get(name, ""))
            if value is not None and self._in_range(name, value):
                return value
        return getattr(self.instance, name) if self.instance.pk else None

    def _in_range(self, name, value):
        """Hints must not break on numbers the field will reject as too large."""
        field = Employee._meta.get_field(name)
        return (
            value.is_finite()
            and value.adjusted() < field.max_digits - field.decimal_places
            and value.as_tuple().exponent >= -field.decimal_places
        )

    def clean_phone(self):
        phone = normalize_phone(self.cleaned_data["phone"])
        if not is_valid_phone(phone):
            raise forms.ValidationError("Enter a 10-digit phone number.")
        users = User.objects.filter(username=phone).exclude(pk=self.instance.user_id)
        employees = Employee.objects.filter(phone=phone).exclude(pk=self.instance.pk)
        if users.exists() or employees.exists():
            raise forms.ValidationError("Another account already uses this number.")
        return phone

    def clean_daily_wage(self):
        wage = self.cleaned_data["daily_wage"]
        if wage < 0:
            raise forms.ValidationError("Enter a wage of 0 or more.")
        return wage

    def clean_overtime_multiplier(self):
        multiplier = self.cleaned_data["overtime_multiplier"]
        if multiplier <= 0:
            raise forms.ValidationError("Enter a number above 0.")
        return multiplier

    def clean_photo(self):
        upload = self.cleaned_data.get("photo")
        self._resized_photo = None
        if upload and "photo" in self.changed_data:
            try:
                self._resized_photo = resize_photo(upload)
            except OSError, SyntaxError, ValueError, Image.DecompressionBombError:
                raise forms.ValidationError(
                    "This image can't be read. Try another."
                ) from None
        return upload

    def save(self, commit=True):
        employee = super().save(commit=False)
        with transaction.atomic():
            if self._resized_photo:
                employee.photo.save("photo.jpg", self._resized_photo, save=False)
            user = employee.user or User()
            user.username = employee.phone
            user.first_name = employee.name
            if self.cleaned_data["password"]:
                user.set_password(self.cleaned_data["password"])
            user.save()
            add_to_role(user, EMPLOYEE)
            employee.user = user
            employee.save()
        return employee


class DayForm(forms.Form):
    start = forms.TimeField(
        label="Start",
        widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        input_formats=["%H:%M"],
    )
    end = forms.TimeField(
        label="End",
        required=False,
        help_text="Leave empty if the day is still going.",
        input_formats=["%H:%M"],
        widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
    )

    def clean(self):
        data = super().clean()
        if data.get("start") and data.get("end") and data["end"] < data["start"]:
            self.add_error("end", "End must be after start.")
        return data
