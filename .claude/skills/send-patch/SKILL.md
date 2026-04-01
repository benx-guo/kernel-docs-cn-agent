---
name: send-patch
description: Send translation patches via email (three-stage workflow)
disable-model-invocation: true
allowed-tools: Bash, Read
argument-hint: "<--self | --review <email> | --submit> [--dry-run] [--in-reply-to <id>] [--series <id>]"
---

# 发送补丁

通过三阶段流程发送翻译补丁，不调用外部脚本。

> **路径约定**：Bash cwd 可能被污染，**不可假设为项目根目录**。
> 项目根目录（`<ROOT>`）从 skill 的 Base directory 推导：`Base directory` 往上 3 级。
> 每条 Bash 命令用 `cd <ROOT>/linux && ...` 或 `cd <ROOT> && ...` 显式切换。

用户必须明确指定阶段。如果没有指定，询问用户要用哪个阶段，并建议从 `--self` 开始。

解析 `$ARGUMENTS`：提取 `--self`、`--review <email>`、`--submit`、`--dry-run`、`--in-reply-to <id>`、`--series <id>`。

## Series 集成

如果指定了 `--series <id>`：

1. 读取 `<ROOT>/scripts/series-state.json`，找到对应系列
2. **自动填充收件人**：
   - 如果 phase=internal_review → `--review` 模式的内审收件人
   - 如果 phase=upstream → `--submit` 模式的上游收件人
3. **v2+ 自动带 `--in-reply-to`**：如果当前 phase 已有 rounds，取第一轮的 cover_message_id 作为 in-reply-to
4. **发送后更新 series-state**：
   - 提取 cover letter 的 Message-ID（从 git send-email 输出中解析）
   - 在当前 phase 的 rounds 中创建新 round
   - 更新 phase status 为 `sent`

```bash
python3 -c "
import json
from datetime import datetime, timezone
with open('<ROOT>/scripts/series-state.json') as f: data = json.load(f)
s = data['series']['<id>']
phase_data = s['phases'][s['phase']]
phase_data['status'] = 'sent'
version = len(phase_data['rounds']) + 1
per_patch = {}
for i, f_path in enumerate(s['files'], 1):
    per_patch[str(i)] = {'file': f_path, 'status': 'no_feedback', 'reviewed_by': [], 'action_items': []}
phase_data['rounds'].append({
    'version': version,
    'sent_at': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
    'cover_message_id': '<extracted-message-id>',
    'per_patch': per_patch
})
with open('<ROOT>/scripts/series-state.json', 'w') as f: json.dump(data, f, ensure_ascii=False, indent=2); f.write('\n')
"
```

## 前置检查

### 1. 确认补丁存在

```bash
ls <ROOT>/outgoing/*.patch 2>/dev/null
```

如果没有补丁，告知用户先运行 `/format-patch`。

### 2. 确认 git send-email 可用

```bash
git send-email --help >/dev/null 2>&1 && echo "ok"
```

如不可用，提示安装：`sudo dnf install git-email` 或 `sudo apt install git-email`。

### 3. 加载邮件配置

```bash
test -f <ROOT>/config/email.conf && cat <ROOT>/config/email.conf
```

### 4. 获取用户邮箱

```bash
cd <ROOT>/linux && git config user.email
```

---

## 模式 1：`--self`（发给自己测试）

构建命令：

```bash
cd <ROOT>/linux && git send-email --to="<user_email>" --confirm=never <ROOT>/outgoing/*.patch
```

如果有 `--dry-run`，加 `--dry-run` 参数。

发送后提示用户检查邮箱确认格式。

## 模式 2：`--review <email>`（发给内审人员）

确认 review 邮箱地址。构建命令：

```bash
cd <ROOT>/linux && git send-email --to="<review_email>" --cc="<user_email>" --confirm=never <ROOT>/outgoing/*.patch
```

## 模式 3：`--submit`（正式提交到邮件列表）

### 3a. 收集收件人

检查 `get_maintainer.pl`：

```bash
test -x <ROOT>/linux/scripts/get_maintainer.pl && echo "exists"
```

**如果存在**：对每个非 cover-letter 补丁运行：

```bash
cd <ROOT>/linux && perl scripts/get_maintainer.pl --no-rolestats <ROOT>/outgoing/<patch>
```

将 maintainer/supporter 归为 To，其他归为 Cc。

**始终添加**：
- To: `Alex Shi <alexs@kernel.org>`
- Cc: `linux-doc@vger.kernel.org`

去重后构建收件人列表。

### 3b. 必须先 dry-run

**无论用户是否指定 `--dry-run`**，`--submit` 阶段都先执行 dry-run：

```bash
cd <ROOT>/linux && git send-email --dry-run --to=<to1> --to=<to2> --cc=<cc1> --cc=<cc2> --confirm=never <ROOT>/outgoing/*.patch
```

展示完整收件人列表和补丁列表给用户。

### 3c. 确认后正式发送

用 `AskUserQuestion` 明确告知：
- **会发送到公开邮件列表**
- 完整收件人列表
- 补丁列表

用户明确确认后才执行正式发送（不带 `--dry-run`）。

## `--in-reply-to` 支持

如果指定了 `--in-reply-to <id>`，处理 message-id 格式（去掉/添加尖括号）：

在发送命令中加入 `--in-reply-to="<message-id>"`。

## 安全提醒

- `--self`: 无风险，随时可以运行
- `--review`: 会发送邮件给他人，确认收件人地址
- `--submit`: **会发送到公开邮件列表**，必须先通过 `--self` 和 `--review` 测试

发送成功后，用中文汇报结果并建议下一步。
