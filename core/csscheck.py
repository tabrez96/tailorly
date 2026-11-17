"""Find colour literals in CSS and templates, and compare CSS blocks."""

import re

HEX = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b")
FUNC = re.compile(r"\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(", re.I)
NAMED = {
    "aliceblue",
    "antiquewhite",
    "aqua",
    "aquamarine",
    "azure",
    "beige",
    "bisque",
    "black",
    "blanchedalmond",
    "blue",
    "blueviolet",
    "brown",
    "burlywood",
    "cadetblue",
    "chartreuse",
    "chocolate",
    "coral",
    "cornflowerblue",
    "cornsilk",
    "crimson",
    "cyan",
    "darkblue",
    "darkcyan",
    "darkgoldenrod",
    "darkgray",
    "darkgreen",
    "darkgrey",
    "darkkhaki",
    "darkmagenta",
    "darkolivegreen",
    "darkorange",
    "darkorchid",
    "darkred",
    "darksalmon",
    "darkseagreen",
    "darkslateblue",
    "darkslategray",
    "darkslategrey",
    "darkturquoise",
    "darkviolet",
    "deeppink",
    "deepskyblue",
    "dimgray",
    "dimgrey",
    "dodgerblue",
    "firebrick",
    "floralwhite",
    "forestgreen",
    "fuchsia",
    "gainsboro",
    "ghostwhite",
    "gold",
    "goldenrod",
    "gray",
    "green",
    "greenyellow",
    "grey",
    "honeydew",
    "hotpink",
    "indianred",
    "indigo",
    "ivory",
    "khaki",
    "lavender",
    "lavenderblush",
    "lawngreen",
    "lemonchiffon",
    "lightblue",
    "lightcoral",
    "lightcyan",
    "lightgoldenrodyellow",
    "lightgray",
    "lightgreen",
    "lightgrey",
    "lightpink",
    "lightsalmon",
    "lightseagreen",
    "lightskyblue",
    "lightslategray",
    "lightslategrey",
    "lightsteelblue",
    "lightyellow",
    "lime",
    "limegreen",
    "linen",
    "magenta",
    "maroon",
    "mediumaquamarine",
    "mediumblue",
    "mediumorchid",
    "mediumpurple",
    "mediumseagreen",
    "mediumslateblue",
    "mediumspringgreen",
    "mediumturquoise",
    "mediumvioletred",
    "midnightblue",
    "mintcream",
    "mistyrose",
    "moccasin",
    "navajowhite",
    "navy",
    "oldlace",
    "olive",
    "olivedrab",
    "orange",
    "orangered",
    "orchid",
    "palegoldenrod",
    "palegreen",
    "paleturquoise",
    "palevioletred",
    "papayawhip",
    "peachpuff",
    "peru",
    "pink",
    "plum",
    "powderblue",
    "purple",
    "rebeccapurple",
    "red",
    "rosybrown",
    "royalblue",
    "saddlebrown",
    "salmon",
    "sandybrown",
    "seagreen",
    "seashell",
    "sienna",
    "silver",
    "skyblue",
    "slateblue",
    "slategray",
    "slategrey",
    "snow",
    "springgreen",
    "steelblue",
    "tan",
    "teal",
    "thistle",
    "tomato",
    "turquoise",
    "violet",
    "wheat",
    "white",
    "whitesmoke",
    "yellow",
    "yellowgreen",
}
NAMED_WORD = re.compile(
    r"(?<![\w-])(" + "|".join(sorted(NAMED, key=len, reverse=True)) + r")(?![\w-])",
    re.I,
)

COMMENT = re.compile(r"/\*.*?\*/", re.S)
DECLARATION_VALUE = re.compile(r":[^;{}]*")
STYLE_ATTR = re.compile(
    r"""(?<![\w-])style\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))""", re.I
)
STYLE_BLOCK = re.compile(r"<style\b[^>]*>(.*?)</style>", re.I | re.S)
COLOUR_ATTR = re.compile(
    r"""(?<![\w-])(?:fill|stroke|stop-color|color)\s*=\s*"""
    r"""(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))""",
    re.I,
)


def colour_literals(value: str) -> list[str]:
    """Colour literals in a CSS value or CSS text (comments removed first)."""
    text = COMMENT.sub("", value)
    found = HEX.findall(text)
    found += [m.group(0) for m in FUNC.finditer(text)]
    for declaration in DECLARATION_VALUE.findall(text):
        found += [m.group(1) for m in NAMED_WORD.finditer(declaration)]
    return found


def value_colour_literals(value: str) -> list[str]:
    """Colour literals in a bare declaration value, e.g. `red` or `var(--ink, red)`."""
    return colour_literals("x:" + value)


def template_colour_literals(html: str) -> list[str]:
    """Colour literals in a template's style contexts.

    Style contexts are style="..." attributes, <style> blocks, and fill= / stroke= /
    stop-color= / color= attributes. Other text (href="#add") is ignored.
    """
    found: list[str] = []
    for match in STYLE_ATTR.finditer(html):
        found += colour_literals(
            match.group(1) or match.group(2) or match.group(3) or ""
        )
    for match in STYLE_BLOCK.finditer(html):
        found += colour_literals(match.group(1))
    for match in COLOUR_ATTR.finditer(html):
        # Attribute values are bare colours, so test them as a declaration value.
        found += value_colour_literals(
            match.group(1) or match.group(2) or match.group(3) or ""
        )
    return found


def declarations(css: str, selector: str) -> dict[str, str]:
    """Declarations of the first block whose selector is exactly `selector`, as
    {property: value} with whitespace collapsed. Raises KeyError if not found."""
    text = COMMENT.sub("", css)
    pattern = r"(?:^|[{};])\s*" + re.escape(selector) + r"\s*\{([^{}]*)\}"
    match = re.search(pattern, text)
    if not match:
        raise KeyError(selector)
    result: dict[str, str] = {}
    for item in match.group(1).split(";"):
        name, sep, value = item.partition(":")
        if sep:
            result[name.strip()] = " ".join(value.split())
    return result
