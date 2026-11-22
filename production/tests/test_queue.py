from datetime import date

from production.queue import (
    clear_moves,
    due_soon,
    due_text,
    fit_text,
    late_keys,
    ordered,
    reason,
    suggested,
    time_text,
)

TODAY = date(2026, 11, 22)


def row(pk, due=None, need=60, started=False, moved_to=None, kind="item"):
    return {
        "key": (kind, pk),
        "due": due,
        "need": need,
        "started": started,
        "moved_to": moved_to,
    }


def keys(rows):
    return [r["key"][1] for r in rows]


def d(day):
    return date(2026, 11, day)


def test_started_first():
    rows = [row(1, d(23)), row(2, d(28), started=True)]
    assert keys(suggested(rows)) == [2, 1]


def test_then_due_date_none_last():
    rows = [row(1), row(2, d(28)), row(3, d(24))]
    assert keys(suggested(rows)) == [3, 2, 1]


def test_same_due_shorter_estimate_first_even_with_less_time_left():
    long_nearly_done = {**row(1, d(24), need=10, started=True), "estimate": 120}
    short_barely_begun = {**row(2, d(24), need=25, started=True), "estimate": 30}
    assert keys(suggested([long_nearly_done, short_barely_begun])) == [2, 1]


def test_same_due_shorter_first():
    rows = [row(1, d(24), need=90), row(2, d(24), need=30)]
    assert keys(suggested(rows)) == [2, 1]


def test_items_before_reworks_on_a_tie():
    rows = [row(1, d(24), kind="rework"), row(2, d(24))]
    assert [r["key"][0] for r in suggested(rows)] == ["item", "rework"]


def five():
    return [row(i, d(23 + i)) for i in range(1, 6)]


def test_moved_item_keeps_place():
    rows = five()
    rows[4]["moved_to"] = 1
    assert keys(ordered(rows)) == [5, 1, 2, 3, 4]
    rows.append(row(9, d(22)))
    assert keys(ordered(rows)) == [5, 9, 1, 2, 3, 4]


def test_moved_rank_beyond_length_goes_last():
    rows = five()
    rows[0]["moved_to"] = 40
    assert keys(ordered(rows)) == [2, 3, 4, 5, 1]


def test_two_moves_same_rank():
    rows = five()
    rows[3]["moved_to"] = 2
    rows[1]["moved_to"] = 2
    assert keys(ordered(rows)) == [1, 2, 4, 3, 5]


def test_clear_moves_restores_suggested():
    rows = five()
    rows[4]["moved_to"] = 1
    rows[2]["moved_to"] = 4
    assert keys(ordered(clear_moves(rows))) == keys(suggested(rows))
    assert keys(ordered(rows)) != keys(suggested(rows))


def test_ordered_empty():
    assert ordered([]) == []


def test_late_risk_flagged():
    rows = [row(1, d(22), 480), row(2, d(23), 480), row(3, d(23), 480)]
    assert late_keys(rows, TODAY) == {("item", 3)}
    rows[2]["due"] = d(24)
    assert late_keys(rows, TODAY) == set()


def test_late_risk_uses_best_order():
    rows = [row(1, d(23), 60), row(2, d(30), 960, started=True)]
    assert late_keys(rows, TODAY) == set()


def test_late_risk_only_the_job_that_cannot_fit():
    rows = [row(1, d(22), 960), row(2, d(23), 60)]
    assert late_keys(rows, TODAY) == {("item", 1)}


def test_late_risk_past_due_and_undated():
    rows = [row(1, d(20), 30), row(2, None, 5000)]
    assert late_keys(rows, TODAY) == {("item", 1)}


def test_due_text_and_soon():
    assert due_text(None, TODAY) == "No due date"
    assert due_text(TODAY, TODAY) == "Due today"
    assert due_text(d(23), TODAY) == "Due tomorrow"
    assert due_text(d(27), TODAY) == "Due Fri 27 Nov"
    assert due_soon(d(24), TODAY)
    assert not due_soon(d(25), TODAY)
    assert due_soon(d(20), TODAY)
    assert not due_soon(None, TODAY)


def test_time_and_reason_text():
    assert time_text(row(1, need=90)) == "about 1h 30m"
    assert time_text(row(1, need=45, started=True)) == "about 45m left"
    assert reason(row(1, d(23), 60), TODAY) == "Due tomorrow and needs about 1h."
    assert reason(row(1, None, 60), TODAY) == (
        "No due date yet, and it needs about 1h."
    )


def test_fit_text():
    assert fit_text(1, 0) == "It fits before its due date."
    assert fit_text(6, 0) == "All 6 items fit before their due dates."
    assert fit_text(3, 1).startswith("1 item won't make its due date.")
    assert fit_text(3, 2).startswith("2 items won't make their due dates.")
