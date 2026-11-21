import json
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parents[2] / "static/js/material_sheet.js"
SCRIPT = """
const vm = require("vm");
const fs = require("fs");
const ctx = { document: { addEventListener() {} } };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1], "utf8"), ctx);
const cases = JSON.parse(process.argv[2]);
console.log(JSON.stringify(cases.map(([n, u]) => ctx.materialTotal(n, u))));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_material_total_rounds_half_up_like_the_server():
    cases = [[0.5, "2.01"], [1.5, "80"], [0.25, "100"], [2, "0.335"], [0.8, "12.5"]]
    out = subprocess.run(
        ["node", "-e", SCRIPT, str(JS), json.dumps(cases)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert json.loads(out) == ["1.01", "120", "25", "0.67", "10"]
