import tarfile
from datetime import UTC, datetime
from subprocess import CalledProcessError

import pytest
from django.core.management import call_command

from core.backups import backup_stem, stale_backups


def pair(stem):
    return [f"{stem}.dump", f"{stem}-media.tar.gz"]


def test_backup_stem_uses_shop_time():
    now = datetime(2026, 11, 24, 21, 0, tzinfo=UTC)
    assert backup_stem(now) == "tailorly-2026-11-25-023000"


def test_stale_backups_keeps_newest():
    names = pair("tailorly-2026-11-01-000000") + pair("tailorly-2026-11-02-000000")
    names += pair("tailorly-2026-11-03-000000")
    assert stale_backups(names, 2) == sorted(pair("tailorly-2026-11-01-000000"))


def test_stale_backups_ignores_other_files():
    names = ["x.partial", "notes.txt", "tailorly-2026-11-01-000000.dump.partial"]
    assert stale_backups(names + pair("tailorly-2026-11-02-000000"), 1) == []


def test_stale_backups_counts_complete_pairs_only():
    names = pair("tailorly-2026-11-01-000000") + pair("tailorly-2026-11-02-000000")
    orphan = "tailorly-2026-11-03-000000.dump"
    assert stale_backups(names + [orphan], 2) == [orphan]


def test_stale_backups_fewer_than_keep():
    assert stale_backups(pair("tailorly-2026-11-01-000000"), 14) == []


def test_stale_backups_rejects_zero():
    with pytest.raises(ValueError):
        stale_backups([], 0)


def fake_dump(args, check):
    path = next(a for a in args if a.startswith("--file=")).removeprefix("--file=")
    with open(path, "wb") as f:
        f.write(b"dump")


@pytest.fixture
def env(settings, tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres:///x")
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.MEDIA_ROOT.mkdir()
    (settings.MEDIA_ROOT / "a.jpg").write_bytes(b"jpg")
    return tmp_path / "b"


def test_backup_command_writes_pair_and_prunes(env, monkeypatch):
    monkeypatch.setattr("core.management.commands.backup.subprocess.run", fake_dump)
    env.mkdir()
    for day in range(1, 16):
        for name in pair(f"tailorly-2026-01-{day:02d}-000000"):
            (env / name).write_bytes(b"old")
    call_command("backup", dir=env, keep=14)
    dumps = sorted(p.name for p in env.glob("*.dump"))
    assert len(dumps) == 14 and len(list(env.glob("*-media.tar.gz"))) == 14
    assert "tailorly-2026-01-01-000000.dump" not in dumps
    newest = dumps[-1].removesuffix(".dump")
    assert newest > "tailorly-2026-01-15"
    with tarfile.open(env / f"{newest}-media.tar.gz") as tar:
        assert "media/a.jpg" in tar.getnames()


def test_backup_command_writes_empty_media_archive(env, settings, monkeypatch):
    monkeypatch.setattr("core.management.commands.backup.subprocess.run", fake_dump)
    settings.MEDIA_ROOT = env.parent / "missing"
    call_command("backup", dir=env, keep=14)
    (archive,) = env.glob("*-media.tar.gz")
    with tarfile.open(archive) as tar:
        assert tar.getnames() == []


def test_backup_command_cleans_partial_on_failure(env, monkeypatch):
    def failing(args, check):
        fake_dump(args, check)
        raise CalledProcessError(1, "pg_dump")

    monkeypatch.setattr("core.management.commands.backup.subprocess.run", failing)
    with pytest.raises(CalledProcessError):
        call_command("backup", dir=env, keep=14)
    assert list(env.iterdir()) == []
