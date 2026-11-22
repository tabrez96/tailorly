import json
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parents[2] / "static/js/timer.js"
SCRIPT = """
const vm = require("vm");
const fs = require("fs");
const ctx = { document: { addEventListener() {} } };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1], "utf8"), ctx);
const [fn, cases] = JSON.parse(process.argv[2]);
console.log(JSON.stringify(cases.map((n) => ctx[fn](n))));
"""


def run(fn, cases):
    out = subprocess.run(
        ["node", "-e", SCRIPT, str(JS), json.dumps([fn, cases])],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return json.loads(out)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_timer_text_matches_python():
    assert run("timerText", [0, 59, 5110, 36000]) == [
        "0:00:00",
        "0:00:59",
        "1:25:10",
        "10:00:00",
    ]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_spoken_time():
    assert run("spokenTime", [0, 1, 85, 60]) == [
        "0 minutes",
        "1 minute",
        "1 hour 25 minutes",
        "1 hour",
    ]
