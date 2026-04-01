# 发送补丁

使用 `bin/kt-send-patch` 发送补丁。三阶段工作流参见 `docs/patch-submission.md`。

> **路径约定**：`<ROOT>` 为项目根目录。

用户必须明确指定阶段。如果没有指定，询问用户要用哪个阶段，并建议从 `--self` 开始。

## 模式 1：`--self`（发给自己测试）

```bash
cd <ROOT> && python3 bin/kt-send-patch --self [额外参数] --json
```

发送后提示用户检查邮箱确认格式。

## 模式 2：`--review <email>`（发给内审人员）

确认 review 邮箱地址后执行：

```bash
cd <ROOT> && python3 bin/kt-send-patch --review <email> [额外参数] --json
```

## 模式 3：`--submit`（正式提交到邮件列表）

**警告**：将发到公开邮件列表。

### 3a. 先 dry-run 预览

```bash
cd <ROOT> && python3 bin/kt-send-patch --submit --dry-run [额外参数] --json
```

展示完整收件人列表和补丁列表。

### 3b. 用户确认

明确告知用户：
- **会发送到公开邮件列表**（linux-doc@vger.kernel.org）
- 完整收件人列表
- 补丁列表

### 3c. 正式发送

用户明确确认后：

```bash
cd <ROOT> && python3 bin/kt-send-patch --submit [额外参数] --json
```

## Series 集成

如果指定了 `--series <id>`（或当前在 `zh-work/*` 分支时自动推断）：
- 从 `outgoing/<series-id>/` 查找补丁（兼容旧的 `outgoing/*.patch`）
- `bin/kt-send-patch` 自动从 series-state.json 读取配置
- v2+ 自动带 `--in-reply-to`
- 发送后自动更新 series-state（新 round、status=sent）

## 安全提醒

- `--self`: 无风险
- `--review`: 会发邮件给他人，确认地址
- `--submit`: **公开邮件列表**，必须先通过 `--self` 和 `--review` 测试

收件人信息参见 `docs/recipients.md`。
