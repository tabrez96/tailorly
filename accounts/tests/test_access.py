import uuid

import pytest
from django.contrib.auth.models import User
from django.urls import URLPattern, URLResolver, get_resolver, reverse
from django.urls.converters import IntConverter, UUIDConverter

from accounts.roles import OWNER, add_to_role

PUBLIC = {"sign_in", "sign_out", "manifest", "styleguide"}
HTMX = {"HX-Request": "true", "HX-Request-Type": "partial"}


def url_patterns(patterns=None, prefix=""):
    for p in patterns if patterns is not None else get_resolver().url_patterns:
        if isinstance(p, URLResolver):
            if p.namespace == "admin":
                continue
            yield from url_patterns(p.url_patterns)
        elif isinstance(p, URLPattern):
            yield p


def sample_url(pattern):
    values = {}
    for name, converter in pattern.pattern.converters.items():
        if isinstance(converter, IntConverter):
            values[name] = 1
        elif isinstance(converter, UUIDConverter):
            values[name] = uuid.UUID(int=1)
        else:
            values[name] = "x"
    return reverse(pattern.name, kwargs=values)


def owner_patterns():
    return [
        p
        for p in url_patterns()
        if getattr(p.callback, "required_role", None) == "owner"
    ]


def test_owner_patterns_found():
    names = {p.name for p in owner_patterns()}
    assert {"today", "shell_check", "sample_sheet"} <= names


@pytest.mark.parametrize("headers", [{}, HTMX], ids=["full", "htmx"])
def test_every_owner_url_refuses_employee(client, db, headers):
    client.force_login(User.objects.create_user("emp", password="x"))
    for pattern in owner_patterns():
        url = sample_url(pattern)
        for method in (client.get, client.post):
            response = method(url, headers=headers)
            if headers:
                assert response.status_code == 403, url
                assert response["HX-Redirect"] == "/my-work/", url
            else:
                assert response.status_code == 302, url
                assert response["Location"] == "/my-work/", url


def test_every_url_is_classified():
    unclassified = [
        p.name
        for p in url_patterns()
        if not hasattr(p.callback, "required_role") and p.name not in PUBLIC
    ]
    assert unclassified == []


def test_owner_reaches_owner_urls(client, db):
    owner = User.objects.create_user("own", password="x")
    add_to_role(owner, OWNER)
    client.force_login(owner)
    assert client.get("/").status_code == 200
