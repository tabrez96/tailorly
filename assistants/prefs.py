"""S21: reading a switch post and the status lines."""

from datetime import datetime

from django.utils import timezone

SWITCHES = {
    "on": "mcp_on",
    "orders": "mcp_orders",
    "measurements": "mcp_measurements",
    "money": "mcp_money",
    "staff": "mcp_staff",
}


def parse(name: str, value: str | None) -> tuple[str, bool] | None:
    """A switch post -> (ShopSettings field, new value); None if not allowed.

    Switches post value "on" when checked and nothing when unchecked; mode posts
    "read" or "change".
    """
    if name in SWITCHES:
        return SWITCHES[name], value == "on"
    if name == "mode" and value in ("read", "change"):
        return "mcp_can_change", value == "change"
    return None


def apps_text(count: int) -> str:
    if not count:
        return "no apps connected"
    return f"{count} app connected" if count == 1 else f"{count} apps connected"


def server_line(on: bool, keys: int) -> str:
    return f"On · {apps_text(keys)}" if on else "Off"


def settings_line(on: bool, keys: int, can_change: bool) -> str:
    if not on:
        return "Off"
    mode = "read and change" if can_change else "only read"
    return f"{server_line(on, keys)} · {mode}"


def key_used(last_used_at: datetime | None) -> str:
    if last_used_at is None:
        return "Not used yet"
    return f"Used {timezone.localtime(last_used_at):%-d %b}"
