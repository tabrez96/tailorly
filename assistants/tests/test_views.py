import hashlib
import re
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from assistants.models import AccessKey, AssistantActivity
from reports.models import ShopSettings

HX = {"HTTP_HX_REQUEST": "true"}


def make_key(name, **extra):
    return AccessKey.objects.create(
        name=name,
        prefix="abcd1234",
        key_hash=hashlib.sha256(name.encode()).hexdigest(),
        **extra,
    )


def page(client):
    return client.get(reverse("assistants")).content.decode()


@pytest.mark.django_db
def test_first_run_defaults(owner):
    s = ShopSettings.current()
    assert not (s.mcp_on or s.mcp_can_change or s.mcp_staff)
    assert s.mcp_orders and s.mcp_measurements and s.mcp_money
    html = page(owner)
    assert "No assistant connected" in html and "Server address" not in html


def test_owner_only(ali, client):
    urls = [
        reverse("assistants"),
        reverse("assistants_set"),
        reverse("assistant_key_new"),
        reverse("assistant_key_revoke", args=[1]),
    ]
    for url in urls:
        assert ali.client.post(url).status_code in (302, 403)
        assert client.post(url).status_code == 302
        assert client.get(url).status_code == 302


def test_switch_saves(owner):
    url = reverse("assistants_set")
    response = owner.post(url, {"name": "staff", "value": "on"}, **HX)
    assert ShopSettings.current().mcp_staff
    assert 'id="assistants"' in response.content.decode()
    owner.post(url, {"name": "staff"}, **HX)
    assert not ShopSettings.current().mcp_staff


def test_switch_without_htmx_redirects(owner):
    response = owner.post(reverse("assistants_set"), {"name": "on", "value": "on"})
    assert response.status_code == 303 and response["Location"] == reverse("assistants")
    assert ShopSettings.current().mcp_on


def test_switch_unknown_400(owner):
    response = owner.post(
        reverse("assistants_set"), {"name": "hold_tip_seen", "value": "on"}, **HX
    )
    assert response.status_code == 400 and response["HX-Reswap"] == "none"
    assert not ShopSettings.current().hold_tip_seen


def test_mode_change(owner):
    ShopSettings.objects.update_or_create(pk=1, defaults={"mcp_on": True})
    owner.post(reverse("assistants_set"), {"name": "mode", "value": "change"}, **HX)
    assert ShopSettings.current().mcp_can_change
    assert 'id="mcp-mode-change"' in page(owner)


def test_full_key_shown_once_hash_stored(owner):
    ShopSettings.objects.update_or_create(pk=1, defaults={"mcp_on": True})
    response = owner.post(
        reverse("assistant_key_new"), {"name": "Claude on tablet"}, **HX
    )
    html = response.content.decode()
    raw = re.search(r"tly_mcp_[A-Za-z0-9_-]+", html).group(0)
    assert "Your new key" in html and "Copy key" in html
    key = AccessKey.objects.get()
    assert key.key_hash == hashlib.sha256(raw.encode()).hexdigest()
    assert key.prefix == raw[len("tly_mcp_") :][:8]
    for field in ("name", "prefix", "key_hash"):
        assert raw not in getattr(key, field) and raw[len("tly_mcp_") :] not in getattr(
            key, field
        )
    after = page(owner)
    assert raw not in after and raw[len("tly_mcp_") + 8 :] not in after
    assert "Claude on tablet" in after


def test_key_sheet_get(owner):
    html = owner.get(reverse("assistant_key_new")).content.decode()
    assert "New key" in html and "Make key" in html


@pytest.mark.parametrize("name", ["", "x" * 41])
def test_key_name_invalid(owner, name):
    response = owner.post(reverse("assistant_key_new"), {"name": name}, **HX)
    assert response.status_code == 422 and "field__error" in response.content.decode()
    assert not AccessKey.objects.exists()


def test_revoke_sets_revoked_at(owner):
    ShopSettings.objects.update_or_create(pk=1, defaults={"mcp_on": True})
    key = make_key("Claude on phone")
    url = reverse("assistant_key_revoke", args=[key.pk])
    response = owner.post(url, **HX)
    key.refresh_from_db()
    assert key.revoked_at is not None
    assert f'id="revoke-{key.pk}"' not in page(owner)
    assert "Claude on phone revoked" in response["HX-Trigger"]
    first = key.revoked_at
    assert owner.post(url, **HX).status_code == 200
    key.refresh_from_db()
    assert key.revoked_at == first
    assert owner.post(reverse("assistant_key_revoke", args=[999])).status_code == 404


def test_turning_off_keeps_keys(owner):
    ShopSettings.objects.update_or_create(pk=1, defaults={"mcp_on": True})
    make_key("A")
    make_key("B")
    owner.post(reverse("assistants_set"), {"name": "on"}, **HX)
    assert AccessKey.active().count() == 2
    assert "No assistant connected" in page(owner)


def test_activity_last_20_newest_first(owner):
    ShopSettings.objects.update_or_create(pk=1, defaults={"mcp_on": True})
    key = make_key("Claude")
    now = timezone.now()
    for n in range(25):
        AssistantActivity.objects.create(
            key=key,
            what=f"Looked at thing {n}",
            kind="read",
            at=now - timedelta(minutes=25 - n),
        )
    html = page(owner)
    assert html.count("Looked at thing") == 20
    assert html.index("Looked at thing 24") < html.index("Looked at thing 5")
    assert "Looked at thing 4<" not in html


def test_activity_change_links_to_order(owner, order_factory):
    ShopSettings.objects.update_or_create(pk=1, defaults={"mcp_on": True})
    key = make_key("Claude")
    order = order_factory()
    AssistantActivity.objects.create(
        key=key, what="Made a change", kind="change", order=order
    )
    AssistantActivity.objects.create(
        key=key, what="Just looking", kind="read", order=order
    )
    AssistantActivity.objects.create(key=key, what="Orphan change", kind="change")
    html = page(owner)
    assert f'href="/orders/{order.pk}/"' in html
    assert html.count(f'href="/orders/{order.pk}/"') == 1
    assert "Orphan change" in html


def test_address_from_setting(owner, settings):
    ShopSettings.objects.update_or_create(pk=1, defaults={"mcp_on": True})
    settings.MCP_SERVER_URL = "https://shop.example/mcp"
    assert "https://shop.example/mcp" in page(owner)
    settings.MCP_SERVER_URL = ""
    assert "http://testserver/mcp" in page(owner)
