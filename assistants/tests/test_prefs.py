from datetime import UTC, datetime

from assistants import prefs


def test_parse_switches():
    for name, field in prefs.SWITCHES.items():
        assert prefs.parse(name, "on") == (field, True)
        assert prefs.parse(name, None) == (field, False)


def test_parse_mode_and_unknown():
    assert prefs.parse("mode", "change") == ("mcp_can_change", True)
    assert prefs.parse("mode", "read") == ("mcp_can_change", False)
    assert prefs.parse("mode", "x") is None
    assert prefs.parse("hold_tip_seen", "on") is None


def test_lines():
    assert prefs.server_line(False, 2) == "Off"
    assert prefs.server_line(True, 1) == "On · 1 app connected"
    assert prefs.server_line(True, 0) == "On · no apps connected"
    assert prefs.settings_line(False, 2, True) == "Off"
    assert prefs.settings_line(True, 2, False) == "On · 2 apps connected · only read"
    assert prefs.settings_line(True, 2, True).endswith("read and change")
    assert prefs.key_used(None) == "Not used yet"
    used = datetime(2026, 11, 5, 8, 0, tzinfo=UTC)
    assert prefs.key_used(used) == "Used 5 Nov"
