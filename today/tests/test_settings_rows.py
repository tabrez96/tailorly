import tomllib
from datetime import date
from decimal import Decimal

from today import settings_rows as rows


def test_sales_line():
    assert (
        rows.sales_line(Decimal("42600.00"), 3, date(2026, 11, 25))
        == "₹42,600 sold in November"
    )
    assert rows.sales_line(Decimal("0"), 0, date(2026, 11, 25)) == "No sales yet"


def test_production_line():
    assert rows.production_line(0) == "Nothing finished yet"
    assert rows.production_line(1) == "1 garment finished this week"
    assert rows.production_line(16) == "16 garments finished this week"


def test_payments_line():
    assert rows.payments_line(Decimal("0")) == "Nothing to collect"
    assert rows.payments_line(Decimal("-5")) == "Nothing to collect"
    assert rows.payments_line(Decimal("18400")) == "₹18,400 still to collect"


def test_staff_report_line():
    assert rows.staff_report_line("Ali Khan", 4, 120) == (
        "Ali: 4 days, 2h overtime this week"
    )
    assert rows.staff_report_line("Ali Khan", 1, 0) == (
        "Ali: 1 day, no overtime this week"
    )
    assert rows.staff_report_line(None, 0, 0) == "No employees yet"


def test_staff_line():
    saturday = date(2026, 11, 28)
    assert rows.staff_line([], saturday) == "Add your first employee"
    assert rows.staff_line(["Ali Khan"], saturday) == "Ali Khan · pay day Saturday"
    assert rows.staff_line(["Ali Khan", "Sana"], saturday) == (
        "Ali Khan and 1 more · pay day Saturday"
    )


def test_running_line():
    assert rows.running_line(Decimal("9500"), Decimal("46")) == (
        "₹9,500 a month · ₹46 an hour"
    )
    assert rows.running_line(Decimal("0"), None) == "Not set yet"


def test_phone_text():
    assert rows.phone_text("9845000000") == "98450 00000"
    assert rows.phone_text("owner") == "owner"


def test_app_version():
    with open("pyproject.toml", "rb") as f:
        version = tomllib.load(f)["project"]["version"]
    assert rows.app_version().startswith("Tailorly ")
    assert version in rows.app_version()
