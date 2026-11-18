def normalize_phone(raw: str) -> str:
    """Digits only, without the +91 / 0 prefix: '+91 98450-12345' -> '9845012345'."""
    digits = "".join(c for c in raw if c.isascii() and c.isdigit())
    if len(digits) == 12 and digits.startswith("91"):
        return digits[2:]
    if len(digits) == 11 and digits.startswith("0"):
        return digits[1:]
    return digits


def is_valid_phone(digits: str) -> bool:
    return len(digits) == 10 and digits.isascii() and digits.isdigit()
