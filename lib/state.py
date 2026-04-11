"""JSON state file I/O for workflow-state and series-state."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


# ── Generic helpers ─────────────────────────────────────────────────

def _load(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ── Workflow state ──────────────────────────────────────────────────

def load_workflow_state(path: str | Path) -> dict:
    """Load workflow-state.json. Returns ``{"version": 1, "files": {...}}``."""
    data = _load(Path(path))
    if not data:
        return {"version": 1, "files": {}}
    return data


def get_workflow_stage(path: str | Path, file_key: str) -> int:
    """Return the current stage (0 if absent) for *file_key*."""
    data = load_workflow_state(path)
    entry = data.get("files", {}).get(file_key)
    return entry["stage"] if entry else 0


def set_workflow_stage(path: str | Path, file_key: str, stage: int) -> None:
    """Write a stage update for *file_key*."""
    p = Path(path)
    data = load_workflow_state(p)
    data.setdefault("files", {})[file_key] = {
        "stage": stage,
        "updated_at": _now_iso(),
    }
    _save(p, data)


def list_in_progress_files(path: str | Path) -> list[tuple[str, int]]:
    """Return ``[(file_key, stage), ...]`` for files with 1 <= stage <= 11."""
    data = load_workflow_state(path)
    result = []
    for fk, info in data.get("files", {}).items():
        s = info.get("stage", 0)
        if 1 <= s <= 11:
            result.append((fk, s))
    result.sort(key=lambda x: x[1])
    return result


# ── Series state ────────────────────────────────────────────────────

def load_series_state(path: str | Path) -> dict:
    """Load series-state.json. Returns ``{"version": 1, "series": {...}}``."""
    data = _load(Path(path))
    if not data:
        return {"version": 1, "series": {}}
    return data


def save_series_state(path: str | Path, data: dict) -> None:
    _save(Path(path), data)


def get_series(path: str | Path, series_id: str) -> dict | None:
    """Return a single series dict, or None."""
    data = load_series_state(path)
    return data.get("series", {}).get(series_id)


def list_active_series(path: str | Path) -> list[tuple[str, dict]]:
    """Return ``[(id, series_dict), ...]`` for non-merged series."""
    data = load_series_state(path)
    result = []
    for sid, s in data.get("series", {}).items():
        if s.get("phase") != "merged":
            result.append((sid, s))
    return result


def create_series(
    path: str | Path,
    series_id: str,
    subject: str,
    files: list[str],
    commits: list[str],
    branch: str | None = None,
) -> None:
    """Create a new series entry in pending internal_review state."""
    p = Path(path)
    data = load_series_state(p)
    entry: dict = {
        "subject": subject,
        "files": files,
        "commits": commits,
        "phase": "internal_review",
        "phases": {
            "internal_review": {"status": "pending", "rounds": []},
            "upstream": {"status": "pending", "rounds": []},
        },
    }
    if branch:
        entry["branch"] = branch
    data.setdefault("series", {})[series_id] = entry
    _save(p, data)


def delete_series(path: str | Path, series_id: str) -> bool:
    """Remove a series entry. Returns True if it existed."""
    p = Path(path)
    data = load_series_state(p)
    series = data.get("series", {})
    if series_id not in series:
        return False
    del series[series_id]
    _save(p, data)
    return True


def add_round(
    path: str | Path,
    series_id: str,
    cover_message_id: str = "",
    tip: str = "",
) -> int:
    """Append a new round to the current phase and return its version number."""
    p = Path(path)
    data = load_series_state(p)
    s = data["series"][series_id]
    phase_data = s["phases"][s["phase"]]
    phase_data["status"] = "sent"
    version = len(phase_data["rounds"]) + 1

    per_patch: dict[str, dict] = {}
    for i, f in enumerate(s["files"], 1):
        per_patch[str(i)] = {
            "file": f,
            "status": "no_feedback",
            "tags": [],
            "action_items": [],
        }

    round_entry: dict = {
        "version": version,
        "sent_at": _today(),
        "cover_message_id": cover_message_id,
        "per_patch": per_patch,
    }
    if tip:
        round_entry["tip"] = tip
    phase_data["rounds"].append(round_entry)
    _save(p, data)
    return version


def update_series_field(
    path: str | Path,
    series_id: str,
    **fields: object,
) -> None:
    """Update top-level fields on a series (e.g. phase, commits)."""
    p = Path(path)
    data = load_series_state(p)
    s = data["series"][series_id]
    s.update(fields)
    _save(p, data)


def update_phase_status(
    path: str | Path,
    series_id: str,
    phase: str,
    status: str,
) -> None:
    """Set the status of a specific phase."""
    p = Path(path)
    data = load_series_state(p)
    data["series"][series_id]["phases"][phase]["status"] = status
    _save(p, data)
