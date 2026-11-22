import re

import pytest
from django.template import Context, Template

from core.thumbs import count_badge, photo_alt, thumb_context


def render(source, **context):
    return Template("{% load ui %}" + source).render(Context(context))


def test_photo_alt():
    assert photo_alt("Blouse", 1, 3) == "Blouse, photo 1 of 3"


def test_count_badge():
    assert count_badge(1, 3) == "1/3"
    assert count_badge(1, 1) == ""
    assert count_badge(1, 0) == ""


def test_thumb_context_unknown_size():
    with pytest.raises(ValueError):
        thumb_context("Blouse", "/p.jpg", 1, "xl")


def test_thumb_with_several_photos():
    html = render('{% thumb "Blouse" "/p.jpg" 3 "sm" %}')
    assert 'class="thumb thumb--sm"' in html
    assert 'alt="Blouse, photo 1 of 3"' in html
    assert '<span class="thumb__badge" aria-hidden="true">1/3</span>' in html


def test_thumb_with_one_photo_has_no_badge():
    html = render('{% thumb "Blouse" "/p.jpg" 1 "sm" %}')
    assert 'alt="Blouse, photo 1 of 1"' in html
    assert "thumb__badge" not in html


def test_thumb_without_photo_shows_camera():
    html = render('{% thumb "Blouse" None 0 "sm" %}')
    assert "thumb--empty" in html
    assert 'role="img"' in html
    assert 'aria-label="Blouse, no photo"' in html
    assert 'data-icon="camera"' in html
    assert "<img" not in html


@pytest.mark.parametrize("size", ["sm", "md", "lg"])
def test_thumb_sizes(size):
    assert f"thumb--{size}" in render("{% thumb 'Blouse' '/p.jpg' 1 size %}", size=size)


def test_thumb_escapes_name():
    html = render("{% thumb name '/p.jpg' 2 'sm' %}", name='A & "B"')
    assert 'alt="A &amp; &quot;B&quot;, photo 1 of 2"' in html


def test_measure_tiles():
    tiles = [{"label": "Bust", "value": "34"}] + [
        {"label": f"M{i}", "value": str(i)} for i in range(5)
    ]
    html = render('{% include "components/measure_tiles.html" %}', tiles=tiles)
    html = re.sub(r"\s+(?=<)|(?<=>)\s+", "", html)
    assert html.count('class="tile"') == 6
    assert '<dt class="tile__label">Bust</dt>' in html
    assert '<dd class="tile__value">34</dd>' in html


ROW = {
    "rank": 3,
    "garment": "Kurta",
    "order_label": "ORD-1044",
    "due_label": "Due Mon 16 Nov",
    "due_soon": False,
    "time_needed": "about 2h",
    "tone": "warn",
    "status": "Not started",
    "moved": False,
    "photo": None,
    "photo_count": 0,
    "picked": False,
}


def render_row(**changes):
    return render(
        '{% include "components/queue_row.html" %}',
        row={**ROW, **changes},
        total=4,
    )


def test_queue_row():
    html = render_row()
    for text in ("Kurta", "ORD-1044", "Not started", "about 2h", ">3</span>"):
        assert text in html
    assert 'data-icon="drag"' in html
    assert 'aria-label="Move Kurta, 3 of 4"' in html
    assert 'aria-pressed="false"' in html
    assert "qrow--picked" not in html
    assert "qrow__due--soon" not in html
    assert "Moved by you" not in html


def test_queue_row_picked_and_moved():
    html = render_row(picked=True, moved=True)
    assert "qrow--picked" in html
    assert 'aria-pressed="true"' in html
    assert "Moved by you" in html


def test_queue_row_due_soon():
    assert "qrow__due--soon" in render_row(due_soon=True)
