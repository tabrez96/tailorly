from datetime import date
from decimal import Decimal

import pytest

from assistants import tools
from assistants.tools import ToolFailure
from catalog.models import Product
from customers.models import Customer, MeasurementSet
from orders.models import Order, OrderItem
from reports.models import ShopSettings
from staff.models import Employee

MONEY = {"paid_by", "total", "received", "balance"}


def product(name, type_="custom", **kw):
    return Product.objects.create(
        name=name,
        kind="primary",
        type=type_,
        usual_price=1000,
        measurement_fields=["Bust"] if type_ == "custom" else [],
        **kw,
    )


@pytest.fixture
def shop(db):
    customer = Customer.objects.create(name="Asha Rao", phone="9000000011")
    blouse = product("Blouse")
    scarf = product("Scarf", "ready_made")
    order = Order.objects.create(
        customer=customer,
        number=7,
        status="open",
        due_date=date(2026, 12, 1),
        assignee=Employee.objects.create(name="Ali", phone="9000011117"),
    )
    OrderItem.from_product(order, blouse, price=Decimal("1500"))
    OrderItem.from_product(order, scarf, price=Decimal("300"))
    order.payments.create(amount=Decimal("500"), date=date(2026, 11, 1), method="cash")
    return order


def switches(**kw):
    ShopSettings.objects.update_or_create(pk=1, defaults=kw)


def test_find_customers_by_name_and_phone(shop):
    Customer.objects.create(name="Bina", phone="9111111111")
    (found,) = tools.find_customers("asha")
    assert found == {
        "id": shop.customer_id,
        "name": "Asha Rao",
        "phone": "9000000011",
        "open_orders": 1,
    }
    assert [c["name"] for c in tools.find_customers("91111 11111")] == ["Bina"]
    assert len(tools.find_customers("a", limit=0)) == 1  # clamped to 1


def test_find_customers_blank_query_fails(db):
    with pytest.raises(ToolFailure):
        tools.find_customers("  ")


def test_get_order_has_money_and_measurements_when_on(shop):
    out = tools.get_order(7)
    assert out["total"] == "1800.00"
    assert out["received"] == "500.00"
    assert out["balance"] == "1300.00"
    assert out["paid_by"] == "customer"
    assert out["assignee"] == "Ali"
    assert out["customer"]["phone"] == "9000000011"
    blouse, scarf = out["items"]
    assert blouse["price"] == "1500.00"
    assert blouse["measurements"] == [{"name": "Bust", "value": ""}]
    assert "measurements" not in scarf  # ready-made never has them
    assert "usual_price" not in blouse


def test_get_order_without_money_has_no_money_fields(shop):
    switches(mcp_money=False)
    out = tools.get_order(7)
    assert not MONEY & set(out)
    assert all("price" not in i for i in out["items"])


def test_get_order_without_measurements_has_no_measurements(shop):
    switches(mcp_measurements=False)
    assert all("measurements" not in i for i in tools.get_order(7)["items"])


def test_list_orders_without_money_has_no_money_fields(shop):
    assert MONEY <= set(tools.list_orders()[0])
    switches(mcp_money=False)
    (out,) = tools.list_orders()
    assert not MONEY & set(out)
    assert out["item_count"] == 2


def test_list_orders_filters_status_and_due_and_skips_drafts(shop):
    Order.objects.create(customer=shop.customer, status="draft")
    late = Order.objects.create(customer=shop.customer, number=8, status="ready")
    assert [o["number"] for o in tools.list_orders()] == [7, 8]  # no due date last
    assert [o["number"] for o in tools.list_orders(status="ready")] == [late.number]
    assert [o["number"] for o in tools.list_orders(due_by="2026-12-01")] == [7]
    assert tools.list_orders(due_by="2026-11-30") == []
    assert len(tools.list_orders(limit=1)) == 1


def test_list_orders_bad_status_fails(shop):
    with pytest.raises(ToolFailure):
        tools.list_orders(status="draft")
    with pytest.raises(ToolFailure):
        tools.list_orders(due_by="soon")


def test_get_order_unknown_number_fails(shop):
    draft = Order.objects.create(customer=shop.customer, status="draft")
    with pytest.raises(ToolFailure, match="No order #99"):
        tools.get_order(99)
    assert draft.number is None


def test_free_order_shows_free_without_amounts(shop):
    shop.paid_by = Order.FREE
    shop.save()
    out = tools.get_order(7)
    assert out["paid_by"] == "free"
    assert not {"total", "received", "balance"} & set(out)


def test_get_measurements_returns_sets(shop):
    blouse = Product.objects.get(name="Blouse")
    MeasurementSet.objects.create(
        customer=shop.customer, product=blouse, values=[{"name": "Bust", "value": "34"}]
    )
    out = tools.get_measurements(shop.customer_id)
    assert out["customer"] == {"id": shop.customer_id, "name": "Asha Rao"}
    assert out["garments"][0]["garment"] == "Blouse"
    assert out["garments"][0]["values"] == [{"name": "Bust", "value": "34"}]
    with pytest.raises(ToolFailure):
        tools.get_measurements(0)
