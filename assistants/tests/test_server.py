import httpx2 as httpx
import pytest
from asgiref.sync import async_to_sync
from django.urls import reverse
from mcp.server.mcpserver.exceptions import ToolError

from assistants import keys
from assistants.models import AccessKey, AssistantActivity
from assistants.server import TailorlyMCP, build_app, build_server
from catalog.models import Product
from customers.models import Customer
from orders.models import Order, OrderItem
from reports.models import ShopSettings

DEFAULT = [
    "find_customers",
    "get_order",
    "list_orders",
    "get_measurements",
    "money_to_collect",
    "list_payments",
    "order_cost_and_gain",
]


def switches(**kw):
    ShopSettings.objects.update_or_create(pk=1, defaults={"mcp_on": True, **kw})


@pytest.fixture
def key(db, monkeypatch):
    raw, prefix, key_hash = keys.generate()
    k = AccessKey.objects.create(name="Claude", prefix=prefix, key_hash=key_hash)
    k.raw = raw
    monkeypatch.setattr(TailorlyMCP, "_key_id", staticmethod(lambda context: k.pk))
    return k


@pytest.fixture
def order(db):
    customer = Customer.objects.create(name="Asha Rao", phone="9000000011")
    placed = Order.objects.create(customer=customer, number=1, status="open")
    OrderItem.from_product(
        placed,
        Product.objects.create(
            name="Scarf", kind="primary", type="ready_made", usual_price=300
        ),
    )
    return placed


def names(tools):
    return [t.name for t in tools]


def test_list_tools_hides_tools_whose_scope_is_off(key):
    server = build_server()
    assert names(async_to_sync(server.list_tools)()) == DEFAULT
    switches(mcp_measurements=False)
    assert names(async_to_sync(server.list_tools)()) == [
        n for n in DEFAULT if n != "get_measurements"
    ]


def test_call_refused_tool_raises_and_logs(key):
    switches(mcp_orders=False)
    with pytest.raises(ToolError, match="Orders and customers"):
        async_to_sync(build_server().call_tool)("get_order", {"number": 1})
    (row,) = AssistantActivity.objects.all()
    assert (row.what, row.key) == ("get_order · refused", key)


def test_call_tool_logs_activity(key, order):
    switches()
    async_to_sync(build_server().call_tool)("get_order", {"number": 1})
    (row,) = AssistantActivity.objects.all()
    assert (row.what, row.kind, row.key) == ("get_order", "read", key)


def test_failed_call_logs_failed(key):
    switches()
    with pytest.raises(ToolError, match="No order #5"):
        async_to_sync(build_server().call_tool)("get_order", {"number": 5})
    assert AssistantActivity.objects.get().what == "get_order · failed"


def test_change_tool_refused_under_only_read(key):
    switches()
    with pytest.raises(ToolError, match="only read"):
        async_to_sync(build_server().call_tool)("create_order", {})
    assert AssistantActivity.objects.get().what == "create_order · refused"


def test_http_tools_list_end_to_end(key):
    switches()
    server = build_server()
    app = build_app(server)
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }

    async def post_both():
        async with server.session_manager.run():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://127.0.0.1:8001",
            ) as client:
                auth = {"Authorization": f"Bearer {key.raw}"}
                ok = await client.post("/mcp", json=body, headers={**headers, **auth})
                return ok, await client.post("/mcp", json=body, headers=headers)

    ok, anonymous = async_to_sync(post_both)()
    assert ok.status_code == 200, ok.text
    assert names_of(ok.json()) == DEFAULT
    assert anonymous.status_code == 401


def names_of(payload):
    return [t["name"] for t in payload["result"]["tools"]]


def test_staff_week_listed_only_with_staff_on(key):
    server = build_server()
    switches()
    assert "staff_week" not in names(async_to_sync(server.list_tools)())
    with pytest.raises(ToolError, match="Staff and pay"):
        async_to_sync(server.call_tool)("staff_week", {})
    assert AssistantActivity.objects.get().what == "staff_week · refused"
    switches(mcp_staff=True)
    assert "staff_week" in names(async_to_sync(server.list_tools)())
    async_to_sync(server.call_tool)("staff_week", {})


def test_money_tools_hidden_and_refused_with_money_off(key):
    switches(mcp_money=False)
    server = build_server()
    money = ["money_to_collect", "list_payments", "order_cost_and_gain"]
    assert not set(money) & set(names(async_to_sync(server.list_tools)()))
    args = {"list_payments": {"start": "2026-11-01", "end": "2026-11-02"}}
    for name in money:
        with pytest.raises(ToolError, match="Invoices and payments"):
            async_to_sync(server.call_tool)(name, args.get(name, {"number": 1}))


def test_each_new_tool_logs_activity_shown_in_s21(key, order, owner):
    switches(mcp_staff=True)
    server = build_server()
    calls = {
        "money_to_collect": {},
        "list_payments": {"start": "2026-11-24", "end": "2026-11-24"},
        "order_cost_and_gain": {"number": 1},
        "staff_week": {},
    }
    for name, args in calls.items():
        async_to_sync(server.call_tool)(name, args)
    rows = AssistantActivity.objects.order_by("pk")
    assert [(r.what, r.kind) for r in rows] == [(n, "read") for n in calls]
    html = owner.get(reverse("assistants")).content.decode()
    assert all(name in html for name in calls)
