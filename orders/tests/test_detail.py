from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone

from orders.detail import (
    assigned_line,
    item_meta,
    item_overline,
    measurement_summary,
    option_rows,
    photo_badge,
    queue_rank,
    status_steps,
)
from orders.forms import PaymentForm


def states(status):
    return [s["state"] for s in status_steps(status)]


def test_status_steps_in_progress():
    assert states("in_progress") == ["done", "current", "todo", "todo"]


def test_status_steps_delivered():
    assert states("delivered") == ["done", "done", "done", "current"]
    assert [s["label"] for s in status_steps("open")][0] == "Open"


def test_assigned_line_with_place():
    assert assigned_line("Ali Khan", 2) == "Ali Khan · 2nd in Ali's queue"


def test_assigned_line_without_place():
    assert assigned_line("Ali Khan", None) == "Ali Khan"


def test_measurement_summary():
    names = [
        "Bust",
        "Waist",
        "Shoulder",
        "Armhole",
        "Sleeve",
        "Neck",
        "Hip",
        "Rise",
        "Seat",
    ]
    tiles = [
        {"label": n, "value": str(v)}
        for n, v in zip(names, [36, 30, 14.5, 1, 2, 3, 4, 5, 6], strict=True)
    ]
    assert measurement_summary(tiles) == "Bust 36 · Waist 30 · Shoulder 14.5 · +6"
    tiles[1]["value"] = "—"
    assert measurement_summary(tiles).endswith("+5")
    assert measurement_summary(tiles[:3]) == "Bust 36 · Shoulder 14.5"
    assert measurement_summary([{"label": "Bust", "value": "—"}]) == ""


def form(amount="500", date=None, method="cash"):
    date = date or timezone.localdate()
    return PaymentForm({"amount": amount, "date": date.isoformat(), "method": method})


def test_payment_form_rejects_zero_and_negative():
    for amount in ("0", "-5", "abc", "1.234"):
        f = form(amount)
        assert not f.is_valid()
        assert f.errors["amount"] == ["Enter an amount above zero."]


def test_payment_form_rejects_future_date():
    f = form(date=timezone.localdate() + timedelta(days=1))
    assert f.errors["date"] == ["Pick today or an earlier date."]


def test_payment_form_accepts_commas():
    f = form("1,200")
    assert f.is_valid()
    assert f.cleaned_data["amount"] == Decimal("1200")


def test_queue_rank_breaks_ties_by_pk():
    day = date(2026, 12, 1)
    assert queue_rank([(2, day)], 1, day) == 1
    assert queue_rank([(1, day)], 2, day) == 2


def test_queue_rank_by_due_date_and_undated_last():
    d1, d2 = date(2026, 12, 1), date(2026, 12, 5)
    assert queue_rank([(1, d2), (2, None)], 3, d1) == 1
    assert queue_rank([(1, d1), (2, d2)], 3, None) == 3
    assert queue_rank([(1, None)], 2, None) == 2


def test_item_overline():
    assert (
        item_overline(1042, "Meera Iyer", 1, 2) == "ORD-1042 · MEERA IYER · ITEM 1 OF 2"
    )


def test_item_meta_full():
    assert (
        item_meta("Ali", 160, 180, date(2026, 11, 13))
        == "Ali · 2h 40m of 3h est. · due Fri 13 Nov"
    )


def test_item_meta_no_estimate_nothing_logged():
    assert item_meta("Ali", 0, None, date(2026, 11, 13)) == "Ali · due Fri 13 Nov"


def test_item_meta_logged_without_estimate():
    assert item_meta("", 90, None, None) == "1h 30m"


def test_item_meta_empty():
    assert item_meta("", 0, None, None) == ""


def test_option_rows_marks_when_done():
    answers = [
        {"name": "Lining", "answer": "Yes"},
        {"name": "Padding", "answer": "No"},
    ]
    assert option_rows(answers, {"Lining"}) == [
        {"name": "Lining", "answer": "Yes", "when_done": True},
        {"name": "Padding", "answer": "No", "when_done": False},
    ]


def test_photo_badge():
    assert [photo_badge(n) for n in (0, 1, 3)] == ["", "", "1/3"]
