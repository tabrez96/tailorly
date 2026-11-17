import os

import pytest

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
