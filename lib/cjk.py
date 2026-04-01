"""CJK display-width utilities."""

import unicodedata


def display_width(text: str) -> int:
    """Return the display width of *text* in terminal columns.

    CJK fullwidth/wide characters count as 2; everything else counts as 1.
    """
    w = 0
    for ch in text:
        if unicodedata.east_asian_width(ch) in ("W", "F"):
            w += 2
        else:
            w += 1
    return w


def check_line_widths(filepath: str, max_width: int = 80) -> list[dict]:
    """Check every line in *filepath* for display-width violations.

    Returns a list of ``{"line": int, "width": int, "text": str}`` dicts
    for lines exceeding *max_width*.
    """
    violations = []
    with open(filepath, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            stripped = line.rstrip("\n")
            w = display_width(stripped)
            if w > max_width:
                violations.append({"line": lineno, "width": w, "text": stripped})
    return violations
