# Patch Series Lifecycle

## Overview

A patch series progresses through a defined lifecycle from initial translation
to final merge into the kernel tree:

```
Translation -> Check -> Patch -> Self-test
  -> Internal review circle: v1 -> feedback -> revise -> v2 -> ... -> vN -> approved
  -> Upstream circle: v1 -> feedback -> ... -> vN -> merged
```

Key rule: the upstream submission **resets to v1**. Internal review tags are
**not** carried over — upstream reviewers give their own tags on the public
mailing list.

## State Schema

Series state is stored in `data/series-state.json`:

```json
{
  "version": 1,
  "series": {
    "<series-id>": {
      "subject": "commit subject prefix",
      "files": ["path/relative/to/zh_CN/"],
      "commits": ["hash1", "hash2"],
      "phase": "internal_review | upstream | merged",
      "follow_up": [
        {"file": "path", "description": "...", "waiting_for": "..."}
      ],
      "phases": {
        "internal_review": {
          "status": "pending | sent | feedback_received | revising | approved",
          "rounds": [{
            "version": 1,
            "sent_at": "YYYY-MM-DD",
            "cover_message_id": "message-id-without-angle-brackets",
            "per_patch": {
              "1": {
                "file": "...",
                "status": "approved | changes_requested | no_feedback",
                "tags": [],
                "action_items": []
              }
            }
          }]
        },
        "upstream": {
          "status": "pending | sent | feedback_received | revising | merged",
          "rounds": []
        }
      }
    }
  }
}
```

### Series ID Format

Generated from the subdirectory and date: `<subdir>-YYYY-MM`
(e.g., `rust-subsystem-2026-03`).

## Phase Transitions

| From              | To        | Trigger                      | Actions                         |
|-------------------|-----------|------------------------------|---------------------------------|
| internal_review   | upstream  | All patches approved         | Soft reset commits, re-commit, re-format-patch (v1) |
| upstream          | merged    | Maintainer applies the patch | Mark phase as merged            |

### Transition: internal_review to upstream

1. Soft reset commits back to the docs-next base.
2. Re-commit each file (no internal review tags — only `Signed-off-by`).
3. Regenerate patches as v1 (no `--reroll-count`), since upstream versioning
   starts fresh.
4. Update series state: `internal_review.status = "approved"`,
   `phase = "upstream"`, `upstream.status = "pending"`.

## Round Versioning

Each review circle tracks rounds independently:

- **Internal review**: Versions increment (v1, v2, v3, ...) within the
  `internal_review.rounds` array.
- **Upstream**: Versions **reset to v1** when transitioning from internal
  review. Subsequent upstream revisions increment from there (v1, v2, ...).

Each round records:

- `version`: The patch version number for that round.
- `sent_at`: The date the patches were sent.
- `cover_message_id`: The Message-ID of the cover letter (used for
  `--in-reply-to` threading in subsequent versions).
- `per_patch`: Per-patch feedback status, tags, and action items.

## Tag Collection

Tags (`Reviewed-by`, `Acked-by`, etc.) are stored as complete tag lines in
`per_patch.tags` — e.g., `"Reviewed-by: Name <email>"`. This keeps the format
consistent with commit messages and avoids needing to distinguish tag types.

Internal review tags are **not** embedded into upstream commits. Internal
review is for quality assurance only — reviewers give their tags independently
on the public mailing list.

Upstream review tags (Reviewed-by, Acked-by, etc.) are collected from mailing
list replies and embedded into commits when preparing the next version (vN).
