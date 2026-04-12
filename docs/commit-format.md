# Commit Message Format for Kernel Translation Patches

Reference: <https://docs.kernel.org/translations/zh_CN/how-to.html>

## Structure

Every commit message consists of exactly **4 sections**, separated by blank
lines. All four are mandatory.

```
1. Subject line          docs/zh_CN: Add/Update <subject>
2. Description           Translate/Update ... into Chinese.
3. Through-commit        Translate/Update through commit <hash> ("<subject>")
4. Signed-off-by         Signed-off-by: Your Name <your@email.com>
```

### Field Details

| # | Field          | Purpose                                              |
|---|----------------|------------------------------------------------------|
| 1 | Subject        | Concise summary with `docs/zh_CN:` prefix            |
| 2 | Description    | One sentence describing what was translated/updated   |
| 3 | Through-commit | The English source commit this translation is based on|
| 4 | Signed-off-by  | Developer Certificate of Origin sign-off              |

## New Translation Example

```
docs/zh_CN: Add admin-guide/README Chinese translation

Translate Documentation/admin-guide/README.rst into Chinese.

Translate through commit a1b2c3d
("docs: update README formatting")

Signed-off-by: Zhang San <zhangsan@example.com>
```

## Update Translation Example

```
docs/zh_CN: Update admin-guide/README.rst translation

Update the translation of .../admin-guide/README.rst into Chinese.

Update the translation through commit a1b2c3d
("docs: update README formatting")

Signed-off-by: Zhang San <zhangsan@example.com>
```

## Rules

- Use `Add` in the subject for new translations; use `Update` for revisions.
- The through-commit hash and subject must refer to the **latest commit** that
  touched the English source file at the time of translation.
- **不能引用 merge commit**。必须找到实际修改文件内容的 commit。
  例如 `a592a36e4937 ("Documentation: use a source-read extension ...")` 是正确的，
  而 `a9aabb3b839a ("Merge tag 'rust-6.20-7.0' ...")` 是错误的。
- The `Signed-off-by` line uses the name and email from your git configuration.
- When a patch receives review tags (`Reviewed-by`, `Acked-by`, etc.) during
  review, insert them on separate lines immediately **before** the
  `Signed-off-by` line.
