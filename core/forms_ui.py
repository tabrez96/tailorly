"""Pure helpers behind the form control partials."""


def describedby(auto_id: str, *, hint: bool, error: bool) -> str:
    """Ids for aria-describedby, error first then hint; "" when neither."""
    ids = []
    if error:
        ids.append(f"{auto_id}_error")
    if hint:
        ids.append(f"{auto_id}_hint")
    return " ".join(ids)


def error_summary_text(count: int, action: str) -> str:
    """'2 things need fixing before you can create this order.'"""
    noun = "thing needs" if count == 1 else "things need"
    return f"{count} {noun} fixing before you can {action}."


def choice_options(field, notes: dict | None = None) -> list[dict]:
    """One dict per choice of a BoundField with a RadioSelect widget."""
    notes = notes or {}
    return [
        {
            "id": w.id_for_label,
            "name": w.data["name"],
            "value": w.data["value"],
            "label": w.choice_label,
            "note": notes.get(w.data["value"], ""),
            "checked": w.data["selected"],
            "required": bool(w.data["attrs"].get("required")),
        }
        for w in field.subwidgets
    ]
