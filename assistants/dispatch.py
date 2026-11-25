"""The scope gate and the activity log for MCP tool calls."""

from reports.models import ShopSettings

from . import scopes
from .models import AssistantActivity


class Refused(Exception):
    pass


def authorize(name: str) -> None:
    reason = scopes.refusal(name, scopes.Access.of(ShopSettings.current()))
    if reason:
        raise Refused(reason)


def record(key_id: int, name: str, outcome: str = "") -> AssistantActivity:
    """outcome: "" (done), "refused" or "failed"."""
    tool = scopes.TOOLS.get(name)
    kind = tool.kind if tool else AssistantActivity.READ
    what = name if not outcome else f"{name} · {outcome}"
    return AssistantActivity.objects.create(key_id=key_id, what=what[:120], kind=kind)
