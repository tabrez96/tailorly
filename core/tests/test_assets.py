import pytest

from core.assets import asset_version, version_of


def test_version_changes_with_content(tmp_path):
    a = tmp_path / "a.css"
    a.write_bytes(b"one")
    first = version_of(tmp_path, [a])
    assert version_of(tmp_path, [a]) == first
    assert len(first) == 12 and int(first, 16) >= 0
    a.write_bytes(b"onf")
    assert version_of(tmp_path, [a]) != first


@pytest.fixture
def fresh_asset_version():
    asset_version.cache_clear()
    yield
    asset_version.cache_clear()


def test_release_version_wins(settings, fresh_asset_version):
    settings.ASSET_VERSION = "abc123"
    assert asset_version() == "abc123"
