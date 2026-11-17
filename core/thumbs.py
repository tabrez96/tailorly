"""Photo thumbnail sizes, alt text and count badge."""

SIZES = {"sm": 52, "md": 76, "lg": 170}


def photo_alt(name: str, index: int, count: int) -> str:
    return f"{name}, photo {index} of {count}"


def count_badge(index: int, count: int) -> str:
    """ "1/3" when an item has more than one photo, else ""."""
    return f"{index}/{count}" if count > 1 else ""


def thumb_context(
    name: str, src: str | None = None, count: int = 0, size: str = "sm"
) -> dict:
    if size not in SIZES:
        raise ValueError(f"Unknown thumbnail size: {size}")
    if not src:
        return {"size": size, "src": None, "alt": f"{name}, no photo", "badge": ""}
    count = max(count, 1)
    return {
        "size": size,
        "src": src,
        "alt": photo_alt(name, 1, count),
        "badge": count_badge(1, count),
    }
