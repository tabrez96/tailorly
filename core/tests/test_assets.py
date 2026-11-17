from core.assets import version_of


def test_version_changes_with_content(tmp_path):
    a = tmp_path / "a.css"
    a.write_bytes(b"one")
    first = version_of(tmp_path, [a])
    assert version_of(tmp_path, [a]) == first
    assert len(first) == 12 and int(first, 16) >= 0
    a.write_bytes(b"onf")
    assert version_of(tmp_path, [a]) != first
