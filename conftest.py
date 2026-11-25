import os

import pytest
from django.contrib.auth.models import Group, User
from django.test import Client

from reports.models import ShopSettings

# Playwright's sync API runs an event loop; the live server's ORM calls are
# still synchronous.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")


@pytest.fixture(autouse=True)
def _plain_static_storage(settings):
    # Tests run without collectstatic, so use unhashed static URLs.
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }


@pytest.fixture
def signed_in(live_server, browser, settings, db):
    settings.DEBUG = True
    contexts = []

    def _open(role, hold_tip_seen=True):
        user = User.objects.create_user(role, password="x")
        if role == "owner":
            user.groups.add(Group.objects.get_or_create(name="owner")[0])
            if hold_tip_seen:  # else the scrim blocks every flow that starts on Today
                ShopSettings.objects.update_or_create(
                    pk=1, defaults={"hold_tip_seen": True}
                )
        client = Client()
        client.force_login(user)
        context = browser.new_context(viewport={"width": 390, "height": 844})
        contexts.append(context)
        context.add_cookies(
            [
                {
                    "name": "sessionid",
                    "value": client.cookies["sessionid"].value,
                    "url": live_server.url,
                }
            ]
        )
        return context, context.new_page()

    yield _open
    for context in contexts:
        context.close()
