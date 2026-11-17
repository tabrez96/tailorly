import pytest
from django.apps import apps
from django.conf import settings
from django.db import connection

APP_LABELS = [
    "core",
    "accounts",
    "catalog",
    "customers",
    "orders",
    "production",
    "staff",
    "reports",
    "today",
    "assistants",
]


def test_time_zone():
    assert settings.TIME_ZONE == "Asia/Kolkata"
    assert settings.USE_TZ is True


@pytest.mark.django_db
def test_database_is_postgresql_18():
    assert connection.vendor == "postgresql"
    assert connection.pg_version >= 180000


def test_all_apps_installed():
    for label in APP_LABELS:
        assert label in apps.app_configs
