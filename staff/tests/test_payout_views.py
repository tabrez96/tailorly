from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth.models import Group, User
from django.test import Client

from staff.models import DayRecord, Employee, Payout

IST = ZoneInfo("Asia/Kolkata")
PARTIAL = {"HX-Request": "true", "HX-Request-Type": "partial"}
WEEK = "2026-11-09"
URL = "/settings/staff/{}/payout/{}/"


@pytest.fixture(autouse=True)
def today(monkeypatch):
    def set_today(day):
        monkeypatch.setattr(
            "django.utils.timezone.localdate", lambda now=None: date(2026, 11, day)
        )

    set_today(16)
    return set_today


@pytest.fixture
def owner(db):
    user = User.objects.create_user("owner", password="x")
    user.groups.add(Group.objects.get_or_create(name="owner")[0])
    client = Client()
    client.force_login(user)
    return client


def make_employee(phone, wage=800, name="Ali Khan"):
    user = User.objects.create_user(phone, password="x", first_name=name)
    e = Employee.objects.create(name=name, phone=phone, daily_wage=wage, user=user)
    client = Client()
    client.force_login(user)
    e.client = client
    return e


@pytest.fixture
def employee(db):
    return make_employee("9000011117")


def record(employee, day, start=(9, 0), end=(17, 0)):
    DayRecord.objects.create(
        employee=employee,
        date=date(2026, 11, day),
        start=datetime(2026, 11, day, *start, tzinfo=IST),
        end=datetime(2026, 11, day, *end, tzinfo=IST) if end else None,
    )


@pytest.fixture
def week(employee):
    record(employee, 9, end=(19, 0))
    record(employee, 10)
    return employee


def pay(owner, employee, **extra):
    data = {"amount": "3,400", "paid_on": "2026-11-14", "method": "upi"} | extra
    return owner.post(URL.format(employee.pk, WEEK), data, headers=PARTIAL)


def test_staff_week_shows_day_pay_and_total(owner, week):
    html = owner.get(f"/settings/staff/?week={WEEK}").content.decode()
    assert "₹1,000" in html
    assert "+2h OT" in html
    assert "To pay" in html
    assert "₹1,800" in html
    assert "Record payout" in html


def test_record_payout_stores_snapshot(owner, week):
    response = pay(owner, week)
    assert response.status_code == 200
    assert "Paid " in response.content.decode()
    p = Payout.objects.get()
    assert (p.days, p.base_total, p.overtime_minutes) == (2, 1600, 120)
    assert (p.overtime_total, p.calculated_total, p.amount) == (200, 1800, 3400)
    assert (p.method, p.week_start) == ("upi", date(2026, 11, 9))


def test_payout_sheet_defaults(owner, week):
    html = owner.get(URL.format(week.pk, WEEK)).content.decode()
    assert "Pay Ali for 9–15 Nov" in html
    assert "Calculated so far: 2 days, 2h overtime = ₹1,800" in html
    assert 'value="1800"' in html
    assert 'value="2026-11-14"' in html


def test_editing_day_after_payout_keeps_payout(owner, week):
    pay(owner, week, amount="1800")
    owner.post(
        f"/settings/staff/{week.pk}/days/2026-11-10/",
        {"start": "09:00", "end": "21:00"},
        headers=PARTIAL,
    )
    p = Payout.objects.get()
    assert (p.calculated_total, p.overtime_minutes) == (1800, 120)
    html = owner.get(f"/settings/staff/?week={WEEK}").content.decode()
    assert "Paid Sat 14 Nov, UPI, ₹1,800" in html
    assert "Record payout" not in html
    assert "₹1,800" in html


def test_paid_week_hides_record_payout(owner, week):
    pay(owner, week)
    html = owner.get(f"/settings/staff/?week={WEEK}").content.decode()
    assert "Record payout" not in html
    assert "Past payouts" in html
    assert "For 9–15 Nov · 2 days, 2h overtime" in html


def test_payout_for_paid_week_404(owner, week):
    pay(owner, week)
    assert pay(owner, week).status_code == 404
    assert owner.get(URL.format(week.pk, WEEK)).status_code == 404
    assert Payout.objects.count() == 1


def test_payout_future_week_404(owner, week):
    assert owner.get(URL.format(week.pk, "2026-11-23")).status_code == 404


@pytest.mark.parametrize("bad", ["junk", "2026-11-10"])
def test_payout_bad_week_404(owner, week, bad):
    assert owner.get(URL.format(week.pk, bad)).status_code == 404


def test_payout_paid_on_future_rejected(owner, week):
    response = pay(owner, week, paid_on="2026-11-20")
    assert response.status_code == 422
    assert "Pick today or an earlier date." in response.content.decode()
    assert not Payout.objects.exists()


@pytest.mark.parametrize("amount", ["-1", "abc", "1.234", "99999999999"])
def test_payout_bad_amount_rejected(owner, week, amount):
    response = pay(owner, week, amount=amount)
    assert response.status_code == 422
    assert "Enter an amount of 0 or more." in response.content.decode()


def test_payout_requires_owner(week):
    response = week.client.get(URL.format(week.pk, WEEK))
    assert response.status_code == 302
    assert response["Location"] == "/my-work/"


def test_my_pay_shows_only_own_pay(week, today):
    today(12)
    other = make_employee("9000011118", wage=1234, name="Zed Other")
    for p, amount in ((week, 2900), (other, 7777)):
        Payout.objects.create(
            employee=p,
            week_start=date(2026, 11, 2),
            paid_on=date(2026, 11, 7),
            method="cash",
            amount=amount,
            days=6,
            daily_wage=p.daily_wage,
            base_total=0,
            overtime_minutes=0,
            overtime_multiplier=1,
            overtime_total=0,
            calculated_total=amount,
        )
    html = week.client.get("/my-pay/").content.decode()
    assert "₹2,900" in html
    assert "₹7,777" not in html
    assert "₹1,234" not in html


def test_my_pay_empty_payments_text(employee, today):
    today(12)
    html = employee.client.get("/my-pay/").content.decode()
    assert "No payments yet. Your first pay day is Sat 14 Nov." in html
    assert "Off, unpaid" in html


def test_my_pay_uses_snapshot_for_paid_week(owner, week, today):
    today(14)
    pay(owner, week, amount="1750")
    DayRecord.objects.filter(date=date(2026, 11, 10)).update(
        end=datetime(2026, 11, 10, 23, 0, tzinfo=IST)
    )
    html = week.client.get("/my-pay/").content.decode()
    assert "₹1,750" in html
    assert "Paid Sat 14 Nov, UPI." in html
    assert "2 days × ₹800" in html
    assert "Overtime 2h × ₹100" in html


def test_my_pay_day_states(week, today):
    today(14)
    record(week, 11, end=None)
    record(week, 12, end=None)
    html = week.client.get("/my-pay/").content.decode()
    assert "not ended, unpaid" in html
    assert "9:00 am – 7:00 pm · 10h · 2h overtime" in html


def test_paid_week_keeps_stored_hourly_rate(owner, week, today):
    today(14)
    pay(owner, week, amount="1800")
    Employee.objects.update(daily_wage=1600)
    mine = week.client.get("/my-pay/").content.decode()
    staff = owner.get(f"/settings/staff/?e={week.pk}&week={WEEK}").content.decode()
    for html in (mine, staff):
        assert "× ₹100" in html
        assert "× ₹200" not in html
