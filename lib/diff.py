"""Core diff computation and caching — translation status analysis."""

import json
import sys
import time
from datetime import datetime, timezone

from lib.project import kernel_dir, en_doc_dir, zh_cn_dir, diff_cache_path
from lib.git_helpers import (
    build_zh_commit_map, english_commits_since_batch, latest_commit_batch,
    last_commit_for_file, commits_between, diff_between,
    head_oneline, docs_next_head,
)


def get_status(subdir=None, on_progress=None):
    """Compute translation status for all files (or a subdirectory).

    *on_progress(phase, done, total, filename)* is called during slow
    operations so callers can display progress.
    """
    kd = kernel_dir()
    en_base = en_doc_dir()
    zh_base = zh_cn_dir()

    # Count English files
    en_files = []
    for rst in sorted(en_base.rglob("*.rst")):
        rel = rst.relative_to(en_base)
        if str(rel).startswith("translations/"):
            continue
        if subdir and not str(rel).startswith(subdir.rstrip("/") + "/"):
            continue
        en_files.append(str(rel))

    # Count and map Chinese files
    zh_file_set = set()
    file_map = build_zh_commit_map()

    candidates = []
    up_to_date = []

    if zh_base.is_dir():
        for zh_file in sorted(zh_base.rglob("*.rst")):
            rel = zh_file.relative_to(zh_base)
            rel_str = str(rel)
            if subdir and not rel_str.startswith(subdir.rstrip("/") + "/"):
                continue
            zh_file_set.add(rel_str)

            en_file = en_base / rel
            zh_rel = str(zh_file.relative_to(kd))
            entry = file_map.get(zh_rel)

            if not en_file.exists() or not entry:
                up_to_date.append({"file": rel_str, "zh_date": entry[1] if entry else None})
                continue

            zh_commit, zh_date = entry
            en_rel = str(en_file.relative_to(kd))
            candidates.append((rel_str, en_rel, zh_commit, zh_date))

    # Phase 1: batch check commits (parallel)
    work_items = [(en_rel, zh_commit) for _, en_rel, zh_commit, _ in candidates]

    def _batch_done(done, total, en_rel):
        if on_progress:
            on_progress("检查英文变更", done, total, en_rel)

    counts = english_commits_since_batch(
        work_items, on_done=_batch_done) if work_items else []

    # Phase 2: get latest English commit for each file (parallel)
    en_paths = [en_rel for _, en_rel, _, _ in candidates]

    def _en_head_done(done, total, path):
        if on_progress:
            on_progress("获取英文最新版本", done, total, path)

    en_heads = latest_commit_batch(
        en_paths, on_done=_en_head_done) if en_paths else []

    results = []
    for (rel_str, _, zh_commit, zh_date), count, en_head in zip(candidates, counts, en_heads):
        # If latest non-merge commit == base commit, file is up-to-date
        # regardless of what rev-list says (avoids merge topology false positives)
        if en_head and en_head[:12] == zh_commit[:12]:
            count = 0
        results.append({
            "file": rel_str,
            "status": "outdated" if count > 0 else "up_to_date",
            "commits_behind": count,
            "zh_last_updated": zh_date,
            "en_base_commit": zh_commit[:12],
            "en_head_commit": en_head[:12] if en_head else None,
        })

    for item in up_to_date:
        results.append({
            "file": item["file"],
            "status": "up_to_date",
            "commits_behind": 0,
            "zh_last_updated": item["zh_date"],
            "en_base_commit": None,
            "en_head_commit": None,
        })

    # Missing files
    missing = [f for f in en_files if f not in zh_file_set]
    outdated_count = sum(1 for r in results if r["status"] == "outdated")

    return {
        "head": head_oneline(),
        "total_english": len(en_files),
        "total_zh": len(zh_file_set),
        "coverage": round(len(zh_file_set) / len(en_files) * 100, 1) if en_files else 0,
        "outdated_count": outdated_count,
        "missing_count": len(missing),
        "files": sorted(results, key=lambda x: -(x["commits_behind"] or 0)),
        "missing": missing,
    }


def get_detail(file_path):
    """Get detailed diff info for a single file."""
    kd = kernel_dir()
    en_rel = f"Documentation/{file_path}"
    zh_rel = f"Documentation/translations/zh_CN/{file_path}"

    zh_full = kd / zh_rel
    en_full = kd / en_rel

    if not en_full.is_file():
        return {"error": f"英文文件不存在: {en_rel}"}

    if not zh_full.is_file():
        return {"error": f"此文件尚未翻译", "file": file_path, "translated": False}

    zh_commit = last_commit_for_file(zh_rel, fmt="%H")
    zh_date = last_commit_for_file(zh_rel, fmt="%as")
    zh_subject = last_commit_for_file(zh_rel, fmt="%s")

    if not zh_commit:
        return {"file": file_path, "translated": True, "en_base_commit": None,
                "changes": [], "diff": ""}

    changes = commits_between(zh_commit, "HEAD", path=en_rel)
    diff = diff_between(zh_commit, "HEAD", path=en_rel) if changes else ""

    return {
        "file": file_path,
        "translated": True,
        "en_base_commit": zh_commit[:12],
        "zh_date": zh_date,
        "zh_subject": zh_subject,
        "changes_count": len(changes),
        "changes": changes,
        "diff": diff,
    }


# ── Cache ───────────────────────────────────────────────────────────

def read_diff_cache() -> dict | None:
    """Read cache; return data if HEAD matches, else None."""
    cp = diff_cache_path()
    if not cp.is_file():
        return None
    try:
        cache = json.loads(cp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if cache.get("head") == docs_next_head():
        return cache["data"]
    return None


def write_diff_cache(data: dict) -> None:
    """Write cache keyed to current docs-next HEAD."""
    cp = diff_cache_path()
    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_text(json.dumps({
        "head": docs_next_head(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }, ensure_ascii=False, indent=2), encoding="utf-8")


class _Progress:
    """Stderr progress reporter for get_status() phases."""

    def __init__(self):
        self._phase = ""
        self._phase_total = 0
        self._phase_start = 0.0
        self._is_tty = hasattr(sys.stderr, "isatty") and sys.stderr.isatty()

    def _overwrite(self, text: str, newline: bool = False) -> None:
        """Write text to stderr, overwriting the current line on a tty."""
        if self._is_tty:
            sys.stderr.write(f"\r{text}\033[K")
        else:
            sys.stderr.write(text)
        if newline:
            sys.stderr.write("\n")
        sys.stderr.flush()

    def __call__(self, phase, done, total, filename=""):
        if phase != self._phase:
            if self._phase:
                elapsed = time.monotonic() - self._phase_start
                self._overwrite(
                    f"{self._phase} [{self._phase_total}/{self._phase_total}]"
                    f" {elapsed:.1f}s", newline=True)
            self._phase = phase
            self._phase_total = total
            self._phase_start = time.monotonic()
        else:
            self._phase_total = total

        elapsed = time.monotonic() - self._phase_start
        if done >= 3:
            eta = elapsed / done * (total - done)
            eta_str = f" 剩余 {eta:.0f}s"
        else:
            eta_str = ""

        if self._is_tty:
            self._overwrite(f"{phase} [{done}/{total}] {filename}{eta_str}")

    def finish(self):
        if self._phase:
            elapsed = time.monotonic() - self._phase_start
            self._overwrite(
                f"{self._phase} [{self._phase_total}/{self._phase_total}]"
                f" 完成 {elapsed:.1f}s", newline=True)


def _filter_by_subdir(data: dict, subdir: str) -> dict:
    """Filter cached full-scan data to a subdirectory."""
    prefix = subdir.rstrip("/") + "/"
    files = [f for f in data["files"] if f["file"].startswith(prefix)]
    missing = [f for f in data["missing"] if f.startswith(prefix)]
    zh_count = sum(1 for f in files)
    en_count = zh_count + len(missing)
    outdated_count = sum(1 for f in files if f["status"] == "outdated")
    return {
        "head": data["head"],
        "total_english": en_count,
        "total_zh": zh_count,
        "coverage": round(zh_count / en_count * 100, 1) if en_count else 0,
        "outdated_count": outdated_count,
        "missing_count": len(missing),
        "files": files,
        "missing": missing,
    }


def get_status_cached(subdir=None) -> dict:
    """Return diff status, using cache when available."""
    cached = read_diff_cache()
    if cached is not None:
        return _filter_by_subdir(cached, subdir) if subdir else cached
    progress = _Progress()
    data = get_status(on_progress=progress)
    progress.finish()
    write_diff_cache(data)
    return _filter_by_subdir(data, subdir) if subdir else data
