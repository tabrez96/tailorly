from io import BytesIO

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from staff.forms import DayForm, EmployeeForm

DATA = {
    "name": "Ali Khan",
    "phone": "+91 98450-12345",
    "daily_wage": "800",
    "overtime_multiplier": "1.5",
    "password": "secret-pass-1",
}


def add(**changes):
    form = EmployeeForm(DATA | changes)
    assert form.is_valid(), form.errors
    return form.save()


def test_add_creates_employee_user_in_employee_role(db):
    employee = add()
    assert employee.phone == "9845012345"
    user = employee.user
    assert user.username == "9845012345"
    assert user.check_password("secret-pass-1")
    assert user.groups.filter(name="employee").exists()
    assert user.first_name == "Ali Khan"


def test_add_requires_password(db):
    form = EmployeeForm(DATA | {"password": ""})
    assert not form.is_valid()
    assert "password" in form.errors


def test_duplicate_phone_rejected(db):
    User.objects.create_user("9845012345", password="x")
    form = EmployeeForm(DATA)
    assert not form.is_valid()
    assert form.errors["phone"] == ["Another account already uses this number."]


def test_duplicate_phone_of_other_employee_rejected(db):
    add()
    form = EmployeeForm(DATA | {"name": "Other"})
    assert form.errors["phone"] == ["Another account already uses this number."]


def test_invalid_phone_rejected(db):
    form = EmployeeForm(DATA | {"phone": "12345"})
    assert form.errors["phone"] == ["Enter a 10-digit phone number."]


def test_negative_wage_and_zero_multiplier_rejected(db):
    form = EmployeeForm(DATA | {"daily_wage": "-1", "overtime_multiplier": "0"})
    assert form.errors["daily_wage"] == ["Enter a wage of 0 or more."]
    assert form.errors["overtime_multiplier"] == ["Enter a number above 0."]


def edit(employee, **changes):
    data = DATA | {"phone": employee.phone, "password": ""} | changes
    form = EmployeeForm(data, instance=employee)
    assert form.is_valid(), form.errors
    return form.save()


def test_edit_blank_password_keeps_old(db):
    employee = edit(add(), name="Ali K")
    employee.user.refresh_from_db()
    assert employee.user.check_password("secret-pass-1")
    assert employee.user.first_name == "Ali K"


def test_edit_password_resets(db):
    employee = edit(add(), password="another-pass-2")
    employee.user.refresh_from_db()
    assert employee.user.check_password("another-pass-2")


def test_edit_changes_phone_on_user(db):
    employee = edit(add(), phone="9845099999")
    employee.user.refresh_from_db()
    assert employee.user.username == "9845099999"


def test_hints_follow_posted_values(db):
    form = EmployeeForm(DATA | {"daily_wage": "1600"})
    assert "₹200" in form.fields["daily_wage"].help_text
    assert "₹300 an hour" in form.fields["overtime_multiplier"].help_text
    assert form.fields["phone"].help_text == "Your employee signs in with this number."
    edit_form = EmployeeForm(instance=add())
    assert edit_form.fields["phone"].help_text == "Ali signs in with this number."
    assert "₹100" in edit_form.fields["daily_wage"].help_text


def test_photo_resized_to_200_square(db, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    buffer = BytesIO()
    Image.new("RGB", (800, 600), "red").save(buffer, "PNG")
    upload = SimpleUploadedFile("me.png", buffer.getvalue(), "image/png")
    form = EmployeeForm(DATA, {"photo": upload})
    assert form.is_valid(), form.errors
    employee = form.save()
    with Image.open(employee.photo.path) as img:
        assert img.size == (200, 200)
        assert img.format == "JPEG"


@pytest.mark.parametrize(
    ("start", "end", "ok"),
    [("10:00", "09:00", False), ("09:00", "10:00", True), ("09:00", "", True)],
)
def test_day_form_end_before_start_error(start, end, ok):
    form = DayForm({"start": start, "end": end})
    assert form.is_valid() is ok
    if not ok:
        assert form.errors["end"] == ["End must be after start."]


def test_huge_wage_gives_field_error_not_crash(db):
    form = EmployeeForm(DATA | {"daily_wage": "1E+30"})
    assert not form.is_valid()
    assert "daily_wage" in form.errors
    assert form.fields["daily_wage"].help_text == "Hourly rate is the daily wage ÷ 8."


def test_edit_without_linked_user_requires_password(db):
    from staff.models import Employee

    employee = Employee.objects.create(name="Ali Khan", phone="9845012345")
    data = DATA | {"phone": employee.phone, "password": ""}
    form = EmployeeForm(data, instance=employee)
    assert not form.is_valid()
    assert "password" in form.errors


def test_truncated_photo_is_a_field_error(db, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    buffer = BytesIO()
    noise = Image.effect_noise((300, 300), 80).convert("RGB")
    noise.save(buffer, "JPEG")
    data = buffer.getvalue()
    upload = SimpleUploadedFile("me.jpg", data[: len(data) // 2], "image/jpeg")
    form = EmployeeForm(DATA, {"photo": upload})
    assert not form.is_valid()
    assert "photo" in form.errors


def test_day_form_rejects_seconds():
    form = DayForm({"start": "09:00:30", "end": ""})
    assert "start" in form.errors
    assert not DayForm({"start": "09:00", "end": "10:15:10"}).is_valid()


@pytest.mark.parametrize("wage", ["1E+1000000", "1E-999999"])
def test_extreme_decimals_use_generic_hint(db, wage):
    form = EmployeeForm(DATA | {"daily_wage": wage})
    assert not form.is_valid()
    assert form.fields["daily_wage"].help_text == "Hourly rate is the daily wage ÷ 8."


def test_extreme_multiplier_keeps_overtime_hint_short(db):
    form = EmployeeForm(DATA | {"overtime_multiplier": "1E-999999"})
    assert not form.is_valid()
    assert len(form.fields["overtime_multiplier"].help_text) < 100


def test_valid_wage_still_gives_hourly_hint(db):
    form = EmployeeForm(DATA | {"daily_wage": "800"})
    assert form.fields["daily_wage"].help_text == "Hourly rate: ₹100 (daily wage ÷ 8)."


def test_password_keeps_surrounding_whitespace(db):
    employee = add(password="tailor7 ")
    assert employee.user.check_password("tailor7 ")


def test_phone_collision_with_employee_without_user(db):
    from staff.models import Employee

    Employee.objects.create(name="Other", phone="9845012345")
    form = EmployeeForm(DATA)
    assert form.errors["phone"] == ["Another account already uses this number."]
