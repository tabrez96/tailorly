"""The scope gate and the activity log for MCP tool calls."""

from contextvars import ContextVar

from orders.models import Order
from reports.models import ShopSettings

from . import scopes
from .models import AssistantActivity

# Set by a change tool to the number of the order it changed or made.
touched_order: ContextVar[int | None] = ContextVar("touched_order", default=None)


class Refused(Exception):
    pass


def authorize(name: str) -> None:
    reason = scopes.refusal(name, scopes.Access.of(ShopSettings.current()))
    if reason:
        raise Refused(reason)


def record(
    key_id: int, name: str, outcome: str = "", order_number: int | None = None
) -> AssistantActivity:
    """outcome: "" (done), "refused" or "failed"."""
    tool = scopes.TOOLS.get(name)
    kind = tool.kind if tool else AssistantActivity.READ
    what = name if not outcome else f"{name} · {outcome}"
    order = (
        Order.objects.filter(number=order_number).first()
        if isinstance(order_number, int) and not isinstance(order_number, bool)
        else None
    )
    return AssistantActivity.objects.create(
        key_id=key_id, what=what[:120], kind=kind, order=order
    )
