import httpx2 as httpx
import pytest
from asgiref.sync import async_to_sync

from assistants import keys
from assistants.gate import KeyGate, check_request
from assistants.models import AccessKey
from reports.models import ShopSettings


def settings_on(**extra):
    ShopSettings.objects.update_or_create(pk=1, defaults={"mcp_on": True, **extra})


def make_key(**extra):
    raw, prefix, key_hash = keys.generate()
    return raw, AccessKey.objects.create(
        name="Claude", prefix=prefix, key_hash=key_hash, **extra
    )


@pytest.mark.django_db
def test_no_header_is_401():
    settings_on()
    assert check_request(None) == (401, None)
    assert check_request("Bearer ") == (401, None)


@pytest.mark.django_db
def test_wrong_scheme_is_401():
    settings_on()
    raw, _ = make_key()
    assert check_request(f"Basic {raw}") == (401, None)


@pytest.mark.django_db
def test_unknown_key_is_401():
    settings_on()
    assert check_request("Bearer tly_mcp_nope") == (401, None)


@pytest.mark.django_db
def test_revoked_key_is_401():
    from django.utils import timezone

    settings_on()
    raw, key = make_key(revoked_at=timezone.now())
    assert check_request(f"Bearer {raw}") == (401, None)
    key.refresh_from_db()
    assert key.last_used_at is None


@pytest.mark.django_db
def test_server_off_is_403():
    ShopSettings.objects.update_or_create(pk=1, defaults={"mcp_on": False})
    raw, key = make_key()
    assert check_request(f"Bearer {raw}") == (403, None)
    key.refresh_from_db()
    assert key.last_used_at is None


@pytest.mark.django_db
def test_valid_key_sets_last_used():
    settings_on()
    raw, key = make_key()
    assert check_request(f"bearer  {raw} ") == (200, key.pk)
    key.refresh_from_db()
    assert key.last_used_at is not None


def test_check_request_closes_old_connections(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "assistants.gate.close_old_connections", lambda: calls.append(1)
    )
    assert check_request(None) == (401, None)
    assert calls == [1]


def _post(app, headers=None):
    async def go():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8001"
        ) as client:
            return await client.post("/mcp", headers=headers or {})

    return async_to_sync(go)()


@pytest.mark.django_db
def test_keygate_returns_401_json_and_does_not_call_app():
    calls = []

    async def app(scope, receive, send):
        calls.append(scope)

    response = _post(KeyGate(app))
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"error": "invalid_key"}
    assert calls == []


@pytest.mark.django_db
def test_keygate_returns_403_when_off():
    raw, _ = make_key()

    async def app(scope, receive, send):
        raise AssertionError("not called")

    response = _post(KeyGate(app), {"Authorization": f"Bearer {raw}"})
    assert response.status_code == 403


@pytest.mark.django_db
def test_keygate_passes_key_id_to_app():
    settings_on()
    raw, key = make_key()
    seen = []

    async def app(scope, receive, send):
        seen.append(scope["state"]["mcp_key_id"])
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    response = _post(KeyGate(app), {"Authorization": f"Bearer {raw}"})
    assert response.status_code == 200
    assert seen == [key.pk]


@pytest.mark.django_db
def test_keygate_passes_lifespan_through():
    seen = []

    async def app(scope, receive, send):
        seen.append(scope["type"])

    async_to_sync(KeyGate(app).__call__)({"type": "lifespan"}, None, None)
    assert seen == ["lifespan"]
