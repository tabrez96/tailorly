"""The MCP server: tools/list and tools/call go through the scope gate and the log."""

from typing import Any
from urllib.parse import urlsplit

from asgiref.sync import sync_to_async
from django.conf import settings
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.context import Context
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings

from reports.models import ShopSettings

from . import change_tools, dispatch, report_tools, scopes, tools
from .gate import KeyGate


def _visible() -> list[str]:
    return scopes.visible(scopes.Access.of(ShopSettings.current()))


class TailorlyMCP(MCPServer):
    async def list_tools(self):
        listed = await super().list_tools()
        allowed = set(await sync_to_async(_visible)())
        return [t for t in listed if t.name in allowed]

    @staticmethod
    def _key_id(context: Context | None) -> int:
        return context.request_context.request.state.mcp_key_id

    async def call_tool(
        self, name: str, arguments: dict[str, Any], context: Context | None = None
    ):
        key_id = self._key_id(context)
        token = dispatch.touched_order.set(None)
        try:
            try:
                await sync_to_async(dispatch.authorize)(name)
            except dispatch.Refused as e:
                await sync_to_async(dispatch.record)(
                    key_id, name, "refused", _order_number(name, arguments)
                )
                raise ToolError(str(e)) from None
            try:
                result = await super().call_tool(name, arguments, context)
            except Exception:
                await sync_to_async(dispatch.record)(
                    key_id, name, "failed", _order_number(name, arguments)
                )
                raise
            await sync_to_async(dispatch.record)(
                key_id, name, "", _order_number(name, arguments)
            )
            return result
        finally:
            dispatch.touched_order.reset(token)


def _order_number(name: str, arguments: dict[str, Any]) -> int | None:
    """The order a change call touched: set by the tool, else the one it was given."""
    tool = scopes.TOOLS.get(name)
    if tool is None or tool.kind != scopes.CHANGE:
        return None
    return dispatch.touched_order.get() or arguments.get("number")


async def _changed(fn, *args) -> dict:
    out = await sync_to_async(fn)(*args)
    dispatch.touched_order.set(out["number"])
    return out


def build_server() -> TailorlyMCP:
    server = TailorlyMCP("Tailorly")

    @server.tool()
    async def find_customers(query: str, limit: int = 10) -> list[dict]:
        """Customers whose name or phone number matches, with their open order count."""
        return await sync_to_async(tools.find_customers)(query, limit)

    @server.tool()
    async def get_order(number: int) -> dict:
        """One order by its number: customer, status, due date and items."""
        return await sync_to_async(tools.get_order)(number)

    @server.tool()
    async def list_orders(
        status: str | None = None, due_by: str | None = None, limit: int = 50
    ) -> list[dict]:
        """Orders, soonest due first. Filter by status or by due_by (YYYY-MM-DD)."""
        return await sync_to_async(tools.list_orders)(status, due_by, limit)

    @server.tool()
    async def get_measurements(customer_id: int) -> dict:
        """A customer's saved measurements for each garment."""
        return await sync_to_async(tools.get_measurements)(customer_id)

    @server.tool()
    async def money_to_collect() -> dict:
        """Money customers still owe: totals, and the orders owing."""
        return await sync_to_async(report_tools.money_to_collect)()

    @server.tool()
    async def list_payments(start: str, end: str) -> dict:
        """Payments received from start to end (YYYY-MM-DD, max 366 days)."""
        return await sync_to_async(report_tools.list_payments)(start, end)

    @server.tool()
    async def order_cost_and_gain(number: int) -> dict:
        """What an order costs and gains, per item, as on its cost card."""
        return await sync_to_async(report_tools.order_cost_and_gain)(number)

    @server.tool()
    async def staff_week(week: str | None = None) -> dict:
        """Each employee's days, overtime, pay and payout for a week (YYYY-MM-DD)."""
        return await sync_to_async(report_tools.staff_week)(week)

    @server.tool()
    async def create_order(
        customer_id: int, products: list[str], due_date: str
    ) -> dict:
        """Place an order for an existing customer.

        products: names as in the catalogue. due_date: YYYY-MM-DD.
        """
        return await _changed(
            change_tools.create_order, customer_id, products, due_date
        )

    @server.tool()
    async def record_payment(
        number: int, amount: str, method: str = "cash", date: str | None = None
    ) -> dict:
        """Record a payment on an order; returns the new balance.

        method: cash, upi, card or bank. date: YYYY-MM-DD, default today.
        """
        return await _changed(change_tools.record_payment, number, amount, method, date)

    @server.tool()
    async def update_item_measurements(
        number: int, item_id: int, values: dict[str, str]
    ) -> dict:
        """Change one custom item's measurements on an order, in inches.

        values: {"Chest": "38.5"}; "" clears one.
        """
        return await _changed(
            change_tools.update_item_measurements, number, item_id, values
        )

    return server


def _allowed_hosts() -> list[str]:
    hosts = ["127.0.0.1:*", "localhost:*"]
    if settings.MCP_SERVER_URL:  # the tunnel sends the public host
        hosts.append(urlsplit(settings.MCP_SERVER_URL).netloc)
    return hosts


def build_app(server: TailorlyMCP | None = None):
    server = server or build_server()
    return KeyGate(
        server.streamable_http_app(
            stateless_http=True,
            json_response=True,
            transport_security=TransportSecuritySettings(
                enable_dns_rebinding_protection=True, allowed_hosts=_allowed_hosts()
            ),
        )
    )
