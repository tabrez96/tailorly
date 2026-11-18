from customers.forms import CustomerForm


def form(**data):
    return CustomerForm({"name": "Meera", "phone": "", "notes": "", **data})


def test_phone_optional():
    f = form()
    assert f.is_valid()
    assert f.cleaned_data["phone"] == ""


def test_phone_normalised():
    for raw in ("+91 98450-22110", "098450 22110", "9845022110"):
        f = form(phone=raw)
        assert f.is_valid()
        assert f.cleaned_data["phone"] == "9845022110"


def test_phone_invalid():
    f = form(phone="12345")
    assert not f.is_valid()
    assert f.errors["phone"] == ["Enter a 10-digit mobile number."]


def test_name_required():
    f = form(name="   ")
    assert not f.is_valid()
    assert f.errors["name"] == ["Enter a name."]


def test_admin_uses_customer_form():
    from customers.admin import CustomerAdmin

    assert CustomerAdmin.form is CustomerForm
