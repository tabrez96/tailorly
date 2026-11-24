from decimal import Decimal as D

from reports import costing
from reports.costing import ItemInput, Work, item_cost, order_cost


def item(**kw) -> ItemInput:
    base = dict(
        price=D("1500"),
        ready_made=False,
        finished=True,
        estimate_minutes=None,
        work=(),
        assignee_wage=None,
        material_cost=D(0),
        billed_selling=D(0),
    )
    return ItemInput(**{**base, **kw})


def test_running_rate_rounds_to_rupee():
    assert costing.running_rate(D("9500"), 208) == D(46)
    assert costing.running_rate(D(0), 208) is None
    assert costing.running_rate(D("9500"), 0) is None


def test_monthly_total():
    lines = [{"name": "Rent", "amount": "7000"}, {"name": "X", "amount": "1800.50"}]
    assert costing.monthly_total(lines) == D("8800.50")
    assert costing.monthly_total([]) == 0


def test_finished_item_uses_logged_minutes_per_employee():
    c = item_cost(item(work=(Work(120, D(800)), Work(60, D(400)))), D(46))
    assert c.minutes == 180
    assert c.staff == D(250)
    assert c.running == D(138)
    assert c.estimated is False
    assert c.rates == {D(100), D(50)}


def test_unfinished_item_uses_estimate_at_assignee_rate():
    c = item_cost(
        item(
            finished=False,
            estimate_minutes=180,
            work=(Work(60, D(800)),),
            assignee_wage=D(800),
        ),
        D(46),
    )
    assert c.minutes == 180
    assert c.staff == D(300)
    assert c.estimated is True


def test_unfinished_item_logged_beyond_estimate():
    c = item_cost(
        item(
            finished=False,
            estimate_minutes=180,
            work=(Work(200, D(800)),),
            assignee_wage=D(800),
        ),
        None,
    )
    assert c.minutes == 200
    assert c.staff == rupees_of("333.33")


def rupees_of(value: str) -> D:
    return costing.rupees(D(value))


def test_unfinished_without_estimate_is_still_estimated():
    c = item_cost(item(finished=False, work=(Work(60, D(800)),)), D(46))
    assert (c.minutes, c.staff, c.estimated) == (60, D(100), True)


def test_no_assignee_extra_minutes_cost_running_only():
    c = item_cost(item(finished=False, estimate_minutes=120), D(46))
    assert c.minutes == 120
    assert c.staff == 0
    assert c.running == D(92)
    assert c.rates == frozenset()


def test_ready_made_costs_materials_only():
    c = item_cost(
        item(
            price=D(799),
            ready_made=True,
            finished=False,
            estimate_minutes=60,
            work=(Work(60, D(800)),),
            material_cost=D(450),
        ),
        D(46),
    )
    assert (c.cost, c.gain, c.gain_pct, c.estimated, c.minutes) == (
        D(450),
        D(349),
        44,
        False,
        0,
    )


def test_gain_includes_billed_material_selling():
    c = item_cost(
        item(
            price=D(1800),
            billed_selling=D(270),
            material_cost=D(1000),
        ),
        None,
    )
    assert c.sale == D(2070)
    assert c.gain == D(1070)
    assert c.gain_pct == 59


def test_free_order_cost_to_shop():
    c = item_cost(
        item(work=(Work(180, D(800)),), material_cost=D(120)),
        D(46),
    )
    oc = order_cost([c])
    assert (oc.staff, oc.materials, oc.running, oc.cost) == (
        D(300),
        D(120),
        D(138),
        D(558),
    )
    assert oc.sale == D(1500)


def test_order_totals_are_sums_of_items():
    a = item_cost(item(price=D(1000), material_cost=D("99.5")), None)
    b = item_cost(item(price=D(500), material_cost=D("99.5")), None)
    oc = order_cost([a, b])
    assert oc.materials == a.materials + b.materials == D(200)
    assert oc.gain == a.gain + b.gain
    assert oc.gain_pct == 87
    assert oc.minutes == 0


def test_order_estimated_if_any_item_estimated():
    done = item_cost(item(), None)
    open_ = item_cost(item(finished=False), None)
    assert order_cost([done]).estimated is False
    assert order_cost([done, open_]).estimated is True
    assert order_cost([]).gain == 0


def test_cost_missing_carries_to_order():
    c = item_cost(item(cost_missing=True), None)
    assert order_cost([c]).cost_missing is True


def test_rate_missing_counts_running_as_zero():
    c = item_cost(item(work=(Work(180, D(800)),)), None)
    assert c.running == 0


def test_bar_and_words():
    c = item_cost(
        item(price=D(1500), work=(Work(180, D(800)),), material_cost=D(120)), D(46)
    )
    segs = costing.bar(c)
    assert [s["key"] for s in segs] == ["staff", "materials", "running", "gain"]
    assert abs(sum(s["pct"] for s in segs) - 100) < 0.5
    assert costing.split_words(c) == (
        "Staff ₹300 · Materials ₹120 · Running costs ₹138 · Gain ₹942"
    )


def test_bar_negative_gain_has_no_gain_segment():
    c = item_cost(item(price=D(100), material_cost=D(140)), None)
    assert c.gain == D(-40)
    assert costing.bar(c)[-1]["pct"] == 0
    assert costing.split_words(c).endswith("Gain -₹40")


def test_bar_all_zero():
    c = item_cost(item(price=D(0)), None)
    assert all(s["pct"] == 0 for s in costing.bar(c))


def test_price_zero_pct_none():
    assert item_cost(item(price=D(0), material_cost=D(10)), None).gain_pct is None
    assert costing.pct(D(5), D(0)) is None


def rework(**kw) -> costing.ReworkInput:
    base = dict(
        finished=True,
        estimate_minutes=45,
        work=(),
        assignee_wage=None,
        material_cost=D(0),
    )
    return costing.ReworkInput(**{**base, **kw})


def test_rework_cost_finished_uses_logged():
    c = costing.rework_cost(
        rework(work=(Work(40, D(800)),), material_cost=D("33.4"), assignee_wage=D(800))
    )
    assert (c.logged, c.minutes, c.staff, c.materials) == (40, 40, D(67), D(33))
    assert c.cost == D(100)
    assert c.estimated is False


def test_rework_cost_open_uses_estimate_when_more():
    c = costing.rework_cost(
        rework(
            finished=False,
            work=(Work(25, D(400)),),
            assignee_wage=D(800),
        )
    )
    assert (c.logged, c.minutes) == (25, 45)
    # 25 min at 50/h + 20 min at 100/h
    assert c.staff == D(54)
    assert c.estimated is True


def test_rework_cost_open_uses_logged_when_more():
    c = costing.rework_cost(
        rework(finished=False, work=(Work(60, D(800)),), assignee_wage=D(800))
    )
    assert (c.logged, c.minutes, c.staff) == (60, 60, D(100))


def test_rework_cost_open_without_sessions_or_assignee():
    c = costing.rework_cost(rework(finished=False))
    assert (c.minutes, c.staff, c.cost) == (45, D(0), D(0))


def test_rework_cost_has_no_running_share():
    assert "rate" not in costing.rework_cost.__code__.co_varnames[:1]
    c = costing.rework_cost(rework(work=(Work(60, D(800)),), material_cost=D(20)))
    assert c.cost == c.staff + c.materials == D(120)


def test_rework_total_and_gain_after():
    a = costing.rework_cost(rework(work=(Work(40, D(800)),), material_cost=D(33)))
    b = costing.rework_cost(
        rework(finished=False, assignee_wage=D(800), cost_missing=True)
    )
    t = costing.rework_total([a, b])
    assert (t.count, t.logged, t.minutes) == (2, 40, 85)
    assert t.cost == a.cost + b.cost
    assert t.estimated and t.cost_missing
    gain, percent = costing.gain_after(D(900), D(2400), t)
    assert gain == 900 - t.cost
    assert percent == costing.pct(gain, D(2400))


def test_item_cost_unchanged_by_refactor_open_item():
    c = item_cost(
        item(
            finished=False,
            estimate_minutes=60,
            work=(Work(30, D(800)),),
            assignee_wage=D(400),
        ),
        None,
    )
    assert (c.minutes, c.staff, c.rates) == (60, D(75), {D(100), D(50)})
