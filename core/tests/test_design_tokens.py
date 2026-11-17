import re
from pathlib import Path

from core.csscheck import (
    colour_literals,
    declarations,
    template_colour_literals,
    value_colour_literals,
)

ROOT = Path(__file__).resolve().parent.parent.parent
CSS_DIR = ROOT / "static" / "css"
TOKENS = (CSS_DIR / "tokens.css").read_text()
DARK = '[data-theme="dark"]'
DARK_MEDIA = ':root:not([data-theme="light"])'
SKIP = {".venv", "node_modules", "design", "staticfiles"}


def _templates():
    for path in ROOT.rglob("*.html"):
        if not SKIP & set(path.relative_to(ROOT).parts) and "templates" in path.parts:
            yield path


def test_no_colour_literals_outside_tokens():
    problems = []
    for path in CSS_DIR.rglob("*.css"):
        if path.name != "tokens.css":
            problems += [
                f"{path.name}: {lit}" for lit in colour_literals(path.read_text())
            ]
    for path in _templates():
        problems += [
            f"{path.relative_to(ROOT)}: {lit}"
            for lit in template_colour_literals(path.read_text())
        ]
    assert problems == []


def test_dark_blocks_identical():
    assert declarations(TOKENS, DARK) == declarations(TOKENS, DARK_MEDIA)


def test_every_light_colour_token_has_dark_value():
    light = declarations(TOKENS, ":root")
    dark = declarations(TOKENS, DARK)
    coloured = {k for k, v in light.items() if value_colour_literals(v)}
    assert coloured <= set(dark)
    assert set(dark) <= set(light) | {"color-scheme"}


def test_font_is_self_hosted():
    blocks = re.findall(r"@font-face\s*\{[^}]*\}", TOKENS)
    assert len(blocks) == 2
    for block in blocks:
        assert re.search(r'src:\s*url\("\.\./vendor/fonts/', block)
    for name in ("plus-jakarta-sans-latin.woff2", "plus-jakarta-sans-latin-ext.woff2"):
        assert (ROOT / "static" / "vendor" / "fonts" / name).exists()


def test_bare_named_light_token_needs_dark_value():
    light = {"--ink": "red"}
    coloured = {k for k, v in light.items() if value_colour_literals(v)}
    assert coloured == {"--ink"}
