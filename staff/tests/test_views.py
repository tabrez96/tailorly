from datetime import date, timedelta

import pytest
from django.contrib.auth.models import Group, User
from django.test import Client
from django.utils import timezone

from staff.models import DayRecord, Employee

PARTIAL = {"HX-Request": "true", "HX-Request-Type": "partial"}


@pytest.fixture
def owner(db):
    user = User.objects.create_user("owner", password="x")
    user.groups.add(Group.objects.get_or_create(name="owner")[0])
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def employee(db):
    user = User.objects.create_user("9000011117", password="x", first_name="Ali Khan")
    e = Employee.objects.create(
        name="Ali Khan", phone="9000011117", daily_wage=800, user=user
    )
    client = Client()
    client.force_login(user)
    e.client = client
    return e


def test_staff_page_owner_only(owner, employee):
    response = employee.client.get("/settings/staff/")
    assert response.status_code == 302
    assert response["Location"] == "/my-work/"
    assert Client().get("/settings/staff/")["Location"].startswith("/sign-in/")


def test_staff_page_lists_week_rows(owner, employee):
    response = owner.get("/settings/staff/?week=2026-11-12")
    html = response.content.decode()
    assert "Mon 9 – Sun 15 Nov" in html
    assert html.count('class="list__row"') == 7
    assert 'data-subpage="1"' in html
    assert "₹800 a day · ₹100 an hour · overtime 1×" in html
    assert "week=2026-11-02" in html
    assert "week=2026-11-16" in html


def test_staff_page_picker_and_bad_params(owner, employee):
    other = Employee.objects.create(name="Zed", phone="9000011118")
    html = owner.get(f"/settings/staff/?e={other.pk}&week=junk").content.decode()
    assert 'aria-label="Employee"' in html
    assert "Zed" in html
    assert "overtime" in html
    assert owner.get("/settings/staff/?e=abc").status_code == 200


def test_staff_empty_state(owner):
    html = owner.get("/settings/staff/").content.decode()
    assert "Add your employee to track their days and pay." in html


def test_owner_adds_employee_then_employee_signs_in(owner):
    response = owner.post(
        "/settings/staff/add/",
        {
            "name": "Meera Iyer",
            "phone": "98450 12345",
            "daily_wage": "700",
            "overtime_multiplier": "1.5",
            "password": "secret-pass-1",
        },
        headers=PARTIAL,
    )
    assert response.status_code == 204
    assert "/settings/staff/?e=" in response["HX-Location"]
    assert Employee.objects.get().daily_wage == 700
    signed_in = Client().post(
        "/sign-in/", {"username": "9845012345", "password": "secret-pass-1"}
    )
    assert signed_in.status_code == 302
    assert signed_in["Location"] == "/my-work/"


def test_add_without_htmx_redirects(owner):
    response = owner.post(
        "/settings/staff/add/",
        {
            "name": "Meera",
            "phone": "9845012345",
            "daily_wage": "700",
            "overtime_multiplier": "1",
            "password": "secret-pass-1",
        },
    )
    assert response.status_code == 302


def test_add_invalid_returns_422(owner):
    response = owner.post("/settings/staff/add/", {"name": ""}, headers=PARTIAL)
    assert response.status_code == 422
    assert "need" in response.content.decode()


def test_edit_form_shows_reset_password(owner, employee):
    html = owner.get(f"/settings/staff/{employee.pk}/edit/").content.decode()
    assert "Reset password" in html
    assert "Ali signs in with this number." in html
    assert owner.get("/settings/staff/999/edit/").status_code == 404


def test_day_sheet_get_prefills(owner, employee):
    day = date(2026, 11, 10)
    owner.post(
        f"/settings/staff/{employee.pk}/days/{day}/", {"start": "09:00", "end": "17:00"}
    )
    html = owner.get(f"/settings/staff/{employee.pk}/days/{day}/").content.decode()
    assert 'value="09:00"' in html
    assert 'value="17:00"' in html


def test_day_sheet_post_saves_edited_record_and_retargets(owner, employee):
    day = date(2026, 11, 10)
    response = owner.post(
        f"/settings/staff/{employee.pk}/days/{day}/", {"start": "09:00", "end": "17:30"}
    )
    assert response["HX-Retarget"] == "#staff-days"
    assert "edited by owner" in response.content.decode()
    record = DayRecord.objects.get()
    assert record.edited_by_owner
    assert timezone.localtime(record.end).strftime("%H:%M") == "17:30"


def test_day_sheet_invalid_returns_422(owner, employee):
    response = owner.post(
        f"/settings/staff/{employee.pk}/days/2026-11-10/",
        {"start": "10:00", "end": "09:00"},
    )
    assert response.status_code == 422
    assert not DayRecord.objects.exists()


def test_day_sheet_future_date_404(owner, employee):
    future = timezone.localdate() + timedelta(days=1)
    assert owner.get(f"/settings/staff/{employee.pk}/days/{future}/").status_code == 404


def test_day_sheet_bad_date_404(owner, employee):
    assert owner.get(f"/settings/staff/{employee.pk}/days/nope/").status_code == 404


def test_owner_end_day_sets_end_and_edited(owner, employee):
    today = timezone.localdate()
    DayRecord.objects.create(
        employee=employee, date=today, start=timezone.now() - timedelta(minutes=1)
    )
    # start may sit just before local midnight; the view only acts on today's record
    response = owner.post(f"/settings/staff/{employee.pk}/days/{today}/end/")
    assert response.status_code == 200
    record = DayRecord.objects.get()
    assert record.end is not None
    assert record.edited_by_owner
    assert (
        owner.get(f"/settings/staff/{employee.pk}/days/{today}/end/").status_code == 405
    )


def test_owner_end_day_past_date_is_noop(owner, employee):
    today = timezone.localdate()
    DayRecord.objects.create(employee=employee, date=today, start=timezone.now())
    yesterday = today - timedelta(days=1)
    response = owner.post(f"/settings/staff/{employee.pk}/days/{yesterday}/end/")
    assert response.status_code == 200
    record = DayRecord.objects.get()
    assert record.end is None
    assert not record.edited_by_owner


def test_employee_start_and_end_my_day(employee):
    client = employee.client
    response = client.post("/my-work/day/start/", headers=PARTIAL)
    assert response.status_code == 200
    assert "Day started" in response.content.decode()
    client.post("/my-work/day/start/", headers=PARTIAL)
    assert employee.days.count() == 1
    response = client.post("/my-work/day/end/", headers=PARTIAL)
    assert "Day ended at" in response.content.decode()
    assert employee.days.get().end is not None


def test_my_work_shows_start_button(employee):
    html = employee.client.get("/my-work/").content.decode()
    assert "Start my day" in html
    assert "Good" in html


def test_start_my_day_without_employee_404(db):
    user = User.objects.create_user("noemp", password="x")
    client = Client()
    client.force_login(user)
    assert client.post("/my-work/day/start/").status_code == 404
    assert "Start my day" not in client.get("/my-work/").content.decode()


def test_start_my_day_get_not_allowed(employee):
    assert employee.client.get("/my-work/day/start/").status_code == 405


def test_photo_view_owner_only_and_404_without_photo(
    owner, employee, settings, tmp_path
):
    settings.MEDIA_ROOT = tmp_path
    url = f"/settings/staff/{employee.pk}/photo/"
    assert owner.get(url).status_code == 404
    from django.core.files.base import ContentFile

    employee.photo.save("p.jpg", ContentFile(b"jpeg"), save=True)
    response = owner.get(url)
    assert response.status_code == 200
    assert b"".join(response.streaming_content) == b"jpeg"
    assert response["Cache-Control"] == "private, max-age=3600"
    assert employee.client.get(url).status_code == 302


def test_photo_view_missing_file_is_404(owner, employee, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    employee.photo.name = "gone.jpg"
    employee.save()
    assert owner.get(f"/settings/staff/{employee.pk}/photo/").status_code == 404


def test_edit_form_without_user_shows_password_field_directly(owner):
    from staff.models import Employee

    bare = Employee.objects.create(name="Bare", phone="9000000001")
    body = owner.get(f"/settings/staff/{bare.pk}/edit/").content.decode()
    assert "Reset password" not in body
    assert "Leave empty to keep" not in body
    assert 'name="password"' in body


def test_day_buttons_have_ids_for_focus(owner, employee):
    from django.utils import timezone

    from staff.models import DayRecord

    today = timezone.localdate()
    DayRecord.objects.create(employee=employee, date=today, start=timezone.now())
    body = owner.get("/settings/staff/").content.decode()
    assert f'id="day-{today.isoformat()}"' in body


def test_staff_page_extreme_week_does_not_crash(owner, employee):
    assert owner.get("/settings/staff/?week=9999-12-31").status_code == 200
    assert owner.get("/settings/staff/?week=0001-01-01").status_code == 200


def test_today_open_row_opens_sheet_and_keeps_end_day(owner, employee):
    now = timezone.now()
    DayRecord.objects.create(
        employee=employee, date=timezone.localdate(), start=now - timedelta(hours=1)
    )
    html = owner.get("/settings/staff/").content.decode()
    today = timezone.localdate().isoformat()
    assert f"/settings/staff/{employee.pk}/days/{today}/" in html
    assert "End day" in html
    assert 'aria-label="Fix' not in html
