# Patch Submission Process

## Three-Stage Workflow

Patch submission follows three stages of increasing scope. Each stage must
be completed before moving to the next.

### Stage 1: `--self` (Send to Yourself)

- **Purpose**: Verify patch formatting and email delivery.
- **Risk level**: None. Only sends to your own email address.
- **Action**: Send all patches in `outgoing/` to the address from
  `git config user.email`.

### Stage 2: `--review <email>` (Send to Internal Reviewer)

- **Purpose**: Get feedback from a trusted reviewer before public submission.
- **Risk level**: Low. Sends to a specific individual.
- **Action**: Send patches to the specified reviewer email, with yourself
  on CC.

### Stage 3: `--submit` (Submit to Mailing List)

- **Purpose**: Submit patches to the public kernel mailing list for upstream
  review and acceptance.
- **Risk level**: High. Emails are sent to a public mailing list and archived
  permanently.
- **Action**: Send patches to maintainers and the documentation mailing list.

## Dry-Run Requirement

The `--submit` stage **always** performs a dry-run first, regardless of
whether `--dry-run` was explicitly requested. The dry-run output displays:

- The complete recipient list (To and CC).
- The list of patches that will be sent.

Only after the user explicitly confirms the dry-run preview does the actual
send proceed.

## In-Reply-To for v2+ Patches

When submitting a revised patch series (v2 or later), use `--in-reply-to`
with the Message-ID of the original cover letter. This threads the new
version under the original discussion on the mailing list.

The Message-ID is stored in `series-state.json` as `cover_message_id` in
the first round of the relevant phase.

## Recipient Detection with get_maintainer.pl

For `--submit`, recipients are determined by running the kernel's
`scripts/get_maintainer.pl` against each non-cover-letter patch:

```
perl scripts/get_maintainer.pl --no-rolestats <patch-file>
```

- Maintainers and supporters are added to the **To** field.
- Other listed addresses are added to the **CC** field.
- The Chinese documentation maintainer and documentation mailing list are
  always included (see `docs/recipients.md`).

Duplicate addresses are removed before sending.
