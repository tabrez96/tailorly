import os
import subprocess
import sys

import dj_database_url
from django.conf import settings

DEPLOY = settings.BASE_DIR / "deploy"


def parse_env(path):
    values = {}
    for line in path.read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            key, value = line.split("=", 1)
            values[key] = value.strip("\"'")
    return values


def test_check_deploy_passes_with_production_example():
    env = {"PATH": os.environ["PATH"], **parse_env(DEPLOY / "production.env.example")}
    result = subprocess.run(
        [sys.executable, "manage.py", "check", "--deploy", "--fail-level", "WARNING"],
        cwd=settings.BASE_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_production_database_url_uses_socket():
    config = dj_database_url.parse("postgres:///tailorly")
    assert config["NAME"] == "tailorly"
    assert not config["HOST"]


def test_no_tunnel_credentials_in_deploy():
    for path in DEPLOY.iterdir():
        assert path.suffix not in {".json", ".pem"}, path
        text = path.read_text()
        for marker in ("TunnelSecret", "AccountTag", "eyJ"):
            assert marker not in text, (path, marker)


def test_cloudflared_routes_mcp_first():
    lines = (DEPLOY / "cloudflared.example.yml").read_text().splitlines()
    services = [
        line.split("service:")[1].strip() for line in lines if "service:" in line
    ]
    assert services == [
        "http://127.0.0.1:8001",
        "http://127.0.0.1:8000",
        "http_status:404",
    ]
