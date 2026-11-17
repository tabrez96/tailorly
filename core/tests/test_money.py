from decimal import Decimal

import pytest

from core.money import format_inr


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (142600, "₹1,42,600"),
        (1234567.4, "₹12,34,567"),
        (999, "₹999"),
        (1000, "₹1,000"),
        (100000, "₹1,00,000"),
        (10000000, "₹1,00,00,000"),
        (Decimal("0.5"), "₹1"),
        (2.5, "₹3"),
        (-142, "-₹142"),
        (-0.4, "₹0"),
        (0, "₹0"),
        ("1800", "₹1,800"),
    ],
)
def test_inr_examples(amount, expected):
    assert format_inr(amount) == expected


@pytest.mark.parametrize("blank", [None, ""])
def test_inr_none_is_blank(blank):
    assert format_inr(blank) == ""
