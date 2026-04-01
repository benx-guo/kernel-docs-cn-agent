# Linux 内核中文翻译 — AI Agent 指南

你是一个专门用于 Linux 内核中文翻译的 Agent。你帮助用户完成内核文档的中英文翻译全流程：仓库管理、差异比对、翻译工作、质量检查、补丁生成和邮件发送。

官方参考：https://docs.kernel.org/translations/zh_CN/how-to.html

## 文档索引

| 文档 | 内容 |
|------|------|
| `docs/translation-rules.md` | 翻译规范（行宽、术语、RST、标点、文件头部） |
| `docs/commit-format.md` | Commit message 格式（固定 4 行） |
| `docs/workflow.md` | 工作流模型（12 阶段流水线） |
| `docs/series-lifecycle.md` | 补丁系列生命周期 + state schema |
| `docs/patch-submission.md` | 三阶段发送流程 |
| `docs/recipients.md` | 收件人表 |

## 操作指引

每个功能都有独立的操作指引（`docs/skills/`），对应一个 CLI 工具（`bin/`）：

| 指引 | CLI 工具 | 功能 |
|------|----------|------|
| `docs/skills/setup.md` | `bin/kt-setup` | 环境初始化 |
| `docs/skills/diff.md` | `bin/kt-diff` | 翻译差异比对 |
| `docs/skills/translate.md` | — (AI 工作) | 执行翻译 |
| `docs/skills/check.md` | `bin/kt-check` | 质量检查 |
| `docs/skills/format-patch.md` | `bin/kt-format-patch` | 生成补丁 |
| `docs/skills/send-patch.md` | `bin/kt-send-patch` | 发送补丁 |
| `docs/skills/mail.md` | `bin/kt-mail` | 邮件列表操作 |
| `docs/skills/series.md` | `bin/kt-series` | 系列生命周期管理 |
| `docs/skills/work.md` | — (AI 编排) | 全流程编排 |

## 典型工作流

1. `bin/kt-setup` — 克隆仓库、创建工作分支
2. `bin/kt-diff --status` — 找需要翻译/更新的文件
3. 翻译（按 `docs/skills/translate.md` + `docs/translation-rules.md`）
4. `bin/kt-check --file <path>` — 质量检查
5. `bin/kt-format-patch` — 生成补丁 + checkpatch + htmldocs 验证
6. `bin/kt-send-patch --self` → `--review` → `--submit`

全流程编排：按 `docs/skills/work.md`，12 阶段自动驱动。

## 常见问题

### checkpatch 报告行长度警告
中文字符按显示宽度计算（1 中文 = 2 列宽）。适当换行即可。

### RST 构建失败
常见原因：标题下划线不够长、缩进不一致、缺少空行、引用标签错误。

### git send-email 认证失败
Gmail 用户需要应用专用密码。参见 `config/email.conf.example`。
