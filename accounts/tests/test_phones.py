import pytest

from accounts.phones import is_valid_phone, normalize_phone


@pytest.mark.parametrize(
    "raw", ["98450 12345", "+91 98450-12345", "098450 12345", "919845012345"]
)
def test_normalize_phone(raw):
    assert normalize_phone(raw) == "9845012345"


def test_normalize_keeps_odd_lengths_for_callers_to_reject():
    assert normalize_phone("abc") == ""
    assert normalize_phone("12345") == "12345"


@pytest.mark.parametrize("digits", ["984501234", "98450123456", "", "98450x2345"])
def test_invalid_phone(digits):
    assert not is_valid_phone(digits)


def test_valid_phone():
    assert is_valid_phone("9845012345")
