import pytest

from assistants import dispatch, keys
from assistants.models import AccessKey, AssistantActivity
from reports.models import ShopSettings


def make_key():
    _, prefix, key_hash = keys.generate()
    return AccessKey.objects.create(name="Claude", prefix=prefix, key_hash=key_hash)


@pytest.mark.django_db
def test_authorize_refuses_change_tool_under_only_read():
    ShopSettings.objects.update_or_create(pk=1, defaults={"mcp_can_change": False})
    for name in ("create_order", "record_payment", "update_measurements"):
        with pytest.raises(dispatch.Refused):
            dispatch.authorize(name)
    ShopSettings.objects.update_or_create(pk=1, defaults={"mcp_can_change": True})
    dispatch.authorize("create_order")


@pytest.mark.django_db
def test_authorize_refuses_tool_with_scope_off():
    ShopSettings.objects.update_or_create(pk=1, defaults={"mcp_orders": False})
    with pytest.raises(dispatch.Refused, match="Orders and customers"):
        dispatch.authorize("get_order")


@pytest.mark.django_db
def test_record_writes_activity_with_key_tool_and_kind():
    key = make_key()
    row = dispatch.record(key.pk, "get_order")
    assert (row.key, row.what, row.kind) == (key, "get_order", AssistantActivity.READ)
    assert dispatch.record(key.pk, "create_order").kind == AssistantActivity.CHANGE


@pytest.mark.django_db
def test_record_refused_and_failed_suffix():
    key = make_key()
    assert dispatch.record(key.pk, "get_order", "refused").what == "get_order · refused"
    assert dispatch.record(key.pk, "get_order", "failed").what == "get_order · failed"
    unknown = dispatch.record(key.pk, "nope", "refused")
    assert (unknown.what, unknown.kind) == ("nope · refused", AssistantActivity.READ)
