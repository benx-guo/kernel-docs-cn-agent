"""Glossary loader for config/glossary.txt."""

from __future__ import annotations

from pathlib import Path


def load_glossary(path: str | Path) -> list[dict]:
    """Parse the glossary file and return a list of term entries.

    Each entry: ``{"en": str, "zh": str, "notes": str}``.
    Lines starting with ``#`` or blank lines are skipped.
    """
    entries: list[dict] = []
    p = Path(path)
    if not p.is_file():
        return entries
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [s.strip() for s in line.split("|")]
        if len(parts) < 2:
            continue
        entries.append({
            "en": parts[0],
            "zh": parts[1],
            "notes": parts[2] if len(parts) > 2 else "",
        })
    return entries


def lookup(glossary: list[dict], term: str) -> dict | None:
    """Case-insensitive lookup by English term.

    Returns the first matching entry dict, or None.
    """
    term_lower = term.lower()
    for entry in glossary:
        if entry["en"].lower() == term_lower:
            return entry
    return None


def no_translate_terms(glossary: list[dict]) -> list[str]:
    """Return English terms marked as '不翻译' (do not translate)."""
    return [e["en"] for e in glossary if "不翻译" in e.get("notes", "")]
