from assistants import scopes
from assistants.scopes import CHANGE, READ, TOOLS, Access, refusal, visible
from reports.models import ShopSettings

ALL = frozenset(scopes.LABELS)


def test_every_tool_has_known_scopes_and_kind():
    assert len(TOOLS) == 11
    for tool in TOOLS.values():
        assert set(tool.scopes) <= set(scopes.LABELS)
        assert tool.kind in (READ, CHANGE)


def test_refusal_names_the_switch_that_is_off():
    access = Access(ALL - {"measurements"}, False)
    assert "Measurements and photos" in refusal("get_measurements", access)


def test_change_tool_refused_under_only_read():
    for name in ("create_order", "record_payment", "update_item_measurements"):
        assert "only read" in refusal(name, Access(ALL, False))
        assert refusal(name, Access(ALL, True)) is None


def test_unknown_tool_refused():
    assert refusal("drop_tables", Access(ALL, True)) == "Unknown tool: drop_tables."


def test_visible_defaults():
    assert visible(Access.of(ShopSettings())) == [
        "find_customers",
        "get_order",
        "list_orders",
        "get_measurements",
        "money_to_collect",
        "list_payments",
        "order_cost_and_gain",
    ]
