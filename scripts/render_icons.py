"""Render the PNG icons in static/brand/ from static/brand/mark.svg with Playwright."""

from pathlib import Path

from playwright.sync_api import sync_playwright

BRAND = Path(__file__).resolve().parent.parent / "static" / "brand"
ICONS = [
    ("favicon-32.png", 32, None),
    ("icon-192.png", 192, None),
    ("icon-512.png", 512, None),
    ("apple-touch-icon.png", 180, "#F6F2ED"),
]


def main() -> None:
    svg = (BRAND / "mark.svg").read_text()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, size, background in ICONS:
            page = browser.new_page(viewport={"width": size, "height": size})
            sized = svg.replace(
                'width="64" height="64"', f'width="{size}" height="{size}"', 1
            )
            fill = background or "transparent"
            page.set_content(
                f'<html><body style="margin:0;background:{fill}">{sized}</body></html>'
            )
            page.screenshot(path=str(BRAND / name), omit_background=background is None)
            page.close()
        browser.close()


if __name__ == "__main__":
    main()
