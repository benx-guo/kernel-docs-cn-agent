"""Patch validation utilities: checkpatch, get_maintainer, htmldocs."""

from __future__ import annotations

import subprocess
from pathlib import Path


def run_checkpatch(
    patch_file: str | Path,
    kernel_dir: str | Path,
) -> dict:
    """Run checkpatch.pl on a single patch file.

    Returns ``{"returncode": int, "errors": int, "warnings": int, "output": str}``.
    """
    script = Path(kernel_dir) / "scripts" / "checkpatch.pl"
    if not script.is_file():
        return {"returncode": -1, "errors": 0, "warnings": 0,
                "output": f"checkpatch.pl not found at {script}"}

    r = subprocess.run(
        ["perl", str(script), str(patch_file)],
        cwd=str(kernel_dir),
        capture_output=True,
        text=True,
    )
    output = r.stdout + r.stderr
    errors = 0
    warnings = 0
    for line in output.splitlines():
        if line.startswith("total:"):
            # e.g. "total: 0 errors, 2 warnings, 45 lines checked"
            parts = line.split(",")
            for part in parts:
                part = part.strip()
                if "error" in part:
                    try:
                        errors = int(part.split()[0])
                    except (ValueError, IndexError):
                        pass
                elif "warning" in part:
                    try:
                        warnings = int(part.split()[0])
                    except (ValueError, IndexError):
                        pass
    return {
        "returncode": r.returncode,
        "errors": errors,
        "warnings": warnings,
        "output": output,
    }


def run_get_maintainer(
    patch_file: str | Path,
    kernel_dir: str | Path,
) -> list[str]:
    """Run get_maintainer.pl on a patch and return the list of recipients."""
    script = Path(kernel_dir) / "scripts" / "get_maintainer.pl"
    if not script.is_file():
        return []

    r = subprocess.run(
        ["perl", str(script), "--no-rolestats", str(patch_file)],
        cwd=str(kernel_dir),
        capture_output=True,
        text=True,
    )
    return [l.strip() for l in r.stdout.splitlines() if l.strip()]


def run_htmldocs(
    kernel_dir: str | Path,
    filter_zh_cn: bool = True,
    clean: bool = False,
) -> dict:
    """Run ``make htmldocs`` and return build results.

    Returns ``{"returncode": int, "warnings": list[str], "errors": list[str],
    "skipped": bool, "skip_reason": str | None}``.

    Pre-checks: sphinx-build and GNU Make >= 4.0 must be available.
    If not, returns skipped=True with the reason — callers should treat
    this as a blocking error, not a pass.
    """
    import shutil
    import os

    # --- Pre-check: sphinx ---
    has_sphinx = (shutil.which("sphinx-build") is not None or
                  subprocess.run(
                      ["python3", "-m", "sphinx", "--version"],
                      capture_output=True).returncode == 0)
    if not has_sphinx:
        return {
            "returncode": -1,
            "warnings": [],
            "errors": ["sphinx-build not installed"],
            "skipped": True,
            "skip_reason": "sphinx-build not installed — run: pip install sphinx",
        }

    # --- Pre-check: GNU Make >= 4.0 ---
    import re
    make_cmd = "make"
    r = subprocess.run(["make", "--version"], capture_output=True, text=True)
    first_line = r.stdout.splitlines()[0] if r.stdout else ""
    m = re.search(r"(\d+)\.(\d+)", first_line)
    if m and int(m.group(1)) < 4:
        # make too old, try gmake (Homebrew on macOS)
        if shutil.which("gmake"):
            make_cmd = "gmake"
        else:
            return {
                "returncode": -1,
                "warnings": [],
                "errors": [f"GNU Make >= 4.0 required, found {m.group(0)}"],
                "skipped": True,
                "skip_reason": f"GNU Make >= 4.0 required (found {m.group(0)})",
            }

    # --- Clean if requested ---
    if clean:
        subprocess.run(
            [make_cmd, "cleandocs"],
            cwd=str(kernel_dir),
            capture_output=True,
        )

    # --- Run htmldocs ---
    nproc = os.cpu_count() or 1
    r = subprocess.run(
        [make_cmd, "htmldocs", f"SPHINXOPTS=-j{nproc}"],
        cwd=str(kernel_dir),
        capture_output=True,
        text=True,
    )
    output = r.stdout + r.stderr
    warnings = []
    errors = []
    for line in output.splitlines():
        if filter_zh_cn and "zh_CN" not in line:
            continue
        upper = line.upper()
        if "ERROR" in upper:
            errors.append(line.strip())
        elif "WARNING" in upper:
            warnings.append(line.strip())

    return {
        "returncode": r.returncode,
        "warnings": warnings,
        "errors": errors,
        "skipped": False,
        "skip_reason": None,
    }
