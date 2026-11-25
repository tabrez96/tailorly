"""Key check for every request to the MCP server."""

from asgiref.sync import sync_to_async
from django.db import close_old_connections
from django.utils import timezone

from reports.models import ShopSettings

from . import keys
from .models import AccessKey


def check_request(authorization: str | None) -> tuple[int, int | None]:
    """(status, key id): 401 for a bad or revoked key, 403 while off, else 200."""
    close_old_connections()  # uvicorn never fires Django's request signals
    scheme, _, raw = (authorization or "").strip().partition(" ")
    raw = raw.strip()
    if scheme.lower() != "bearer" or not raw:
        return 401, None
    key = AccessKey.active().filter(key_hash=keys.hash_key(raw)).only("id").first()
    if key is None:
        return 401, None
    if not ShopSettings.current().mcp_on:
        return 403, None
    AccessKey.objects.filter(pk=key.pk).update(last_used_at=timezone.now())
    return 200, key.pk


class KeyGate:
    """ASGI middleware: only requests with a good key reach the MCP app."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":  # lifespan passes through
            return await self.app(scope, receive, send)
        header = dict(scope["headers"]).get(b"authorization")
        status, key_id = await sync_to_async(check_request)(
            header.decode("latin-1") if header else None
        )
        if status != 200:
            body = {401: b'{"error":"invalid_key"}', 403: b'{"error":"server_off"}'}[
                status
            ]
            headers = [(b"content-type", b"application/json")]
            if status == 401:
                headers.append((b"www-authenticate", b"Bearer"))
            await send(
                {"type": "http.response.start", "status": status, "headers": headers}
            )
            await send({"type": "http.response.body", "body": body})
            return
        scope.setdefault("state", {})["mcp_key_id"] = key_id
        await self.app(scope, receive, send)
