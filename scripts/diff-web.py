#!/usr/bin/env python3
"""Translation Diff Viewer — full-status translation dashboard.

A zero-dependency web tool for viewing translation status across all
documentation files: outdated, missing, up-to-date, and in-progress.

Usage:
    python3 scripts/diff-web.py [--port PORT]
"""

import concurrent.futures
from datetime import datetime, timezone
import http.server
import json
import mimetypes
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Make lib/ importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import project as _proj
from lib import state as _state
from lib import git_helpers as _git

try:
    from docutils.core import publish_parts
    HAS_DOCUTILS = True
except ImportError:
    HAS_DOCUTILS = False

KERNEL_DIR = _proj.kernel_dir()
WORKFLOW_STATE_FILE = _proj.workflow_state_path()

DEFAULT_PORT = 8080

# Workflow stages: id, label (Chinese), abbreviation
WORKFLOW_STAGES = [
    {"id": 1, "label": "检查是否需要翻译", "abbr": "CHK"},
    {"id": 2, "label": "翻译进行中", "abbr": "TL"},
    {"id": 3, "label": "质检通过", "abbr": "QA"},
    {"id": 4, "label": "Patch 制作完成", "abbr": "PAT"},
    {"id": 5, "label": "邮件-自测", "abbr": "E1"},
    {"id": 6, "label": "邮件-内审", "abbr": "E2"},
    {"id": 7, "label": "等待内审回复", "abbr": "W1"},
    {"id": 8, "label": "内审修订中", "abbr": "RV1"},
    {"id": 9, "label": "邮件-邮件列表", "abbr": "E3"},
    {"id": 10, "label": "等待列表回复", "abbr": "W2"},
    {"id": 11, "label": "列表修订中", "abbr": "RV2"},
    {"id": 12, "label": "已归档", "abbr": "ARC"},
]


def _load_workflow_state():
    """Load workflow state from JSON file."""
    return _state.load_workflow_state(WORKFLOW_STATE_FILE).get("files", {})


def _save_workflow_state(files_state):
    """Save workflow state to JSON file."""
    data = {"version": 1, "files": files_state}
    _state._save(WORKFLOW_STATE_FILE, data)


def git(*args):
    """Run a git command in the kernel directory and return stdout."""
    return _git.git_stdout(*args)


def _build_zh_commit_map():
    """Build a map of zh_CN file -> (last_commit_hash, date) in one git pass."""
    return _git.build_zh_commit_map()


def _check_english_commits(args):
    """Check how many English commits exist since a given commit. For thread pool."""
    en_rel, zh_commit = args
    return _git.english_commits_since(en_rel, zh_commit)


def _get_working_tree_files():
    """Detect working tree changes in zh_CN files (unstaged + staged + untracked)."""
    return _git.working_tree_zh_files()


def _find_missing_files(zh_file_set):
    """Find English .rst files that have no zh_CN translation.

    Returns (missing_list, total_english_count).
    """
    en_base = KERNEL_DIR / "Documentation"
    missing = []
    total = 0
    for rst in sorted(en_base.rglob("*.rst")):
        rel = rst.relative_to(en_base)
        rel_str = str(rel)
        # Skip translations directory
        if rel_str.startswith("translations/"):
            continue
        total += 1
        if rel_str not in zh_file_set:
            missing.append(rel_str)
    return missing, total


# ── Cache ───────────────────────────────────────────────────────────────

_git_cache = None  # {"files": [...], "total_english": int}
_git_cache_pid = None


def clear_all_files_cache():
    global _git_cache, _git_cache_pid
    _git_cache = None
    _git_cache_pid = None


def _compute_git_history_data():
    """Compute expensive git history data for all files (cached at process level)."""
    zh_base = KERNEL_DIR / "Documentation" / "translations" / "zh_CN"

    all_files = []
    zh_file_set = set()  # relative paths like "admin-guide/README.rst"

    if zh_base.is_dir():
        # Step 1: Build file -> (commit, date) map in one git log pass
        file_map = _build_zh_commit_map()

        # Step 2: Collect zh_CN .rst files and prepare for commit checking
        candidates = []  # (rel_str, en_rel, zh_commit, zh_date)
        up_to_date_pending = []  # files without English counterparts or git history

        for zh_file in sorted(zh_base.rglob("*.rst")):
            rel_path = zh_file.relative_to(zh_base)
            rel_str = str(rel_path)
            zh_file_set.add(rel_str)

            en_file = KERNEL_DIR / "Documentation" / rel_path
            zh_rel = str(zh_file.relative_to(KERNEL_DIR))

            entry = file_map.get(zh_rel)

            if not en_file.exists():
                # English removed but zh_CN remains
                zh_date = entry[1] if entry else None
                up_to_date_pending.append((rel_str, zh_date))
                continue

            if not entry:
                # zh file exists but no git history (newly added, untracked)
                up_to_date_pending.append((rel_str, None))
                continue

            zh_commit, zh_date = entry
            en_rel = str(en_file.relative_to(KERNEL_DIR))
            candidates.append((rel_str, en_rel, zh_commit, zh_date))

        # Step 3: Check English commit counts in parallel
        work_items = [(en_rel, zh_commit) for _, en_rel, zh_commit, _ in candidates]
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            counts = list(pool.map(_check_english_commits, work_items))

        # Step 4: Classify candidates as outdated or up_to_date
        for (rel_str, _, _, zh_date), count in zip(candidates, counts):
            if count > 0:
                all_files.append({
                    "file": rel_str,
                    "status": "outdated",
                    "commits_behind": count,
                    "zh_last_updated": zh_date,
                })
            else:
                all_files.append({
                    "file": rel_str,
                    "status": "up_to_date",
                    "commits_behind": 0,
                    "zh_last_updated": zh_date,
                })

        # Step 5: Add up_to_date pending files
        for rel_str, zh_date in up_to_date_pending:
            all_files.append({
                "file": rel_str,
                "status": "up_to_date",
                "commits_behind": 0,
                "zh_last_updated": zh_date,
            })

    # Step 6: Find missing files (works even if no zh_CN dir exists)
    missing, total_english = _find_missing_files(zh_file_set)
    for rel_str in missing:
        all_files.append({
            "file": rel_str,
            "status": "missing",
            "commits_behind": None,
            "zh_last_updated": None,
        })

    return {"files": all_files, "total_english": total_english}


def get_all_files():
    """Get all documentation files with their translation status.

    Returns {"files": [...], "summary": {...}} where each file has:
      file, status (outdated/missing/up_to_date), commits_behind, zh_last_updated, working_tree
    """
    global _git_cache, _git_cache_pid

    if _git_cache is not None and _git_cache_pid == os.getpid():
        cached = _git_cache
    else:
        cached = _compute_git_history_data()
        _git_cache = cached
        _git_cache_pid = os.getpid()

    # Working tree status is always fresh (~50ms)
    wt_files = _get_working_tree_files()
    wf_state = _load_workflow_state()
    zh_prefix = "Documentation/translations/zh_CN/"

    # Detect new working tree files not yet in cache (e.g. untracked new translations)
    known_files = {f["file"] for f in cached["files"]}
    new_wt_files = set()
    for wt_path in wt_files:
        if wt_path.startswith(zh_prefix) and wt_path.endswith(".rst"):
            rel = wt_path[len(zh_prefix):]
            if rel not in known_files:
                new_wt_files.add(rel)

    files = []
    summary = {
        "total_english": cached["total_english"],
        "translated": 0,
        "outdated": 0,
        "missing": 0,
        "up_to_date": 0,
        "working_tree": 0,
    }

    for f in cached["files"]:
        # Skip missing entries that now have working tree translations
        if f["status"] == "missing" and f["file"] in new_wt_files:
            continue

        wt_key = zh_prefix + f["file"]
        wt = wt_key in wt_files
        wf_entry = wf_state.get(f["file"])
        wf_stage = wf_entry["stage"] if wf_entry else 0
        entry = {**f, "working_tree": wt, "workflow_stage": wf_stage}
        files.append(entry)

        if f["status"] == "outdated":
            summary["outdated"] += 1
            summary["translated"] += 1
        elif f["status"] == "up_to_date":
            summary["up_to_date"] += 1
            summary["translated"] += 1
        elif f["status"] == "missing":
            summary["missing"] += 1
        if wt:
            summary["working_tree"] += 1

    # Add new working tree files as up_to_date (new translations in progress)
    for rel in sorted(new_wt_files):
        wf_entry = wf_state.get(rel)
        wf_stage = wf_entry["stage"] if wf_entry else 0
        files.append({
            "file": rel,
            "status": "up_to_date",
            "commits_behind": 0,
            "zh_last_updated": None,
            "working_tree": True,
            "workflow_stage": wf_stage,
        })
        summary["working_tree"] += 1
        summary["up_to_date"] += 1
        summary["translated"] += 1

    return {"files": files, "summary": summary}


def get_diff(file_path):
    """Return English and Chinese diffs for a given file path.

    English diff: changes to the English original since the Chinese file
    was last updated.
    Chinese diff: uncommitted working-tree + staged changes to the Chinese file.
    """
    en_rel = f"Documentation/{file_path}"
    zh_rel = f"Documentation/translations/zh_CN/{file_path}"

    zh_last_commit = git("log", "-1", "--format=%H", "--", zh_rel).strip()

    en_diff = ""
    if zh_last_commit:
        en_diff = git("diff", f"{zh_last_commit}..HEAD", "--", en_rel)

    # Working-tree changes (unstaged)
    zh_diff = git("diff", "--", zh_rel)

    # Staged changes
    zh_staged = git("diff", "--cached", "--", zh_rel)
    if zh_staged and zh_diff:
        zh_diff = zh_staged + "\n" + zh_diff
    elif zh_staged:
        zh_diff = zh_staged

    return {"en_diff": en_diff, "zh_diff": zh_diff}


def get_file_content(file_path, side):
    """Read raw file content for English or Chinese side."""
    if ".." in file_path:
        return None

    if side == "en":
        full_path = KERNEL_DIR / "Documentation" / file_path
    elif side == "zh":
        full_path = KERNEL_DIR / "Documentation" / "translations" / "zh_CN" / file_path
    else:
        return None

    # Prevent directory traversal
    try:
        full_path = full_path.resolve()
        if not str(full_path).startswith(str(KERNEL_DIR.resolve())):
            return None
    except (OSError, ValueError):
        return None

    if not full_path.is_file():
        return None

    try:
        return full_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def save_file_content(file_path, content):
    """Save content to a zh_CN translation file. Returns (ok, error_msg)."""
    if ".." in file_path:
        return False, "invalid path: contains '..'"

    zh_base = KERNEL_DIR / "Documentation" / "translations" / "zh_CN"
    full_path = (zh_base / file_path).resolve()

    # Verify the resolved path is under zh_CN
    try:
        if not str(full_path).startswith(str(zh_base.resolve())):
            return False, "path escapes zh_CN directory"
    except (OSError, ValueError):
        return False, "invalid path"

    # Create parent directories if needed
    full_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        full_path.write_text(content, encoding="utf-8")
        return True, None
    except OSError as e:
        return False, str(e)


def render_rst_preview(file_path, side):
    """Render an RST file to HTML using docutils (live preview)."""
    content = get_file_content(file_path, side)
    if content is None:
        return None

    if not HAS_DOCUTILS:
        return ("<html><body><p>Install docutils for live preview: "
                "<code>pip install docutils</code></p></body></html>")

    try:
        parts = publish_parts(
            content,
            writer_name="html",
            settings_overrides={"halt_level": 5, "report_level": 5},
        )
        body = parts["html_body"]
    except Exception as e:
        body = f"<p>Render error: {e}</p>"

    return (
        '<!DOCTYPE html>\n<html><head><meta charset="utf-8">'
        "<style>"
        "body { font-family: sans-serif; padding: 16px; line-height: 1.6; }"
        "pre { background: #f5f5f5; padding: 10px; overflow-x: auto; }"
        "code { background: #f0f0f0; padding: 2px 4px; }"
        "table { border-collapse: collapse; }"
        "td, th { border: 1px solid #ccc; padding: 4px 8px; }"
        "</style></head><body>" + body + "</body></html>"
    )


def parse_diff(raw):
    """Parse a unified diff string into structured hunks for the frontend."""
    if not raw.strip():
        return []

    hunks = []
    current_hunk = None

    for line in raw.splitlines():
        if line.startswith("@@"):
            current_hunk = {"header": line, "lines": []}
            hunks.append(current_hunk)
        elif current_hunk is not None:
            if line.startswith("+"):
                current_hunk["lines"].append({"type": "add", "text": line[1:]})
            elif line.startswith("-"):
                current_hunk["lines"].append({"type": "del", "text": line[1:]})
            else:
                # Context line (starts with space or is empty)
                text = line[1:] if line.startswith(" ") else line
                current_hunk["lines"].append({"type": "ctx", "text": text})

    return hunks


# ── HTML ────────────────────────────────────────────────────────────────

INDEX_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Translation Diff Viewer</title>
<style>
  :root {
    --bg: #1e1e2e;
    --surface: #282840;
    --border: #3e3e5e;
    --text: #cdd6f4;
    --text-dim: #7f849c;
    --add-bg: #1a3a2a;
    --add-text: #a6e3a1;
    --del-bg: #3a1a1a;
    --del-text: #f38ba8;
    --hunk-bg: #2a2a4a;
    --hunk-text: #89b4fa;
    --accent: #89b4fa;
    --sidebar-w: 300px;
    --clr-outdated: #f38ba8;
    --clr-missing: #f9e2af;
    --clr-working: #89dceb;
    --clr-uptodate: #a6e3a1;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    height: 100vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  /* ── Header ── */
  header {
    padding: 10px 16px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    gap: 12px;
    flex-shrink: 0;
  }
  header h1 { font-size: 16px; font-weight: 600; white-space: nowrap; }
  #header-info { font-size: 13px; color: var(--text-dim); }
  .header-btn {
    background: var(--surface); color: var(--text); border: 1px solid var(--border);
    border-radius: 4px; padding: 4px 10px; cursor: pointer; font-size: 12px;
  }
  .header-btn:hover { border-color: var(--accent); }

  /* ── Main layout ── */
  .main {
    flex: 1;
    display: flex;
    overflow: hidden;
  }

  /* ── Sidebar ── */
  .sidebar {
    width: var(--sidebar-w);
    min-width: var(--sidebar-w);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  /* Filter tabs */
  .filter-tabs {
    display: flex;
    padding: 6px 8px;
    gap: 4px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
    flex-wrap: wrap;
  }
  .tab {
    background: transparent;
    color: var(--text-dim);
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 3px 8px;
    font-size: 11px;
    cursor: pointer;
    white-space: nowrap;
    font-family: inherit;
  }
  .tab:hover { background: rgba(137,180,250,.08); }
  .tab.active { background: var(--surface); color: var(--text); border-color: var(--border); }

  /* Summary bar */
  .summary-bar {
    padding: 6px 12px;
    font-size: 11px;
    color: var(--text-dim);
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
  }
  .summary-item { display: flex; align-items: center; gap: 3px; }
  .dot {
    width: 8px; height: 8px; border-radius: 50%;
    display: inline-block; flex-shrink: 0;
  }
  .dot-outdated { background: var(--clr-outdated); }
  .dot-missing { background: var(--clr-missing); }
  .dot-working { background: var(--clr-working); }
  .dot-uptodate { background: var(--clr-uptodate); }

  .sidebar-body {
    flex: 1;
    overflow-y: auto;
    padding: 4px 0;
  }
  .sidebar-loading {
    padding: 24px 12px;
    text-align: center;
    color: var(--text-dim);
    font-size: 13px;
  }

  /* Tree toolbar */
  .tree-toolbar {
    display: flex;
    gap: 4px;
    padding: 4px 8px;
    border-bottom: 1px solid var(--border);
  }
  .tree-toolbar button {
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text-dim);
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 11px;
    cursor: pointer;
  }
  .tree-toolbar button:hover {
    color: var(--text);
    background: rgba(137,180,250,.12);
  }

  /* Directory row */
  .dir-row {
    display: flex;
    align-items: center;
    padding: 3px 8px;
    cursor: pointer;
    font-size: 13px;
    user-select: none;
  }
  .dir-row:hover { background: rgba(137,180,250,.08); }
  .dir-arrow {
    width: 16px;
    text-align: center;
    font-size: 10px;
    color: var(--text-dim);
    flex-shrink: 0;
    transition: transform .15s;
  }
  .dir-arrow.collapsed { transform: rotate(-90deg); }
  .dir-name {
    font-weight: 600;
    margin-left: 2px;
  }
  .dir-count {
    margin-left: auto;
    font-size: 11px;
    color: var(--text-dim);
    background: var(--surface);
    border-radius: 8px;
    padding: 0 6px;
  }

  /* File row */
  .file-row {
    display: flex;
    align-items: center;
    padding: 3px 8px 3px 26px;
    cursor: pointer;
    font-size: 13px;
  }
  .file-row:hover { background: rgba(137,180,250,.08); }
  .file-row.active { background: rgba(137,180,250,.15); }
  .status-icon {
    flex-shrink: 0;
    margin-right: 6px;
    font-size: 12px;
    width: 14px;
    text-align: center;
  }
  .file-name {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .file-badge {
    margin-left: auto;
    font-size: 11px;
    flex-shrink: 0;
    padding-left: 6px;
  }

  /* ── Diff panels ── */
  .diff-area {
    flex: 1;
    display: flex;
    overflow: hidden;
  }
  .diff-panel {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .panel-body {
    flex: 1;
    overflow-y: auto;
  }
  .diff-panel + .diff-panel {
    border-left: 1px solid var(--border);
  }
  .panel-header {
    background: var(--surface);
    padding: 8px 16px;
    font-weight: 600;
    font-size: 13px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .hunk-header {
    background: var(--hunk-bg);
    color: var(--hunk-text);
    padding: 3px 16px;
    font-family: "SF Mono", "Fira Code", "Cascadia Code", monospace;
    font-size: 12px;
    border-top: 1px solid var(--border);
  }
  .diff-line {
    font-family: "SF Mono", "Fira Code", "Cascadia Code", monospace;
    font-size: 13px;
    line-height: 1.5;
    padding: 1px 16px;
    white-space: pre-wrap;
    word-break: break-all;
  }
  .diff-line.add { background: var(--add-bg); color: var(--add-text); }
  .diff-line.del { background: var(--del-bg); color: var(--del-text); }
  .diff-line.ctx { color: var(--text-dim); }
  .no-diff {
    padding: 40px 16px;
    text-align: center;
    color: var(--text-dim);
    font-style: italic;
  }
  .diff-placeholder {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--text-dim);
    font-size: 14px;
  }

  /* ── File content view (non-diff) ── */
  .file-content {
    font-family: "SF Mono", "Fira Code", "Cascadia Code", monospace;
    font-size: 13px;
    line-height: 1.5;
  }
  .content-line {
    padding: 1px 16px 1px 0;
    white-space: pre-wrap;
    word-break: break-all;
    display: flex;
  }
  .line-num {
    display: inline-block;
    min-width: 4em;
    text-align: right;
    padding-right: 12px;
    color: var(--text-dim);
    user-select: none;
    flex-shrink: 0;
  }

  /* ── Editor mode ── */
  .edit-btn {
    background: var(--surface);
    color: var(--accent);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 2px 10px;
    cursor: pointer;
    font-size: 12px;
    font-family: inherit;
    flex-shrink: 0;
  }
  .edit-btn:hover { border-color: var(--accent); background: rgba(137,180,250,.12); }
  .editor-wrap {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .editor-toolbar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    border-bottom: 1px solid var(--border);
    background: var(--surface);
    flex-shrink: 0;
  }
  .save-btn, .back-btn {
    background: var(--surface);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 3px 12px;
    cursor: pointer;
    font-size: 12px;
    font-family: inherit;
  }
  .save-btn { color: var(--add-text); border-color: var(--add-text); }
  .save-btn:hover { background: var(--add-bg); }
  .back-btn:hover { border-color: var(--accent); }
  .save-status { font-size: 12px; color: var(--text-dim); }
  .editor-textarea {
    flex: 1;
    background: var(--bg);
    color: var(--text);
    border: none;
    padding: 8px 16px;
    font-family: "SF Mono", "Fira Code", "Cascadia Code", monospace;
    font-size: 13px;
    line-height: 1.5;
    resize: none;
    outline: none;
    tab-size: 8;
  }

  /* ── HTML Preview panes ── */
  .preview-pane {
    display: flex;
    flex-direction: column;
    height: 40%;
    min-height: 80px;
    flex-shrink: 0;
    border-bottom: 1px solid var(--border);
  }
  .preview-header {
    background: var(--surface);
    padding: 4px 16px;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-dim);
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }
  .preview-iframe {
    flex: 1;
    width: 100%;
    border: none;
    background: #fff;
  }
  .panel-split {
    height: 4px;
    background: var(--border);
    cursor: row-resize;
    flex-shrink: 0;
  }
  .panel-split:hover { background: var(--accent); }

  /* ── Workflow badge (pill in file rows) ── */
  .wf-badge {
    display: inline-block;
    font-size: 10px;
    font-weight: 600;
    padding: 1px 6px;
    border-radius: 8px;
    margin-left: 4px;
    flex-shrink: 0;
    line-height: 1.4;
    cursor: default;
  }
  .wf-stage-1 { background: #45475a; color: #cdd6f4; }  /* CHK  - Surface1 */
  .wf-stage-2 { background: #89b4fa; color: #1e1e2e; }  /* TL   - Blue */
  .wf-stage-3 { background: #a6e3a1; color: #1e1e2e; }  /* DONE - Green */
  .wf-stage-4 { background: #f9e2af; color: #1e1e2e; }  /* PAT  - Yellow */
  .wf-stage-5 { background: #fab387; color: #1e1e2e; }  /* E1   - Peach */
  .wf-stage-6 { background: #f38ba8; color: #1e1e2e; }  /* E2   - Red */
  .wf-stage-7 { background: #cba6f7; color: #1e1e2e; }  /* E3   - Mauve */
  .wf-stage-8 { background: #94e2d5; color: #1e1e2e; }  /* ARC  - Teal */

  /* ── Workflow group headers (In Progress tab) ── */
  .wf-group-header {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px 4px;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-dim);
    border-bottom: 1px solid var(--border);
    margin-top: 4px;
  }
  .wf-group-dot {
    width: 10px; height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  /* ── Workflow select dropdown in zh-header ── */
  .wf-select {
    background: var(--surface);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 12px;
    font-family: inherit;
    cursor: pointer;
    flex-shrink: 0;
    margin-left: 6px;
  }
  .wf-select:hover { border-color: var(--accent); }
  .wf-select:focus { outline: 1px solid var(--accent); outline-offset: -1px; }
</style>
</head>
<body>

<header>
  <h1>Translation Diff Viewer</h1>
  <button class="header-btn" id="refresh-btn">Refresh</button>
  <span id="header-info"></span>
</header>

<div class="main">
  <!-- Sidebar -->
  <div class="sidebar">
    <div class="filter-tabs" id="filter-tabs">
      <button class="tab active" data-filter="outdated">Outdated</button>
      <button class="tab" data-filter="missing">Missing</button>
      <button class="tab" data-filter="working_tree">In Progress</button>
      <button class="tab" data-filter="up_to_date">Up to Date</button>
      <button class="tab" data-filter="all">All</button>
    </div>
    <div class="summary-bar" id="summary-bar"></div>
    <div class="tree-toolbar">
      <button onclick="toggleAllDirs(true)">Expand All</button>
      <button onclick="toggleAllDirs(false)">Collapse All</button>
    </div>
    <div class="sidebar-body" id="tree"></div>
  </div>

  <!-- Diff / content panels -->
  <div class="diff-area" id="diff-area">
    <div class="diff-placeholder" id="placeholder">Select a file from the sidebar to view.</div>
    <div class="diff-panel" id="panel-en" style="display:none">
      <div class="preview-pane" id="en-preview-pane">
        <div class="preview-header">English HTML Preview</div>
        <iframe class="preview-iframe" id="en-preview"></iframe>
      </div>
      <div class="panel-split" id="en-split"></div>
      <div class="panel-header" id="en-header">English</div>
      <div class="panel-body" id="en-body"></div>
    </div>
    <div class="diff-panel" id="panel-zh" style="display:none">
      <div class="preview-pane" id="zh-preview-pane">
        <div class="preview-header">Chinese HTML Preview</div>
        <iframe class="preview-iframe" id="zh-preview"></iframe>
      </div>
      <div class="panel-split" id="zh-split"></div>
      <div class="panel-header" id="zh-header">
        <span id="zh-header-text">Chinese</span>
        <select class="wf-select" id="wf-select" style="display:none"></select>
        <button class="edit-btn" id="edit-btn" style="display:none">Edit</button>
      </div>
      <div class="panel-body" id="zh-body"></div>
      <div class="editor-wrap" id="zh-editor" style="display:none">
        <div class="editor-toolbar">
          <button class="save-btn" id="save-btn">Save</button>
          <button class="back-btn" id="back-btn">Back</button>
          <span class="save-status" id="save-status"></span>
        </div>
        <textarea class="editor-textarea" id="editor-textarea"></textarea>
      </div>
    </div>
  </div>
</div>

<script>
var tree = document.getElementById('tree');
var placeholder = document.getElementById('placeholder');
var panelEn = document.getElementById('panel-en');
var panelZh = document.getElementById('panel-zh');
var enBody = document.getElementById('en-body');
var zhBody = document.getElementById('zh-body');
var enHeader = document.getElementById('en-header');
var zhHeaderText = document.getElementById('zh-header-text');
var editBtn = document.getElementById('edit-btn');
var zhEditor = document.getElementById('zh-editor');
var editorTextarea = document.getElementById('editor-textarea');
var saveBtn = document.getElementById('save-btn');
var backBtn = document.getElementById('back-btn');
var saveStatus = document.getElementById('save-status');
var headerInfo = document.getElementById('header-info');
var summaryBar = document.getElementById('summary-bar');
var enPreview = document.getElementById('en-preview');
var zhPreview = document.getElementById('zh-preview');
var enPreviewPane = document.getElementById('en-preview-pane');
var zhPreviewPane = document.getElementById('zh-preview-pane');
var enSplit = document.getElementById('en-split');
var zhSplit = document.getElementById('zh-split');

var wfSelect = document.getElementById('wf-select');

var allFiles = [];
var summaryData = {};
var activeFileEl = null;
var currentFilter = 'outdated';
var currentFile = null;
var editorMode = false;
var workflowStages = [];

// Stage colors for group dots (matches CSS)
var wfStageColors = {
  1: '#45475a', 2: '#89b4fa', 3: '#a6e3a1', 4: '#f9e2af',
  5: '#fab387', 6: '#f38ba8', 7: '#cba6f7', 8: '#94e2d5'
};

// Load workflow stage definitions
fetch('/api/workflow-stages')
  .then(function(r) { return r.json(); })
  .then(function(data) {
    workflowStages = data.stages || [];
    populateWfSelect();
  });

function populateWfSelect() {
  wfSelect.innerHTML = '<option value="0">-- 工作流 --</option>';
  workflowStages.forEach(function(s) {
    var opt = document.createElement('option');
    opt.value = s.id;
    opt.textContent = s.abbr + ' - ' + s.label;
    wfSelect.appendChild(opt);
  });
}

// (Scroll sync is set up in the heading-based sync section below)

// ── Filter tabs ──
document.getElementById('filter-tabs').addEventListener('click', function(e) {
  var btn = e.target.closest('.tab');
  if (!btn) return;
  document.querySelectorAll('.tab').forEach(function(t) { t.classList.remove('active'); });
  btn.classList.add('active');
  currentFilter = btn.dataset.filter;
  buildTree(getFilteredFiles());
});

function getFilteredFiles() {
  if (currentFilter === 'all') return allFiles;
  if (currentFilter === 'working_tree') return allFiles.filter(function(f) {
    return f.working_tree || (f.workflow_stage >= 1 && f.workflow_stage <= 7);
  });
  return allFiles.filter(function(f) { return f.status === currentFilter; });
}

// ── Summary bar ──
function updateSummary() {
  // Update tab counts
  var inProgressCount = allFiles.filter(function(f) {
    return f.working_tree || (f.workflow_stage >= 1 && f.workflow_stage <= 7);
  }).length;
  var tabs = {
    outdated: summaryData.outdated,
    missing: summaryData.missing,
    working_tree: inProgressCount,
    up_to_date: summaryData.up_to_date,
    all: allFiles.length
  };
  var labels = {
    outdated: 'Outdated',
    missing: 'Missing',
    working_tree: 'In Progress',
    up_to_date: 'Up to Date',
    all: 'All'
  };
  document.querySelectorAll('.tab').forEach(function(t) {
    var f = t.dataset.filter;
    if (tabs[f] !== undefined) {
      t.textContent = labels[f] + ' (' + tabs[f] + ')';
    }
  });

  // Summary bar with colored dots
  summaryBar.innerHTML =
    '<span class="summary-item"><span class="dot dot-outdated"></span>' + summaryData.outdated + ' outdated</span>' +
    '<span class="summary-item"><span class="dot dot-missing"></span>' + summaryData.missing + ' missing</span>' +
    '<span class="summary-item"><span class="dot dot-working"></span>' + summaryData.working_tree + ' in progress</span>' +
    '<span class="summary-item"><span class="dot dot-uptodate"></span>' + summaryData.up_to_date + ' up to date</span>';
}

// ── Create a file row element (reusable) ──
function createFileRow(f) {
  var row = document.createElement('div');
  row.className = 'file-row';
  row.dataset.file = f.file;

  // Status icon
  var icon = document.createElement('span');
  icon.className = 'status-icon';
  if (f.working_tree) {
    icon.textContent = '\\u270E';  // pencil
    icon.style.color = 'var(--clr-working)';
  } else if (f.status === 'outdated') {
    icon.textContent = '\\u25CF';  // filled circle
    icon.style.color = 'var(--clr-outdated)';
  } else if (f.status === 'missing') {
    icon.textContent = '\\u25CF';
    icon.style.color = 'var(--clr-missing)';
  } else {
    icon.textContent = '\\u2713';  // checkmark
    icon.style.color = 'var(--clr-uptodate)';
  }
  row.appendChild(icon);

  // File name
  var fname = document.createElement('span');
  fname.className = 'file-name';
  fname.textContent = f.name || f.file.split('/').pop();
  var tooltip = f.file;
  if (f.zh_last_updated) tooltip += ' (updated: ' + f.zh_last_updated + ')';
  if (f.working_tree) tooltip += ' [working tree changes]';
  fname.title = tooltip;
  row.appendChild(fname);

  // Workflow badge
  if (f.workflow_stage >= 1 && f.workflow_stage <= 8) {
    var stageInfo = workflowStages.find(function(s) { return s.id === f.workflow_stage; });
    if (stageInfo) {
      var wfBadge = document.createElement('span');
      wfBadge.className = 'wf-badge wf-stage-' + f.workflow_stage;
      wfBadge.textContent = stageInfo.abbr;
      wfBadge.title = stageInfo.label;
      row.appendChild(wfBadge);
    }
  }

  // Status badge
  var badge = document.createElement('span');
  badge.className = 'file-badge';
  if (f.status === 'outdated') {
    badge.textContent = f.commits_behind + '\\u2193';
    badge.style.color = 'var(--clr-outdated)';
  } else if (f.status === 'missing') {
    badge.textContent = '--';
    badge.style.color = 'var(--text-dim)';
  } else if (f.working_tree) {
    badge.textContent = '\\u270E';
    badge.style.color = 'var(--clr-working)';
  } else {
    badge.textContent = '\\u2713';
    badge.style.color = 'var(--clr-uptodate)';
  }
  row.appendChild(badge);

  row.addEventListener('click', function() { selectFile(f, row); });
  return row;
}

// ── Build directory tree from flat file list ──
function buildTree(files) {
  // Group by directory
  var dirs = {};
  files.forEach(function(f) {
    var parts = f.file.split('/');
    var name = parts.pop();
    var dir = parts.join('/') || '.';
    if (!dirs[dir]) dirs[dir] = [];
    dirs[dir].push(Object.assign({}, f, { name: name }));
  });

  tree.innerHTML = '';
  if (files.length === 0) {
    tree.innerHTML = '<div class="sidebar-loading">No files in this category.</div>';
    return;
  }

  // Use workflow-grouped view for "In Progress" tab
  if (currentFilter === 'working_tree') {
    buildWorkflowTree(files);
    return;
  }

  var sortedDirs = Object.keys(dirs).sort();

  sortedDirs.forEach(function(dir) {
    var items = dirs[dir].sort(function(a, b) {
      var order = { outdated: 0, missing: 1, up_to_date: 2 };
      var sa = order[a.status] !== undefined ? order[a.status] : 1;
      var sb = order[b.status] !== undefined ? order[b.status] : 1;
      if (sa !== sb) return sa - sb;
      if (a.commits_behind != null && b.commits_behind != null && a.commits_behind !== b.commits_behind)
        return b.commits_behind - a.commits_behind;
      return a.name.localeCompare(b.name);
    });

    var dirEl = document.createElement('div');

    // Directory row
    var dirRow = document.createElement('div');
    dirRow.className = 'dir-row';
    var arrow = document.createElement('span');
    arrow.className = 'dir-arrow';
    arrow.textContent = '\\u25BC';
    var dirName = document.createElement('span');
    dirName.className = 'dir-name';
    dirName.textContent = dir === '.' ? '(root)' : dir;
    var count = document.createElement('span');
    count.className = 'dir-count';
    count.textContent = items.length;
    dirRow.appendChild(arrow);
    dirRow.appendChild(dirName);
    dirRow.appendChild(count);
    dirEl.appendChild(dirRow);

    // File list container
    var fileList = document.createElement('div');
    fileList.className = 'file-list';

    items.forEach(function(f) {
      fileList.appendChild(createFileRow(f));
    });

    dirEl.appendChild(fileList);

    // Toggle collapse
    dirRow.addEventListener('click', function() {
      var hidden = fileList.style.display === 'none';
      fileList.style.display = hidden ? '' : 'none';
      arrow.classList.toggle('collapsed', !hidden);
    });

    tree.appendChild(dirEl);
  });
}

// ── Build workflow-grouped tree for "In Progress" tab ──
function buildWorkflowTree(files) {
  tree.innerHTML = '';

  // Group files by workflow stage
  var groups = {};  // stage -> [files]
  files.forEach(function(f) {
    var stage = f.workflow_stage || 0;
    if (!groups[stage]) groups[stage] = [];
    groups[stage].push(f);
  });

  // Define display order: active stages 1-7, then 0 (no stage), then 8 (archived)
  var order = [1, 2, 3, 4, 5, 6, 7, 0, 8];

  order.forEach(function(stageId) {
    var items = groups[stageId];
    if (!items || items.length === 0) return;

    // Group header
    var header = document.createElement('div');
    header.className = 'wf-group-header';

    if (stageId === 0) {
      header.innerHTML = '<span class="wf-group-dot" style="background:var(--text-dim)"></span>' +
        '<span>未分配 (' + items.length + ')</span>';
    } else {
      var stageInfo = workflowStages.find(function(s) { return s.id === stageId; });
      var label = stageInfo ? stageInfo.abbr + ' - ' + stageInfo.label : 'Stage ' + stageId;
      var color = wfStageColors[stageId] || 'var(--text-dim)';
      header.innerHTML = '<span class="wf-group-dot" style="background:' + color + '"></span>' +
        '<span>' + label + ' (' + items.length + ')</span>';
    }
    tree.appendChild(header);

    // File rows
    items.sort(function(a, b) { return a.file.localeCompare(b.file); });
    items.forEach(function(f) {
      tree.appendChild(createFileRow(f));
    });
  });
}

function toggleAllDirs(expand) {
  var tree = document.getElementById('tree');
  tree.querySelectorAll('.file-list').forEach(function(fl) {
    fl.style.display = expand ? '' : 'none';
  });
  tree.querySelectorAll('.dir-arrow').forEach(function(a) {
    a.classList.toggle('collapsed', !expand);
  });
}

// ── Load file list ──
function loadFileList(refresh) {
  tree.innerHTML = '<div class="sidebar-loading">Loading file list...</div>';
  headerInfo.textContent = '';
  var url = refresh ? '/api/files?refresh=1' : '/api/files';
  fetch(url)
    .then(function(r) { return r.json(); })
    .then(function(data) {
      allFiles = data.files;
      summaryData = data.summary;
      updateSummary();
      headerInfo.textContent = summaryData.translated + '/' + summaryData.total_english + ' translated';
      buildTree(getFilteredFiles());
    })
    .catch(function(err) {
      tree.innerHTML = '<div class="sidebar-loading">Error: ' + err + '</div>';
    });
}

document.getElementById('refresh-btn').addEventListener('click', function() { loadFileList(true); });
loadFileList(false);

// ── Panel helpers ──
function showPanels(visible) {
  if (visible) {
    placeholder.style.display = 'none';
    panelEn.style.display = '';
    panelZh.style.display = '';
  } else {
    panelEn.style.display = 'none';
    panelZh.style.display = 'none';
    placeholder.style.display = 'flex';
  }
}

function showPlaceholder(msg) {
  showPanels(false);
  placeholder.textContent = msg;
}

// ── Render diff hunks ──
function renderHunks(hunks, target) {
  target.innerHTML = '';
  if (!hunks || hunks.length === 0) {
    target.innerHTML = '<div class="no-diff">No changes</div>';
    return;
  }
  hunks.forEach(function(hunk) {
    var hdr = document.createElement('div');
    hdr.className = 'hunk-header';
    hdr.textContent = hunk.header;
    target.appendChild(hdr);
    hunk.lines.forEach(function(line) {
      var div = document.createElement('div');
      div.className = 'diff-line ' + line.type;
      var prefix = line.type === 'add' ? '+' : line.type === 'del' ? '-' : ' ';
      div.textContent = prefix + line.text;
      target.appendChild(div);
    });
  });
}

// ── Render raw file content with line numbers ──
function showFileContent(content, target) {
  target.innerHTML = '';
  var container = document.createElement('div');
  container.className = 'file-content';
  var lines = content.split('\\n');
  for (var i = 0; i < lines.length; i++) {
    var div = document.createElement('div');
    div.className = 'content-line';
    var num = document.createElement('span');
    num.className = 'line-num';
    num.textContent = String(i + 1);
    div.appendChild(num);
    div.appendChild(document.createTextNode(lines[i]));
    container.appendChild(div);
  }
  target.appendChild(container);
}

// ── HTML Preview helpers ──
function rstToHtmlPath(rstFile) {
  return rstFile.replace(/\\.rst$/, '.html');
}

// ── Heading-based scroll sync ──
// Detects RST headings and HTML <h1>-<h6> to scroll related sections together.
var scrollSyncing = false;
var enRstHeadings = [];  // [{offsetTop}, ...]
var zhRstHeadings = [];
var enHtmlHeadings = []; // [{offsetTop}, ...]
var zhHtmlHeadings = [];

function withSyncLock(fn) {
  if (scrollSyncing) return;
  scrollSyncing = true;
  try { fn(); } catch(e) {}
  requestAnimationFrame(function() { scrollSyncing = false; });
}

// Scan RST content-line elements for heading patterns (line followed by underline)
function isRstUnderline(text) {
  var t = text.trim();
  if (t.length < 3) return false;
  var ch = t[0];
  if ('=-~^"`.+*#:'.indexOf(ch) < 0) return false;
  for (var i = 1; i < t.length; i++) { if (t[i] !== ch) return false; }
  return true;
}

function elPos(el, body) {
  return el.getBoundingClientRect().top - body.getBoundingClientRect().top + body.scrollTop;
}

function buildRstHeadings(body) {
  var headings = [];

  // Full file view: detect heading underlines in .content-line elements
  var lines = body.querySelectorAll('.content-line');
  if (lines.length > 0) {
    for (var i = 0; i + 1 < lines.length; i++) {
      var nodes = lines[i + 1].childNodes;
      var text = '';
      for (var j = 1; j < nodes.length; j++) text += nodes[j].textContent;
      if (isRstUnderline(text)) {
        var hText = '';
        var hn = lines[i].childNodes;
        for (var k = 1; k < hn.length; k++) hText += hn[k].textContent;
        if (hText.trim().length > 0) {
          headings.push({ offsetTop: elPos(lines[i], body) });
        }
      }
    }
    return headings;
  }

  // Diff view: detect headings in .diff-line elements
  var dlines = body.querySelectorAll('.diff-line');
  if (dlines.length > 0) {
    for (var i = 0; i + 1 < dlines.length; i++) {
      // Strip the +/-/space prefix
      var t2 = dlines[i + 1].textContent.substring(1);
      if (isRstUnderline(t2)) {
        var t1 = dlines[i].textContent.substring(1).trim();
        if (t1.length > 0) {
          headings.push({ offsetTop: elPos(dlines[i], body), text: t1 });
        }
      }
    }
    return headings;
  }

  return headings;
}

// Collect heading positions from an HTML iframe
function buildHtmlHeadings(iframe) {
  try {
    var doc = iframe.contentDocument || iframe.contentWindow.document;
    var scrollEl = doc.scrollingElement || doc.documentElement;
    var els = doc.querySelectorAll('h1, h2, h3, h4, h5, h6');
    return Array.from(els).map(function(el) {
      return {
        offsetTop: el.getBoundingClientRect().top + scrollEl.scrollTop,
        text: el.textContent.trim()
      };
    });
  } catch(e) { return []; }
}

// Find best matching HTML heading index for a given text
function findHtmlHeadingByText(htmlH, text) {
  if (!text) return -1;
  var lower = text.toLowerCase();
  for (var i = 0; i < htmlH.length; i++) {
    if (htmlH[i].text && htmlH[i].text.toLowerCase().indexOf(lower) >= 0) return i;
  }
  // Partial match: first few words
  var words = lower.split(/\\s+/).slice(0, 3).join(' ');
  if (words.length >= 4) {
    for (var i = 0; i < htmlH.length; i++) {
      if (htmlH[i].text && htmlH[i].text.toLowerCase().indexOf(words) >= 0) return i;
    }
  }
  return -1;
}

// Map scroll position between two sets of headings.
// Uses text matching when available (diff view), index matching otherwise.
function mapScrollPosition(srcH, srcScroll, srcScrollMax, tgtH, tgtScrollMax) {
  // Ratio fallback when no headings
  if (srcH.length === 0 || tgtH.length === 0) {
    if (srcScrollMax <= 0) return 0;
    return (srcScroll / srcScrollMax) * tgtScrollMax;
  }

  // Find current source heading
  var idx = -1;
  for (var i = 0; i < srcH.length; i++) {
    if (srcH[i].offsetTop <= srcScroll + 30) idx = i;
  }

  if (idx < 0) {
    var srcFirst = srcH[0].offsetTop;
    var tgtFirst = tgtH[0].offsetTop;
    if (srcFirst <= 0) return 0;
    return Math.min(1, srcScroll / srcFirst) * tgtFirst;
  }

  // Map to target heading: text match first, then index
  var tgtIdx;
  if (srcH[idx].text) {
    tgtIdx = findHtmlHeadingByText(tgtH, srcH[idx].text);
    if (tgtIdx < 0) tgtIdx = Math.min(idx, tgtH.length - 1);
  } else {
    tgtIdx = Math.min(idx, tgtH.length - 1);
  }

  var srcStart = srcH[idx].offsetTop;
  var srcEnd = (idx + 1 < srcH.length) ? srcH[idx + 1].offsetTop : srcScrollMax;
  var tgtStart = tgtH[tgtIdx].offsetTop;
  var tgtEnd = (tgtIdx + 1 < tgtH.length) ? tgtH[tgtIdx + 1].offsetTop : tgtScrollMax;

  var srcRange = srcEnd - srcStart;
  var progress = srcRange > 0 ? (srcScroll - srcStart) / srcRange : 0;
  progress = Math.max(0, Math.min(1, progress));
  return tgtStart + progress * (tgtEnd - tgtStart);
}

function scrollIframeTo(iframe, pos) {
  try {
    var doc = iframe.contentDocument || iframe.contentWindow.document;
    (doc.scrollingElement || doc.documentElement).scrollTop = pos;
  } catch(e) {}
}

function getIframeScroll(iframe) {
  try {
    var doc = iframe.contentDocument || iframe.contentWindow.document;
    var el = doc.scrollingElement || doc.documentElement;
    return { scrollTop: el.scrollTop, scrollHeight: el.scrollHeight, clientHeight: el.clientHeight };
  } catch(e) { return null; }
}

// RST body scroll → own HTML preview + cross-panel RST body
enBody.addEventListener('scroll', function() {
  withSyncLock(function() {
    var s = getIframeScroll(enPreview);
    if (s) {
      var srcMax = enBody.scrollHeight - enBody.clientHeight;
      var tgtMax = s.scrollHeight - s.clientHeight;
      scrollIframeTo(enPreview, mapScrollPosition(
        enRstHeadings, enBody.scrollTop, srcMax || enBody.scrollHeight,
        enHtmlHeadings, tgtMax || s.scrollHeight));
    }
    var r = enBody.scrollTop / (enBody.scrollHeight - enBody.clientHeight || 1);
    zhBody.scrollTop = r * (zhBody.scrollHeight - zhBody.clientHeight || 1);
  });
});
zhBody.addEventListener('scroll', function() {
  withSyncLock(function() {
    var s = getIframeScroll(zhPreview);
    if (s) {
      var srcMax = zhBody.scrollHeight - zhBody.clientHeight;
      var tgtMax = s.scrollHeight - s.clientHeight;
      scrollIframeTo(zhPreview, mapScrollPosition(
        zhRstHeadings, zhBody.scrollTop, srcMax || zhBody.scrollHeight,
        zhHtmlHeadings, tgtMax || s.scrollHeight));
    }
    var r = zhBody.scrollTop / (zhBody.scrollHeight - zhBody.clientHeight || 1);
    enBody.scrollTop = r * (enBody.scrollHeight - enBody.clientHeight || 1);
  });
});

// HTML iframe scroll → own RST body + cross-panel HTML iframe
function attachEnPreviewSync() {
  try {
    enPreview.contentWindow.addEventListener('scroll', function() {
      withSyncLock(function() {
        var s = getIframeScroll(enPreview);
        if (!s) return;
        var srcMax = s.scrollHeight - s.clientHeight;
        var tgtMax = enBody.scrollHeight - enBody.clientHeight;
        enBody.scrollTop = mapScrollPosition(
          enHtmlHeadings, s.scrollTop, srcMax || s.scrollHeight,
          enRstHeadings, tgtMax || enBody.scrollHeight);
        var t = getIframeScroll(zhPreview);
        if (t && zhHtmlHeadings.length > 0) {
          var tgtMax2 = t.scrollHeight - t.clientHeight;
          scrollIframeTo(zhPreview, mapScrollPosition(
            enHtmlHeadings, s.scrollTop, srcMax || s.scrollHeight,
            zhHtmlHeadings, tgtMax2 || t.scrollHeight));
        }
      });
    });
  } catch(e) {}
}
function attachZhPreviewSync() {
  try {
    zhPreview.contentWindow.addEventListener('scroll', function() {
      withSyncLock(function() {
        var s = getIframeScroll(zhPreview);
        if (!s) return;
        var srcMax = s.scrollHeight - s.clientHeight;
        var tgtMax = zhBody.scrollHeight - zhBody.clientHeight;
        zhBody.scrollTop = mapScrollPosition(
          zhHtmlHeadings, s.scrollTop, srcMax || s.scrollHeight,
          zhRstHeadings, tgtMax || zhBody.scrollHeight);
        var t = getIframeScroll(enPreview);
        if (t && enHtmlHeadings.length > 0) {
          var tgtMax2 = t.scrollHeight - t.clientHeight;
          scrollIframeTo(enPreview, mapScrollPosition(
            zhHtmlHeadings, s.scrollTop, srcMax || s.scrollHeight,
            enHtmlHeadings, tgtMax2 || t.scrollHeight));
        }
      });
    });
  } catch(e) {}
}

function previewUrl(file, side) {
  return '/api/rst-preview?file=' + encodeURIComponent(file) + '&side=' + side + '&t=' + Date.now();
}

function updatePreviews(file, zhBlank) {
  enRstHeadings = []; zhRstHeadings = [];
  enHtmlHeadings = []; zhHtmlHeadings = [];

  enPreview.onload = function() {
    enRstHeadings = buildRstHeadings(enBody);
    enHtmlHeadings = buildHtmlHeadings(enPreview);
    attachEnPreviewSync();
  };
  enPreview.src = previewUrl(file, 'en');

  if (zhBlank) {
    zhPreview.onload = null;
    zhPreview.src = 'about:blank';
  } else {
    zhPreview.onload = function() {
      zhRstHeadings = buildRstHeadings(zhBody);
      zhHtmlHeadings = buildHtmlHeadings(zhPreview);
      attachZhPreviewSync();
    };
    zhPreview.src = previewUrl(file, 'zh');
  }
}

// ── Draggable split bars ──
function initSplitDrag(splitEl, paneEl) {
  splitEl.addEventListener('mousedown', function(e) {
    e.preventDefault();
    var panel = splitEl.parentElement;
    var startY = e.clientY;
    var startH = paneEl.offsetHeight;
    var panelH = panel.offsetHeight;
    function onMove(ev) {
      var delta = ev.clientY - startY;
      var newH = Math.max(40, Math.min(panelH - 80, startH + delta));
      paneEl.style.height = newH + 'px';
    }
    function onUp() {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    }
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });
}
initSplitDrag(enSplit, enPreviewPane);
initSplitDrag(zhSplit, zhPreviewPane);

// ── Workflow select handler ──
wfSelect.addEventListener('change', function() {
  if (!currentFile) return;
  var stage = parseInt(wfSelect.value, 10);
  fetch('/api/workflow', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ file: currentFile.file, stage: stage })
  })
  .then(function(r) { return r.json(); })
  .then(function(data) {
    if (data.ok) {
      // Update local data
      currentFile.workflow_stage = stage;
      var match = allFiles.find(function(f) { return f.file === currentFile.file; });
      if (match) match.workflow_stage = stage;
      // Rebuild tree to reflect changes
      updateSummary();
      buildTree(getFilteredFiles());
    }
  });
});

// ── Select file: dispatch view based on status ──
function selectFile(fileObj, rowEl) {
  if (editorMode) exitEditor();
  if (activeFileEl) activeFileEl.classList.remove('active');
  activeFileEl = rowEl;
  rowEl.classList.add('active');
  currentFile = fileObj;

  // Sync workflow dropdown
  wfSelect.style.display = '';
  wfSelect.value = fileObj.workflow_stage || 0;

  showPlaceholder('Loading ' + fileObj.file + '...');

  if (fileObj.status === 'outdated') {
    loadDiffView(fileObj.file);
  } else if (fileObj.status === 'missing') {
    loadMissingView(fileObj.file);
  } else if (fileObj.status === 'up_to_date' && fileObj.working_tree) {
    loadWorkingTreeView(fileObj.file);
  } else {
    loadSideBySideView(fileObj.file);
  }
}

// View: outdated files — English diff + Chinese working-tree diff
function loadDiffView(file) {
  fetch('/api/diff?file=' + encodeURIComponent(file))
    .then(function(r) { return r.json(); })
    .then(function(data) {
      showPanels(true);
      enHeader.textContent = 'English Changes \\u2014 ' + file;
      zhHeaderText.textContent = 'Chinese Changes \\u2014 ' + file;
      editBtn.style.display = '';
      renderHunks(data.en_hunks, enBody);
      renderHunks(data.zh_hunks, zhBody);
      enBody.scrollTop = 0;
      zhBody.scrollTop = 0;
      updatePreviews(file);
    })
    .catch(function(err) { showPlaceholder('Error: ' + err); });
}

// View: missing files — English full content + "no translation" message
function loadMissingView(file) {
  fetch('/api/file-content?file=' + encodeURIComponent(file) + '&side=en')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      showPanels(true);
      enHeader.textContent = 'English Source \\u2014 ' + file;
      zhHeaderText.textContent = 'Chinese Translation \\u2014 ' + file;
      editBtn.style.display = '';
      if (data.content != null) {
        showFileContent(data.content, enBody);
      } else {
        enBody.innerHTML = '<div class="no-diff">File not found</div>';
      }
      zhBody.innerHTML = '<div class="no-diff">\\u6682\\u65E0\\u4E2D\\u6587\\u7FFB\\u8BD1<br><br>No Chinese translation yet.</div>';
      enBody.scrollTop = 0;
      zhBody.scrollTop = 0;
      updatePreviews(file, true);
    })
    .catch(function(err) { showPlaceholder('Error: ' + err); });
}

// View: up_to_date + working_tree — "no English changes" + Chinese diff
function loadWorkingTreeView(file) {
  fetch('/api/diff?file=' + encodeURIComponent(file))
    .then(function(r) { return r.json(); })
    .then(function(data) {
      showPanels(true);
      enHeader.textContent = 'English Changes \\u2014 ' + file;
      zhHeaderText.textContent = 'Chinese Changes \\u2014 ' + file;
      editBtn.style.display = '';
      if (!data.en_hunks || data.en_hunks.length === 0) {
        enBody.innerHTML = '<div class="no-diff">\\u82F1\\u6587\\u65E0\\u53D8\\u66F4<br><br>English source is up to date.</div>';
      } else {
        renderHunks(data.en_hunks, enBody);
      }
      renderHunks(data.zh_hunks, zhBody);
      enBody.scrollTop = 0;
      zhBody.scrollTop = 0;
      updatePreviews(file);
    })
    .catch(function(err) { showPlaceholder('Error: ' + err); });
}

// View: up_to_date (no working tree) — side-by-side full content
function loadSideBySideView(file) {
  Promise.all([
    fetch('/api/file-content?file=' + encodeURIComponent(file) + '&side=en').then(function(r) { return r.json(); }),
    fetch('/api/file-content?file=' + encodeURIComponent(file) + '&side=zh').then(function(r) { return r.json(); })
  ]).then(function(results) {
    var enData = results[0];
    var zhData = results[1];
    showPanels(true);
    enHeader.textContent = 'English Source \\u2014 ' + file;
    zhHeaderText.textContent = 'Chinese Translation \\u2014 ' + file;
    editBtn.style.display = '';
    if (enData.content != null) {
      showFileContent(enData.content, enBody);
    } else {
      enBody.innerHTML = '<div class="no-diff">File not found</div>';
    }
    if (zhData.content != null) {
      showFileContent(zhData.content, zhBody);
    } else {
      zhBody.innerHTML = '<div class="no-diff">File not found</div>';
    }
    enBody.scrollTop = 0;
    zhBody.scrollTop = 0;
    updatePreviews(file);
  }).catch(function(err) { showPlaceholder('Error: ' + err); });
}

// ── Editor mode ──
function enterEditor() {
  if (!currentFile) return;
  editorMode = true;
  saveStatus.textContent = '';

  if (currentFile.status === 'missing') {
    // Pre-fill with English source as template
    fetch('/api/file-content?file=' + encodeURIComponent(currentFile.file) + '&side=en')
      .then(function(r) { return r.json(); })
      .then(function(data) {
        editorTextarea.value = data.content || '';
      });
  } else {
    // Load current Chinese content
    fetch('/api/file-content?file=' + encodeURIComponent(currentFile.file) + '&side=zh')
      .then(function(r) { return r.json(); })
      .then(function(data) {
        editorTextarea.value = data.content || '';
      });
  }

  zhBody.style.display = 'none';
  zhEditor.style.display = 'flex';
  editorTextarea.focus();
}

function exitEditor() {
  editorMode = false;
  zhEditor.style.display = 'none';
  zhBody.style.display = '';
}

function saveFile() {
  if (!currentFile) return;
  saveStatus.textContent = 'Saving...';
  saveStatus.style.color = 'var(--text-dim)';
  fetch('/api/save-file', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ file: currentFile.file, content: editorTextarea.value })
  })
  .then(function(r) { return r.json(); })
  .then(function(data) {
    if (data.ok) {
      saveStatus.textContent = 'Saved';
      saveStatus.style.color = 'var(--add-text)';
      // Refresh Chinese HTML preview with updated content
      if (currentFile) {
        zhPreview.src = previewUrl(currentFile.file, 'zh');
      }
    } else {
      saveStatus.textContent = 'Error: ' + (data.error || 'unknown');
      saveStatus.style.color = 'var(--del-text)';
    }
  })
  .catch(function(err) {
    saveStatus.textContent = 'Error: ' + err;
    saveStatus.style.color = 'var(--del-text)';
  });
}

editBtn.addEventListener('click', enterEditor);
saveBtn.addEventListener('click', saveFile);
backBtn.addEventListener('click', exitEditor);

document.addEventListener('keydown', function(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === 's') {
    if (editorMode) {
      e.preventDefault();
      saveFile();
    }
  }
});
</script>
</body>
</html>
"""


# ── HTTP Handler ────────────────────────────────────────────────────────


class DiffHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        params = parse_qs(parsed.query)

        if path == "/":
            self._send_html(INDEX_HTML)
        elif path == "/api/files":
            if params.get("refresh"):
                clear_all_files_cache()
            data = get_all_files()
            self._send_json(data)
        elif path == "/api/diff":
            file_path = params.get("file", [""])[0]
            if not file_path:
                self._send_json({"error": "missing file parameter"}, 400)
                return
            diff_data = get_diff(file_path)
            result = {
                "file": file_path,
                "en_hunks": parse_diff(diff_data["en_diff"]),
                "zh_hunks": parse_diff(diff_data["zh_diff"]),
            }
            self._send_json(result)
        elif path == "/api/file-content":
            file_path = params.get("file", [""])[0]
            side = params.get("side", [""])[0]
            if not file_path or side not in ("en", "zh"):
                self._send_json({"error": "missing file or side parameter"}, 400)
                return
            content = get_file_content(file_path, side)
            self._send_json({"content": content})
        elif path == "/api/rst-preview":
            file_path = params.get("file", [""])[0]
            side = params.get("side", [""])[0]
            if not file_path or side not in ("en", "zh"):
                self._send_json({"error": "missing file or side parameter"}, 400)
                return
            html = render_rst_preview(file_path, side)
            if html is None:
                self._send_html(
                    "<html><body><p>File not found</p></body></html>", 404)
            else:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(html.encode())
        elif path == "/api/workflow-stages":
            self._send_json({"stages": WORKFLOW_STAGES})
        elif path.startswith("/docs/"):
            rel_path = path[len("/docs/"):]
            base_dir = KERNEL_DIR / "Documentation" / "output"
            self._serve_static_file(base_dir, rel_path)
        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/api/save-file":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length))
            except (ValueError, json.JSONDecodeError):
                self._send_json({"error": "invalid JSON"}, 400)
                return

            file_path = body.get("file", "")
            content = body.get("content", "")
            if not file_path:
                self._send_json({"error": "missing file parameter"}, 400)
                return

            ok, err = save_file_content(file_path, content)
            if ok:
                self._send_json({"ok": True})
            else:
                self._send_json({"error": err}, 400)
        elif path == "/api/workflow":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length))
            except (ValueError, json.JSONDecodeError):
                self._send_json({"error": "invalid JSON"}, 400)
                return

            file_path = body.get("file", "")
            stage = body.get("stage")
            if not file_path or stage is None:
                self._send_json({"error": "missing file or stage"}, 400)
                return
            try:
                stage = int(stage)
            except (TypeError, ValueError):
                self._send_json({"error": "stage must be an integer"}, 400)
                return

            wf = _load_workflow_state()
            if stage == 0:
                wf.pop(file_path, None)
            else:
                wf[file_path] = {
                    "stage": stage,
                    "updated_at": datetime.now(timezone.utc)
                        .strftime("%Y-%m-%dT%H:%M:%S"),
                }
            _save_workflow_state(wf)
            self._send_json({"ok": True})
        else:
            self._send_json({"error": "not found"}, 404)

    def _serve_static_file(self, base_dir, rel_path):
        """Serve a static file from base_dir/rel_path with path traversal protection."""
        if ".." in rel_path:
            self._send_json({"error": "invalid path"}, 400)
            return

        full_path = (base_dir / rel_path).resolve()

        # Verify resolved path is under base_dir
        try:
            base_resolved = base_dir.resolve()
            if not str(full_path).startswith(str(base_resolved)):
                self._send_json({"error": "path escapes base directory"}, 403)
                return
        except (OSError, ValueError):
            self._send_json({"error": "invalid path"}, 400)
            return

        if not full_path.is_file():
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<html><body><p>HTML not built. Run <code>make htmldocs</code> in the kernel tree.</p></body></html>")
            return

        mime_type, _ = mimetypes.guess_type(str(full_path))
        if mime_type is None:
            mime_type = "application/octet-stream"

        try:
            data = full_path.read_bytes()
        except OSError:
            self._send_json({"error": "read error"}, 500)
            return

        self.send_response(200)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_html(self, content, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode())

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[diff-web] {args[0]} {args[1]} {args[2]}\n")


def main():
    port = DEFAULT_PORT

    # Simple --port argument
    args = sys.argv[1:]
    if "--port" in args:
        idx = args.index("--port")
        if idx + 1 < len(args):
            port = int(args[idx + 1])

    if not KERNEL_DIR.is_dir() or not (KERNEL_DIR / ".git").exists():
        print(f"Error: kernel repo not found at {KERNEL_DIR}")
        print("Run scripts/setup.sh first.")
        sys.exit(1)

    server = http.server.HTTPServer(("0.0.0.0", port), DiffHandler)
    print(f"Translation Diff Viewer running at http://0.0.0.0:{port}/")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
