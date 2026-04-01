"""Git operation wrappers for the kernel repository."""

from __future__ import annotations

import concurrent.futures
import subprocess
from pathlib import Path


def git(*args: str, cwd: str | Path | None = None) -> subprocess.CompletedProcess:
    """Run a git command and return the CompletedProcess.

    If *cwd* is None, uses the kernel directory from project.py.
    """
    if cwd is None:
        from lib.project import kernel_dir
        cwd = kernel_dir()
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


def git_stdout(*args: str, cwd: str | Path | None = None) -> str:
    """Run a git command and return stripped stdout."""
    return git(*args, cwd=cwd).stdout.strip()


def git_lines(*args: str, cwd: str | Path | None = None) -> list[str]:
    """Run a git command and return non-empty stdout lines."""
    return [l for l in git_stdout(*args, cwd=cwd).splitlines() if l.strip()]


# ── Branch / identity ───────────────────────────────────────────────

def current_branch(cwd: str | Path | None = None) -> str:
    return git_stdout("branch", "--show-current", cwd=cwd)


def head_oneline(cwd: str | Path | None = None) -> str:
    return git_stdout("log", "--oneline", "-1", cwd=cwd)


# ── Branch operations ─────────────────────────────────────────────

WORK_BRANCH_PREFIX = "zh-work/"


def branch_exists(name: str, cwd: str | Path | None = None) -> bool:
    """Check if a local branch exists."""
    r = git("rev-parse", "--verify", name, cwd=cwd)
    return r.returncode == 0


def create_branch(name: str, base: str = "docs-next",
                  cwd: str | Path | None = None) -> None:
    """Create a new branch from *base*. Raises on failure."""
    r = git("branch", name, base, cwd=cwd)
    if r.returncode != 0:
        raise RuntimeError(f"git branch {name} {base} failed: {r.stderr.strip()}")


def checkout(branch: str, cwd: str | Path | None = None) -> None:
    """Switch to *branch*. Raises on failure."""
    r = git("checkout", branch, cwd=cwd)
    if r.returncode != 0:
        raise RuntimeError(f"git checkout {branch} failed: {r.stderr.strip()}")


def delete_branch(name: str, cwd: str | Path | None = None) -> None:
    """Delete a local branch. Raises on failure."""
    r = git("branch", "-D", name, cwd=cwd)
    if r.returncode != 0:
        raise RuntimeError(f"git branch -D {name} failed: {r.stderr.strip()}")


def is_work_branch(branch: str | None = None,
                   cwd: str | Path | None = None) -> bool:
    """Check if *branch* (default: current) is a zh-work/* branch."""
    if branch is None:
        branch = current_branch(cwd=cwd)
    return branch.startswith(WORK_BRANCH_PREFIX)


def series_id_from_branch(branch: str | None = None,
                          cwd: str | Path | None = None) -> str | None:
    """Extract series-id from a zh-work/<series-id> branch name.

    Returns None if the branch is not a work branch.
    """
    if branch is None:
        branch = current_branch(cwd=cwd)
    if branch.startswith(WORK_BRANCH_PREFIX):
        return branch[len(WORK_BRANCH_PREFIX):]
    return None


def work_branch_name(series_id: str) -> str:
    """Return the branch name for a series-id."""
    return f"{WORK_BRANCH_PREFIX}{series_id}"


def list_work_branches(cwd: str | Path | None = None) -> list[str]:
    """Return all zh-work/* branch names."""
    lines = git_lines("branch", "--list", f"{WORK_BRANCH_PREFIX}*", cwd=cwd)
    # git branch prefixes current branch with "* " and others with "  "
    return [l.strip().removeprefix("* ") for l in lines]


def ensure_clean_worktree(cwd: str | Path | None = None) -> None:
    """Raise if the working tree has uncommitted changes."""
    r = git("diff", "--quiet", cwd=cwd)
    r2 = git("diff", "--cached", "--quiet", cwd=cwd)
    if r.returncode != 0 or r2.returncode != 0:
        raise RuntimeError("工作区有未提交的更改，请先 commit 或 stash。")


def user_name(cwd: str | Path | None = None) -> str:
    return git_stdout("config", "user.name", cwd=cwd)


def user_email(cwd: str | Path | None = None) -> str:
    return git_stdout("config", "user.email", cwd=cwd)


# ── Commit map for zh_CN files ──────────────────────────────────────

def build_zh_commit_map(cwd: str | Path | None = None) -> dict[str, tuple[str, str]]:
    """Build a map: zh_CN file path -> (last_commit_hash, date).

    Single ``git log`` pass — much faster than per-file queries.
    Returns keys like ``Documentation/translations/zh_CN/admin-guide/README.rst``.
    """
    raw = git_stdout(
        "log", "--format=%H %as", "--name-only",
        "--diff-filter=ACMR",
        "--", "Documentation/translations/zh_CN/",
        cwd=cwd,
    )
    file_map: dict[str, tuple[str, str]] = {}
    current_commit: str | None = None
    current_date: str | None = None

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(" ", 1)
        if len(parts) == 2 and len(parts[0]) == 40:
            current_commit = parts[0]
            current_date = parts[1]
        elif current_commit and current_date and line.startswith("Documentation/translations/zh_CN/"):
            if line not in file_map:
                file_map[line] = (current_commit, current_date)

    return file_map


def english_commits_since(en_rel: str, since_commit: str,
                          cwd: str | Path | None = None) -> int:
    """Count English doc commits since *since_commit*."""
    count_str = git_stdout(
        "rev-list", "--count", f"{since_commit}..HEAD", "--", en_rel,
        cwd=cwd,
    )
    try:
        return int(count_str)
    except ValueError:
        return 0


def english_commits_since_batch(
    items: list[tuple[str, str]],
    cwd: str | Path | None = None,
    max_workers: int = 16,
) -> list[int]:
    """Parallel version: count commits for [(en_rel, since_commit), ...]."""
    def _check(args: tuple[str, str]) -> int:
        return english_commits_since(args[0], args[1], cwd=cwd)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(_check, items))


# ── Working tree helpers ────────────────────────────────────────────

def working_tree_zh_files(cwd: str | Path | None = None) -> set[str]:
    """Return set of zh_CN files with uncommitted changes (unstaged+staged+untracked)."""
    prefix = "Documentation/translations/zh_CN/"
    files: set[str] = set()

    for cmd_args in [
        ("diff", "--name-only", "--", prefix),
        ("diff", "--cached", "--name-only", "--", prefix),
        ("ls-files", "--others", "--exclude-standard", "--", prefix),
    ]:
        for line in git_lines(*cmd_args, cwd=cwd):
            files.add(line.strip())

    return files


# ── Diff helpers ────────────────────────────────────────────────────

def commits_between(base: str, tip: str = "HEAD", path: str | None = None,
                    cwd: str | Path | None = None) -> list[str]:
    """Return oneline commit list between base..tip, optionally filtered by path."""
    args = ["log", "--oneline", f"{base}..{tip}"]
    if path:
        args += ["--", path]
    return git_lines(*args, cwd=cwd)


def diff_between(base: str, tip: str = "HEAD", path: str | None = None,
                 cwd: str | Path | None = None) -> str:
    """Return diff text between base..tip."""
    args = ["diff", f"{base}..{tip}"]
    if path:
        args += ["--", path]
    return git_stdout(*args, cwd=cwd)


def last_commit_for_file(filepath: str, fmt: str = "%H",
                         cwd: str | Path | None = None) -> str:
    """Return the last commit touching *filepath*."""
    return git_stdout("log", "-1", f"--format={fmt}", "--", filepath, cwd=cwd)


def is_ancestor(commit: str, branch: str = "docs-next",
                cwd: str | Path | None = None) -> bool:
    """Check if *commit* is an ancestor of *branch*."""
    r = git("merge-base", "--is-ancestor", commit, branch, cwd=cwd)
    return r.returncode == 0


# ── Format-patch ────────────────────────────────────────────────────

def format_patch(
    base: str = "docs-next",
    tip: str = "HEAD",
    output_dir: str | Path = ".",
    cover_letter: bool = False,
    version: int | None = None,
    cwd: str | Path | None = None,
) -> list[str]:
    """Run git format-patch and return list of generated patch filenames."""
    args = ["format-patch", f"{base}..{tip}", "-o", str(output_dir)]
    if cover_letter:
        args += ["--cover-letter", "--thread=shallow"]
    if version is not None and version > 1:
        args += [f"--reroll-count={version}"]
    out = git_stdout(*args, cwd=cwd)
    return [l for l in out.splitlines() if l.strip()]
