# Patch Series Lifecycle

## Overview

A patch series progresses through a defined lifecycle from initial translation
to final merge into the kernel tree:

```
Translation -> Check -> Patch -> Self-test
  -> Internal review circle: v1 -> feedback -> revise -> v2 -> ... -> vN -> approved
  -> Upstream circle: v1 (with Reviewed-by) -> feedback -> ... -> vN -> merged
```

Key rule: the upstream submission **resets to v1**. Reviewed-by tags collected
during internal review are embedded into the commit messages before upstream
submission.

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
                "reviewed_by": [],
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
| internal_review   | upstream  | All patches approved         | Collect Reviewed-by, soft reset commits, re-commit with tags, re-format-patch (v1) |
| upstream          | merged    | Maintainer applies the patch | Mark phase as merged            |

### Transition: internal_review to upstream

1. Collect all `Reviewed-by` tags from the latest internal review round.
2. Soft reset commits back to the docs-next base.
3. Re-commit each file with `Reviewed-by` lines inserted before `Signed-off-by`.
4. Regenerate patches as v1 (no `--reroll-count`), since upstream versioning
   starts fresh.
5. Update series state: `internal_review.status = "approved"`,
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
- `per_patch`: Per-patch feedback status, reviewer tags, and action items.

## Reviewed-by Collection

When advancing from internal review to upstream:

- All `reviewed_by` entries from the latest round's `per_patch` are collected.
- These tags are inserted into the commit message of each corresponding patch,
  on separate lines before `Signed-off-by`.
- This ensures upstream reviewers can see that the patch has already been
  reviewed internally.
