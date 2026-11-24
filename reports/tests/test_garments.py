from datetime import date
from decimal import Decimal as D

from reports import costing, garments
from reports.sales import CUSTOM, LAST_MONTH, MONTH, Period

RATE = D(46)


def piece(
    price, *, minutes=0, materials=0, free=False, ready_made=False, name="Blouse"
):
    work = (costing.Work(minutes=minutes, daily_wage=D(800)),) if minutes else ()
    cost = costing.item_cost(
        costing.ItemInput(
            price=D(price),
            ready_made=ready_made,
            finished=True,
            estimate_minutes=None,
            work=work,
            assignee_wage=None,
            material_cost=D(materials),
            billed_selling=D(0),
        ),
        RATE,
    )
    return garments.Piece(name, free, cost)


def test_average_paid_pieces():
    # 120 min: staff 200, running 92. 60 min: staff 100, running 46.
    a = garments.average(
        "Blouse",
        [
            piece(1600, minutes=120, materials=100),
            piece(1700, minutes=60, materials=50),
        ],
    )
    assert a.count == 2
    assert a.price == D(1650)
    assert a.staff == D(150)
    assert a.materials == D(75)
    assert a.running == D(69)
    assert a.cost == D(294)
    # gains 1600-392 = 1208 and 1700-196 = 1504; average 1356
    assert a.gain == D(1356)
    assert a.gain_pct == 82  # 2712 / 3300


def test_free_piece_counts_cost_not_price():
    a = garments.average(
        "Blouse",
        [
            piece(1600, minutes=120, materials=100),
            piece(1600, minutes=120, materials=100, free=True),
        ],
    )
    assert a.price == D(800)
    assert a.cost == D(392)
    # paid gain 1208, free gain -392: average 408
    assert a.gain == D(408)
    assert a.gain_pct == 51  # 816 / 1600


def test_ready_made_has_no_staff_or_running():
    a = garments.average("Kurta", [piece(799, ready_made=True)])
    assert (a.staff, a.running, a.materials) == (0, 0, 0)
    assert a.gain == D(799)
    assert a.gain_pct == 100


def test_all_free_has_no_pct():
    a = garments.average("Blouse", [piece(1000, minutes=60, free=True)])
    assert a.price == 0
    assert a.gain == D(-146)
    assert a.gain_pct is None


def test_by_garment_groups_by_name_and_sorts():
    pieces = [
        piece(1, name="Kurta"),
        piece(1, name="Churidar"),
        piece(1, name="Blouse"),
        piece(1, name="Churidar"),
        piece(1, name="Blouse"),
    ]
    got = garments.by_garment(pieces)
    assert [(a.name, a.count) for a in got] == [
        ("Blouse", 2),
        ("Churidar", 2),
        ("Kurta", 1),
    ]


def test_rows_words_and_bar():
    [row] = garments.rows(
        [garments.average("Blouse", [piece(1000, minutes=60, materials=100)])]
    )
    assert row["words"] == (
        "Average price ₹1,000 · cost ₹246: staff ₹100, materials ₹100, running ₹46"
    )
    assert [s["key"] for s in row["bar"]] == [
        "staff",
        "materials",
        "running",
        "gain",
    ]
    assert row["gain"] == D(754)
    assert row["loss"] is False


def test_rate_card_set():
    card = garments.rate_card(D(9500), 208, D(46))
    assert card["title"] == "₹46 an hour of work"
    assert card["text"] == (
        "₹9,500 a month over 208 working hours (26 days × 8h). "
        "Added to each item by its time."
    )


def test_rate_card_hours_not_whole_days():
    card = garments.rate_card(D(9500), 205, D(46))
    assert card["text"].startswith("₹9,500 a month over 205 working hours. ")


def test_rate_card_not_set():
    assert garments.rate_card(D(0), 208, None) == {
        "set": False,
        "text": garments.NOT_SET_TEXT,
    }


def test_caption_month_and_custom():
    month = Period(MONTH, date(2026, 11, 1), date(2026, 11, 30))
    assert garments.caption(month) == (
        "Gain per piece, average of garments sold in November. "
        "Tap a garment for its orders."
    )
    last = Period(LAST_MONTH, date(2026, 10, 1), date(2026, 10, 31))
    assert "sold in October." in garments.caption(last)
    custom = Period(CUSTOM, date(2026, 11, 3), date(2026, 11, 9))
    assert "sold in 3–9 Nov." in garments.caption(custom)


def test_bills_average():
    assert garments.bills_average([D(9000), D(9600), D(9900)]) == D(9500)
    assert garments.bills_average([D(6000)]) == D(6000)
    assert garments.bills_average([]) is None
    assert garments.bills_average([D(0)]) is None


def test_last_three_months():
    assert garments.last_three_months(date(2026, 11, 24)) == (
        date(2026, 8, 1),
        date(2026, 10, 31),
    )
    assert garments.last_three_months(date(2027, 1, 15)) == (
        date(2026, 10, 1),
        date(2026, 12, 31),
    )


def test_prefill_lines():
    assert garments.prefill_lines(None) == []
    assert garments.prefill_lines(D(9500)) == [{"name": "Other", "amount": "9500"}]
