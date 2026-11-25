import os
import re
import shutil
import subprocess
import uuid

import psycopg
import pytest
from django.core.management import call_command
from django.db import connection
from psycopg.conninfo import make_conninfo

SCRATCH = "tailorly_restore_check"


def require_pg_tools():
    missing = None
    if not (shutil.which("pg_dump") and shutil.which("pg_restore")):
        missing = "pg_dump and pg_restore are not installed"
    else:
        out = subprocess.run(
            ["pg_dump", "--version"], capture_output=True, text=True
        ).stdout
        major = int(re.search(r"\) (\d+)", out).group(1))
        if major < connection.pg_version // 10000:
            missing = f"pg_dump {major} is older than the server"
    if missing:
        if os.environ.get("REQUIRE_PG_TOOLS") == "1":
            pytest.fail(missing)
        pytest.skip(missing)


def database_url(settings_dict, name):
    """A libpq connection string; an empty HOST stays a default socket connection."""
    params = {
        key.lower(): settings_dict[key]
        for key in ("USER", "PASSWORD", "HOST", "PORT")
        if settings_dict[key]
    }
    return make_conninfo(dbname=name, **params)


@pytest.mark.django_db(transaction=True)
def test_backup_restores_on_scratch_database(tmp_path, monkeypatch):
    require_pg_tools()
    cfg = connection.settings_dict
    monkeypatch.setenv("DATABASE_URL", database_url(cfg, cfg["NAME"]))
    call_command("backup", dir=tmp_path, keep=14)
    (dump,) = tmp_path.glob("*.dump")
    scratch = f"{SCRATCH}_{uuid.uuid4().hex}"
    scratch_url = database_url(cfg, scratch)
    with connection.cursor() as cursor:
        cursor.execute(f"CREATE DATABASE {scratch}")
    try:
        subprocess.run(
            ["pg_restore", "--no-owner", f"--dbname={scratch_url}", str(dump)],
            check=True,
        )
        with psycopg.connect(scratch_url) as conn:
            count = conn.execute("select count(*) from django_migrations").fetchone()
        assert count[0] > 0
    finally:
        with connection.cursor() as cursor:
            cursor.execute(f"DROP DATABASE IF EXISTS {scratch} WITH (FORCE)")
