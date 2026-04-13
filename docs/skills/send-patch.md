# 发送补丁

使用 `bin/kt-send-patch` 发送补丁。三阶段工作流参见 `docs/patch-submission.md`。

> **路径约定**：`<ROOT>` 为项目根目录。

用户必须明确指定阶段。如果没有指定，询问用户要用哪个阶段，并建议从 `--self` 开始。

## 确认规则（所有模式通用）

**禁止 Claude 执行发送。** 所有模式都必须：
1. 先不带 `--confirm` 运行，获取预览（收件人、补丁列表、`command` 字段）
2. 展示预览信息给用户
3. 从 JSON 输出的 `command` 字段提取 `git send-email` 原始命令，贴给用户自己执行

## 模式 1：`--self`（发给自己测试）

```bash
cd <ROOT> && python3 bin/kt-send-patch --self [额外参数] --json
```

展示收件人和补丁列表，把 `command` 字段的 `git send-email` 命令贴给用户执行。发送后提示用户检查邮箱确认格式。

## 模式 2：`--review <email>`（发给内审人员）

确认 review 邮箱地址后：

```bash
cd <ROOT> && python3 bin/kt-send-patch --review <email> [额外参数] --json
```

展示收件人和补丁列表，把 `command` 字段的 `git send-email` 命令贴给用户执行。

## 模式 3：`--submit`（正式提交到邮件列表）

**警告**：将发到公开邮件列表。

```bash
cd <ROOT> && python3 bin/kt-send-patch --submit [额外参数] --json
```

展示完整收件人列表和补丁列表，明确告知用户：
- **会发送到公开邮件列表**（linux-doc@vger.kernel.org）
- 完整收件人列表
- 补丁列表

把 `command` 字段的 `git send-email` 命令贴给用户执行。

## Series 集成

如果指定了 `--series <id>`（或当前在 `zh-work/*` 分支时自动推断）：
- 从 `outgoing/<series-id>/` 查找补丁（兼容旧的 `outgoing/*.patch`）
- `bin/kt-send-patch` 自动从 series-state.json 读取配置
- v2+ 自动带 `--in-reply-to`
- 发送后自动更新 series-state（新 round、status=sent）

## 收件人筛选（--submit 模式）

`get_maintainer.pl` 会基于补丁内容的关键词匹配收件人。翻译补丁包含各子系统的术语（如 riscv、clang、llvm），会导致大量**不相关的 maintainer/reviewer** 被误匹配。

展示收件人列表时，必须提醒用户根据翻译内容筛选，排除不相关的人：

- **保留**：`CHINESE DOCUMENTATION`（maintainer + reviewer）、`DOCUMENTATION`（maintainer + reviewer）、相关邮件列表（open list）
- **排除**：`commit_signer`（仅因相邻目录活跃）、`removed_lines`（补丁作者自己）、因关键词误匹配的其他子系统 maintainer/reviewer（如翻译 Rust 文档不需要 To RISC-V maintainer）
- **酌情保留**：翻译主题对应子系统的 maintainer（如翻译 Rust 文档可考虑 Cc rust-for-linux 列表）

## 安全提醒

- `--self`: 无风险
- `--review`: 会发邮件给他人，确认地址
- `--submit`: **公开邮件列表**，必须先通过 `--self` 和 `--review` 测试

收件人信息参见 `docs/recipients.md`。
