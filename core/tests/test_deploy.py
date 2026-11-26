import os
import re
import subprocess
import sys

import dj_database_url
from django.conf import settings

ROOT = settings.BASE_DIR
DEPLOY = ROOT / "deploy"


def parse_env(path):
    values = {}
    for line in path.read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            key, value = line.split("=", 1)
            values[key] = value.strip("\"'")
    return values


def test_check_deploy_passes_with_production_example():
    env = {
        "PATH": os.environ["PATH"],
        "DATABASE_URL": "postgres://tailorly:abc123@db:5432/tailorly",
        **parse_env(DEPLOY / "production.env.example"),
    }
    result = subprocess.run(
        [sys.executable, "manage.py", "check", "--deploy", "--fail-level", "WARNING"],
        cwd=settings.BASE_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


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


def test_compose_database_url_points_at_db_service():
    line = next(
        line
        for line in (ROOT / "compose.yaml").read_text().splitlines()
        if line.strip().startswith("DATABASE_URL:")
    )
    url = re.sub(r"\$\{POSTGRES_PASSWORD[^}]*\}", "abc123", line.split(":", 1)[1])
    config = dj_database_url.parse(url.strip())
    assert config["HOST"] == "db"
    assert config["PORT"] == 5432
    assert config["NAME"] == "tailorly"
    assert config["PASSWORD"] == "abc123"


def test_compose_publishes_only_on_localhost():
    published = set()
    in_ports = False
    for line in (ROOT / "compose.yaml").read_text().splitlines():
        if line.strip() == "ports:":
            in_ports = True
        elif in_ports and (match := re.match(r'^\s*-\s*"(.+?)"\s*$', line)):
            published.add(match.group(1))
        else:
            in_ports = False
    assert published == {"127.0.0.1:8000:8000", "127.0.0.1:8001:8001"}


def test_production_env_example_has_no_database_url():
    values = parse_env(DEPLOY / "production.env.example")
    assert "POSTGRES_PASSWORD" in values
    for key in ("DATABASE_URL", "MEDIA_ROOT", "BACKUP_DIR"):
        assert key not in values


def test_dockerfile_runs_as_non_root():
    lines = (ROOT / "Dockerfile").read_text().splitlines()
    last_user = max(i for i, line in enumerate(lines) if line.startswith("USER "))
    last_from = max(i for i, line in enumerate(lines) if line.startswith("FROM "))
    assert lines[last_user] == "USER tailorly"
    assert last_user > last_from


def test_dockerignore_excludes_env():
    lines = (ROOT / ".dockerignore").read_text().splitlines()
    assert ".env" in lines
    assert ".git" in lines


def test_backup_service_runs_in_web_container():
    lines = (DEPLOY / "tailorly-backup.service").read_text().splitlines()
    run = "ExecStart=/usr/bin/docker compose exec -T web python manage.py"
    assert [line for line in lines if line.startswith("ExecStart=")] == [
        f"{run} backup --keep 14",
        f"{run} delete_old_drafts",
    ]


def test_host_web_and_mcp_units_removed():
    assert not (DEPLOY / "tailorly-web.service").exists()
    assert not (DEPLOY / "tailorly-mcp.service").exists()
