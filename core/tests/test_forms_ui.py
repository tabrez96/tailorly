import re

import pytest
from django import forms
from django.core.exceptions import ValidationError
from django.template import Context, Template

from core.forms_ui import choice_options, describedby, error_summary_text


class DemoForm(forms.Form):
    due = forms.CharField(label="Due date")
    advance = forms.CharField(label="Advance", help_text="Leave empty.")
    f = forms.ChoiceField(
        label="Pick",
        widget=forms.RadioSelect,
        choices=[("a", "A"), ("b", "B")],
        initial="b",
    )
    place = forms.ChoiceField(
        label="Place",
        widget=forms.RadioSelect,
        choices=[("s", "Suggested"), ("n", "Next")],
        initial="s",
    )
    on = forms.BooleanField(label="Switch me", required=False, initial=True)
    off = forms.BooleanField(
        label="Off row", required=False, disabled=True, help_text="Add a phone."
    )


class ErrForm(forms.Form):
    customer = forms.CharField(
        label="Customer", error_messages={"required": "Choose a customer."}
    )
    estimate = forms.CharField(label="Estimate", help_text="Usually 3h.")


class NonFieldForm(forms.Form):
    def clean(self):
        raise ValidationError("Pick a date after today.")


def render(source, **ctx):
    return Template("{% load ui %}" + source).render(Context(ctx))


def input_tag(html):
    return re.search(r"<input[^>]*>", html).group(0)


def test_describedby_combinations():
    assert describedby("id_x", hint=False, error=False) == ""
    assert describedby("id_x", hint=True, error=False) == "id_x_hint"
    assert describedby("id_x", hint=False, error=True) == "id_x_error"
    assert describedby("id_x", hint=True, error=True) == "id_x_error id_x_hint"


def test_error_summary_text_singular_plural():
    assert error_summary_text(1, "save") == "1 thing needs fixing before you can save."
    assert error_summary_text(2, "save") == "2 things need fixing before you can save."


def test_choice_options():
    form = DemoForm()
    options = choice_options(form["f"], {"a": "Note A"})
    assert [o["id"] for o in options] == ["id_f_0", "id_f_1"]
    assert [o["label"] for o in options] == ["A", "B"]
    assert [o["checked"] for o in options] == [False, True]
    assert [o["note"] for o in options] == ["Note A", ""]
    assert options[0]["name"] == "f" and options[1]["value"] == "b"


def test_field_tag_plain():
    html = render("{% field form.due %}", form=DemoForm())
    assert "aria-describedby" not in html
    assert 'class="field__input"' in html
    assert re.search(r'<label[^>]*for="id_due"[^>]*>Due date</label>', html)


def test_field_tag_hint():
    html = render("{% field form.advance %}", form=DemoForm())
    assert 'aria-describedby="id_advance_hint"' in html
    assert 'id="id_advance_hint"' in html


def test_field_tag_error():
    form = ErrForm(data={}, prefix="err")
    html = render("{% field form.estimate %}{% field form.customer %}", form=form)
    assert "field--error" in html
    assert 'aria-invalid="true"' in html
    assert 'id="err-customer_error"' not in html
    assert 'id="id_err-customer_error"' in html
    assert "Choose a customer." in html
    tags = re.findall(r"<input[^>]*>", html)
    assert len(tags) == 2
    for tag in tags:
        assert tag.count("aria-describedby") == 1
    assert 'aria-describedby="id_err-estimate_error id_err-estimate_hint"' in html


def test_error_summary_tag():
    src = '{% error_summary form "create this order" %}'
    html = render(src, form=ErrForm(data={}))
    assert 'role="alert"' in html
    assert "2 things need fixing before you can create this order." in html
    assert (
        render(src, form=ErrForm(data={"customer": "a", "estimate": "b"})).strip() == ""
    )
    assert render(src, form=ErrForm()).strip() == ""
    html = render(src, form=NonFieldForm(data={}))
    assert "<li>Pick a date after today.</li>" in html
    assert "1 thing needs fixing" in html


def test_segmented_tag():
    html = render("{% segmented form.f %}", form=DemoForm())
    assert 'class="seg"' in html and "<legend" in html
    assert html.count('type="radio"') == 2
    assert len(re.findall(r"\schecked", html)) == 1


def test_radio_rows_tag():
    notes = {"s": "After the chudidar"}
    html = render("{% radio_rows form.place notes %}", form=DemoForm(), notes=notes)
    assert 'aria-describedby="id_place_0_note"' in input_tag(html)
    assert "After the chudidar" in html
    assert len(re.findall(r"\schecked", html)) == 1


def test_switch_tag():
    html = render("{% switch form.on %}", form=DemoForm())
    tag = input_tag(html)
    assert 'role="switch"' in tag and 'type="checkbox"' in tag
    assert 'class="switch"' in tag and " checked" in tag
    assert 'for="id_on"' in html and 'id="id_on"' in tag


def test_checkbox_row_disabled():
    html = render("{% checkbox_row form.off %}", form=DemoForm())
    assert "disabled" in input_tag(html)
    assert "check-row--disabled" in html
    plain = render("{% checkbox_row form.on %}", form=DemoForm())
    assert "check-row--disabled" not in plain


def test_filter_chips_tag():
    chips = [
        {"label": "Open", "count": 12, "url": "?a", "selected": True},
        {"label": "Free", "count": None, "url": "?b", "selected": False},
    ]
    html = render('{% filter_chips chips "Filter orders" %}', chips=chips)
    assert html.count('aria-current="true"') == 1
    assert "(12)" in html
    assert html.count("(") == 1
    assert 'aria-label="Filter orders"' in html


@pytest.mark.parametrize("name", ["field", "error_summary", "segmented"])
def test_partials_have_no_js_hooks(name):
    from pathlib import Path

    text = (Path("templates/components") / f"{name}.html").read_text()
    assert not re.search(r"x-|hx-|<script", text)


class RequiredControlsForm(forms.Form):
    pays = forms.ChoiceField(
        label="Who pays",
        widget=forms.RadioSelect,
        choices=[("a", "A"), ("b", "B")],
        error_messages={"required": "Pick who pays."},
    )
    on = forms.BooleanField(
        label="Switch", help_text="Hint.", error_messages={"required": "Turn it on."}
    )


@pytest.mark.parametrize("tag", ["segmented", "radio_rows"])
def test_choice_tags_render_errors(tag):
    html = render("{% " + tag + " form.pays %}", form=RequiredControlsForm(data={}))
    assert '<p class="field__error" id="id_pays_error">Pick who pays.</p>' in html
    inputs = re.findall(r"<input[^>]*>", html)
    assert len(inputs) == 2
    for tag_html in inputs:
        assert 'aria-invalid="true"' in tag_html
        assert tag_html.count("aria-describedby") == 1
        assert 'aria-describedby="id_pays_error"' in tag_html


@pytest.mark.parametrize("tag", ["segmented", "radio_rows"])
def test_choice_tags_required_attribute(tag):
    html = render("{% " + tag + " form.pays %}", form=RequiredControlsForm())
    inputs = re.findall(r"<input[^>]*>", html)
    assert len(inputs) == 2
    assert all(" required" in i for i in inputs)


@pytest.mark.parametrize("tag", ["segmented", "radio_rows"])
def test_choice_tags_no_required_when_opted_out(tag):
    form = RequiredControlsForm()
    form.use_required_attribute = False
    html = render("{% " + tag + " form.pays %}", form=form)
    assert " required" not in html


def test_radio_rows_error_before_note():
    html = render(
        "{% radio_rows form.pays notes %}",
        form=RequiredControlsForm(data={}),
        notes={"a": "Note A"},
    )
    assert 'aria-describedby="id_pays_error id_pays_0_note"' in html


@pytest.mark.parametrize("tag", ["switch", "checkbox_row"])
def test_toggle_tags_render_errors(tag):
    html = render("{% " + tag + " form.on %}", form=RequiredControlsForm(data={}))
    assert '<p class="field__error" id="id_on_error">Turn it on.</p>' in html
    tag_html = input_tag(html)
    assert 'aria-invalid="true"' in tag_html
    assert tag_html.count("aria-describedby") == 1
    assert 'aria-describedby="id_on_error id_on_hint"' in tag_html
