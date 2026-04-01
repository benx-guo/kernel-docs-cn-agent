# Translation Workflow

## 7-Stage Overview

The kernel translation process follows seven high-level stages:

| Stage | Name         | Description                                       |
|-------|--------------|---------------------------------------------------|
| 1     | Setup        | Clone the docs-next branch, create a work branch  |
| 2     | Diff         | Compare English source with existing translations  |
| 3     | Translate    | Perform the actual translation work                |
| 4     | Check        | Run quality checks (line width, RST, whitespace)   |
| 5     | Format-patch | Commit changes and generate patch files            |
| 6     | Send-patch   | Send patches through the three-stage email flow    |
| 7     | Work         | Orchestrate the full pipeline end-to-end           |

## 12-Stage Pipeline

The full orchestrated pipeline (stage 7 above) breaks down into 12 granular
stages with two review circles:

```
1(CHK) -> 2(TL) -> 3(QA) -> 4(PAT) -> 5(E1) -> 6(E2)
                                                   |
                                           +-- 7(W1) <--+
                                           |    |        |
                                           |  8(RV1) ----+  Internal review circle
                                           |    | (approved)
                                           +-> 9(E3)
                                                 |
                                          +-- 10(W2) <--+
                                          |     |        |
                                          |  11(RV2) ----+  Mailing list review circle
                                          |     | (accepted)
                                          +-> 12(ARC)
```

## Stage Descriptions

| # | Code | Name                  | Description                                    |
|---|------|-----------------------|------------------------------------------------|
| 1 | CHK  | Check                 | Determine if file needs new translation or update |
| 2 | TL   | Translate             | Execute translation following all rules         |
| 3 | QA   | Quality Assurance     | Line width, trailing whitespace, line endings   |
| 4 | PAT  | Patch                 | Git commit + format-patch + checkpatch + htmldocs |
| 5 | E1   | Email Self            | Send patch to yourself for format verification  |
| 6 | E2   | Email Reviewer        | Send patch to internal reviewer                 |
| 7 | W1   | Wait Internal Review  | Wait for internal reviewer feedback             |
| 8 | RV1  | Revise (Internal)     | Address internal review feedback, re-send       |
| 9 | E3   | Email Upstream        | Submit to the public mailing list               |
| 10| W2   | Wait Upstream Review  | Wait for mailing list feedback                  |
| 11| RV2  | Revise (Upstream)     | Address upstream feedback, re-send as vN        |
| 12| ARC  | Archive               | Record completion, report summary               |

## Review Circles

### Internal Review Circle (Stages 7-8)

Stages 7 and 8 form a loop. After sending patches to an internal reviewer
(stage 6), the process waits for feedback (stage 7). If changes are requested,
the translation is revised and re-sent (stage 8), then returns to stage 7.
When the reviewer approves, the process advances to stage 9.

### Mailing List Review Circle (Stages 10-11)

Stages 10 and 11 form the same pattern for upstream review. After submitting
to the mailing list (stage 9), the process waits for community feedback
(stage 10). If changes are requested, a new patch version is prepared and
re-sent (stage 11), then returns to stage 10. When the maintainer accepts
(or applies the patch), the process moves to archival (stage 12).

## Recovery and Resumption

Each file's progress is tracked in `data/workflow-state.json` with its
current stage number. If the workflow is interrupted, it resumes from the
last recorded stage:

| Saved Stage | Recovery Action                                          |
|-------------|----------------------------------------------------------|
| 2           | Check git diff for existing translation changes          |
| 4           | Check git log for existing commits                       |
| 5-6         | Ask if previous send was successful                      |
| 7 / 10      | Ask if a reply has been received                         |
| 8 / 11      | Check if revision edits already exist                    |

The user is always informed of the recovery point and asked to confirm
before continuing.

## Batch Mode

Multiple files can be processed together using `--batch N`:

- **Stages 1-3 (translate)**: Run in parallel, up to 3 files concurrently.
- **Stage 4 (patch)**: Wait for all translations to finish, then commit all
  files and generate patches with a cover letter.
- **Stages 5-12 (email/review)**: Proceed serially, as email operations
  require user confirmation.
