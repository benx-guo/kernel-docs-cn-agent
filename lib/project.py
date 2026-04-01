"""Project root detection and path constants."""

import os
from pathlib import Path

# Sentinel file that marks the project root
_SENTINEL = os.environ.get("KT_SENTINEL", "docs/guide.md")


def find_project_root(start: str | Path | None = None) -> Path:
    """Walk upward from *start* (default: this file) until sentinel is found.

    Returns the resolved project root Path.
    Raises FileNotFoundError if the root cannot be determined.
    """
    if start is None:
        start = Path(__file__).resolve().parent  # lib/
    current = Path(start).resolve()
    while True:
        if (current / _SENTINEL).is_file():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    raise FileNotFoundError(
        f"Cannot find project root (no {_SENTINEL} in ancestor directories of {start})"
    )


# Lazily resolved project root — import once, use everywhere
_root: Path | None = None


def root() -> Path:
    """Return the cached project root."""
    global _root
    if _root is None:
        _root = find_project_root()
    return _root


# ── Derived path helpers ────────────────────────────────────────────

def kernel_dir() -> Path:
    """Return <root>/linux/ — the cloned kernel repository."""
    return root() / "linux"


def config_dir() -> Path:
    return root() / "config"


def outgoing_dir() -> Path:
    return root() / "outgoing"


def scripts_dir() -> Path:
    return root() / "scripts"


def docs_dir() -> Path:
    return root() / "docs"


def data_dir() -> Path:
    return root() / "data"


def glossary_path() -> Path:
    return config_dir() / "glossary.txt"


def workflow_state_path() -> Path:
    return data_dir() / "workflow-state.json"


def series_state_path() -> Path:
    return data_dir() / "series-state.json"


def zh_cn_dir() -> Path:
    """Return the zh_CN translation base directory inside the kernel tree."""
    return kernel_dir() / "Documentation" / "translations" / "zh_CN"


def en_doc_dir() -> Path:
    """Return the English Documentation base directory inside the kernel tree."""
    return kernel_dir() / "Documentation"
