"""The one table of what every MCP tool needs, and the gate built on it."""

from dataclasses import dataclass

READ, CHANGE = "read", "change"  # same values as AssistantActivity.READ/CHANGE

LABELS = {
    "orders": "Orders and customers",
    "measurements": "Measurements and photos",
    "money": "Invoices and payments",
    "staff": "Staff and pay",
}
FIELDS = {
    "orders": "mcp_orders",
    "measurements": "mcp_measurements",
    "money": "mcp_money",
    "staff": "mcp_staff",
}


@dataclass(frozen=True)
class Tool:
    scopes: tuple[str, ...]
    kind: str  # READ or CHANGE


# Every tool of the server, including those built later. Order = tools/list order.
TOOLS = {
    "find_customers": Tool(("orders",), READ),
    "get_order": Tool(("orders",), READ),
    "list_orders": Tool(("orders",), READ),
    "get_measurements": Tool(("orders", "measurements"), READ),
    "money_to_collect": Tool(("money",), READ),
    "list_payments": Tool(("money",), READ),
    "order_cost_and_gain": Tool(("orders", "money"), READ),
    "staff_week": Tool(("staff",), READ),
    # Never delete, never record a payout
    "create_order": Tool(("orders",), CHANGE),
    "record_payment": Tool(("orders", "money"), CHANGE),
    "update_measurements": Tool(("orders", "measurements"), CHANGE),
}


@dataclass(frozen=True)
class Access:
    scopes: frozenset[str]
    can_change: bool

    @classmethod
    def of(cls, s) -> Access:
        """Snapshot of the switches; s is a ShopSettings."""
        return cls(
            frozenset(k for k, f in FIELDS.items() if getattr(s, f)),
            s.mcp_can_change,
        )


def refusal(name: str, access: Access) -> str | None:
    """Why a call is refused, or None when it may run."""
    tool = TOOLS.get(name)
    if tool is None:
        return f"Unknown tool: {name}."
    off = [LABELS[s] for s in tool.scopes if s not in access.scopes]
    if off:
        return "Turned off in the shop's AI assistant settings: " + ", ".join(off) + "."
    if tool.kind == CHANGE and not access.can_change:
        return (
            "Assistants can only read. Changes need Read and change "
            "in the shop's AI assistant settings."
        )
    return None


def visible(access: Access) -> list[str]:
    return [n for n in TOOLS if refusal(n, access) is None]
