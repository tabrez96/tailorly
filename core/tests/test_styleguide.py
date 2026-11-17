import json
from pathlib import Path

from django.template.loader import render_to_string

STATIC = Path(__file__).resolve().parent.parent.parent / "static"


def test_styleguide_404_when_debug_off(client, settings):
    settings.DEBUG = False
    assert client.get("/styleguide/").status_code == 404


def test_styleguide_renders_when_debug_on(client, settings):
    settings.DEBUG = True
    response = client.get("/styleguide/")
    assert response.status_code == 200
    html = response.content.decode()
    for needle in (
        'data-sg="hero"',
        'class="chip chip--ok"',
        "tokens.css",
        "components.css",
    ):
        assert needle in html


def test_dark_query_sets_theme(client, settings):
    settings.DEBUG = True
    assert 'data-theme="dark"' in client.get("/styleguide/?theme=dark").content.decode()
    assert "data-theme" not in client.get("/styleguide/").content.decode()


def test_favicon_and_manifest_links(client, settings):
    settings.DEBUG = True
    html = client.get("/styleguide/").content.decode()
    assert 'rel="icon" href="/static/brand/mark.svg"' in html
    assert 'rel="apple-touch-icon"' in html
    assert 'rel="manifest" href="/manifest.webmanifest"' in html


def test_manifest(client, settings):
    settings.DEBUG = False
    response = client.get("/manifest.webmanifest")
    assert response.status_code == 200
    assert response["Content-Type"] == "application/manifest+json"
    data = json.loads(response.content)
    assert data["name"] == "Tailorly"
    sizes = {icon["sizes"] for icon in data["icons"]}
    assert {"192x192", "512x512", "any"} <= sizes
    for icon in data["icons"]:
        assert (STATIC / icon["src"].removeprefix("/static/")).exists()


def test_chip_partial():
    html = render_to_string(
        "components/chip.html", {"tone": "warn", "label": "Not started"}
    )
    assert "chip--warn" in html
    assert '<span class="chip__dot" aria-hidden="true"></span>' in html
    assert "Not started" in html
    assert "chip--grey" in render_to_string("components/chip.html", {"label": "Draft"})


def test_styleguide_form_controls(client, settings):
    settings.DEBUG = True
    html = client.get("/styleguide/").content.decode()
    for hook in (
        "seg",
        "seg-4",
        "fchips",
        "switches",
        "checks",
        "radios",
        "fields",
        "errors",
    ):
        assert f'data-sg="{hook}"' in html
    assert 'role="alert"' in html and 'role="switch"' in html
    ready = client.get("/styleguide/?status=ready").content.decode()
    assert 'aria-current="true">Ready' in ready
