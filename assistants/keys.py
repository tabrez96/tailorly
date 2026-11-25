"""Access keys for the MCP server: made once, shown once, stored only as a hash."""

import hashlib
import secrets

PREFIX = "tly_mcp_"


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def generate() -> tuple[str, str, str]:
    """(full key, 8-char prefix, hash). The full key is never stored."""
    body = secrets.token_urlsafe(24)  # 32 chars
    raw = PREFIX + body
    return raw, body[:8], hash_key(raw)
