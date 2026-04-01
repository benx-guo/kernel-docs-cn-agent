---
name: series
description: Manage patch series lifecycle — track review rounds, feedback, and Reviewed-by across internal and upstream review cycles
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, AskUserQuestion
argument-hint: "<--list | --show <id> | --create | --check-feedback [id] | --prepare-next [id] | --advance [id] | --dashboard>"
---

# 补丁系列生命周期管理

管理补丁系列从翻译到合并的完整生命周期，跟踪内审和上游两个 review 循环。

> **路径约定**：Bash cwd 可能被污染，**不可假设为项目根目录**。
> 项目根目录（`<ROOT>`）从 skill 的 Base directory 推导：`Base directory` 往上 3 级。
> 每条 Bash 命令用 `cd <ROOT>/linux && ...` 或 `cd <ROOT> && ...` 显式切换。

## 生命周期模型

```
翻译 → 检查 → 补丁 → 自审
→ 内审循环（hust-os-kernel-patches）：v1 → 反馈 → 修改 → v2 → ... → vN → 通过
→ 上游循环（linux-doc@vger.kernel.org）：v1（带 Reviewed-by）→ 反馈 → ... → vN → 合并
```

上游重置为 v1，内审 Reviewed-by 写入 commit。

## 状态文件

`<ROOT>/scripts/series-state.json`，结构：

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
              "1": { "file": "...", "status": "approved|changes_requested|no_feedback", "reviewed_by": [], "action_items": [] }
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

## 参数解析

解析 `$ARGUMENTS`：提取 `--list`、`--show <id>`、`--create`、`--check-feedback [id]`、`--prepare-next [id]`、`--advance [id]`、`--dashboard`。

如果没有指定参数，默认执行 `--list`。

---

## 模式 1：`--list` — 列出所有活跃系列

读取 `<ROOT>/scripts/series-state.json`。

对每个系列，显示：

```
<id>
  主题: <subject>
  阶段: <phase> / <phase_status>
  文件: <N> 个
  当前版本: v<latest_round_version>
  待处理: <action_items_count> 个 action items
```

过滤掉 phase=merged 的系列（除非没有其他活跃系列）。

---

## 模式 2：`--show <id>` — 详细查看一个系列

读取 series-state.json，找到指定 id 的系列。

显示：
1. **基本信息**：subject, phase, files
2. **当前阶段详情**：
   - 当前 phase 的 status
   - 最新 round 的 version、sent_at、cover_message_id
3. **每个补丁的状态**：
   - 文件名
   - 状态（approved / changes_requested / no_feedback）
   - Reviewed-by 列表
   - Action items（如有）
4. **历史轮次摘要**：每轮的版本号和日期

---

## 模式 3：`--create` — 创建新系列

### 3a. 收集信息

从 outgoing/ 补丁和 git log 创建新系列：

```bash
ls <ROOT>/outgoing/*.patch 2>/dev/null
```

```bash
cd <ROOT>/linux && git log --oneline docs-next..HEAD
```

### 3b. 生成系列 ID

从 commit subject 和日期生成 ID：
- 提取文件路径中的子目录（如 `rust/`, `admin-guide/`）
- 格式：`<subdir>-YYYY-MM`（如 `rust-subsystem-2026-03`）

### 3c. 构建系列数据

用 AskUserQuestion 确认：
- 系列 ID
- Subject
- 文件列表

### 3d. 写入 series-state.json

```python
import json
from datetime import datetime, timezone

with open('<ROOT>/scripts/series-state.json') as f:
    data = json.load(f)

data['series']['<id>'] = {
    "subject": "<subject>",
    "files": [<files>],
    "commits": [<commit_hashes>],
    "phase": "internal_review",
    "phases": {
        "internal_review": { "status": "pending", "rounds": [] },
        "upstream": { "status": "pending", "rounds": [] }
    }
}

with open('<ROOT>/scripts/series-state.json', 'w') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
    f.write('\n')
```

---

## 模式 4：`--check-feedback [id]` — 检查邮件反馈

### 4a. 确定系列

如果未指定 id，自动选择 phase 不是 merged 且 status 为 sent 或 feedback_received 的系列。如果有多个，用 AskUserQuestion 让用户选。

### 4b. 同步邮件

```bash
mbsync -a 2>&1 | tail -5
```

```bash
notmuch new 2>&1
```

### 4c. 搜索回复

获取当前 phase 最新 round 的 cover_message_id：

```bash
notmuch search "thread:{id:<cover_message_id>}" 2>&1
```

如果找到线程，获取所有回复：

```bash
notmuch show --format=json "thread:{id:<cover_message_id>}" 2>&1
```

### 4d. 解析反馈

用 Python 提取线程中的回复：

```bash
notmuch show --format=json "thread:{id:<cover_message_id>}" 2>&1 | python3 -c "
import json, sys, re
data = json.load(sys.stdin)
def walk(msgs):
    for msg in msgs:
        if isinstance(msg, list):
            walk(msg)
        elif isinstance(msg, dict):
            hdrs = msg.get('headers', {})
            frm = hdrs.get('From', '?')
            subj = hdrs.get('Subject', '?')
            mid = hdrs.get('Message-ID', '?')
            irt = hdrs.get('In-Reply-To', '')
            body_parts = msg.get('body', [])
            body_text = ''
            for part in body_parts:
                if part.get('content-type','').startswith('text/plain'):
                    body_text = part.get('content', '')
                elif 'content' in part and isinstance(part['content'], list):
                    for sub in part['content']:
                        if isinstance(sub, dict) and sub.get('content-type','').startswith('text/plain'):
                            body_text = sub.get('content', '')
            if irt:  # Only replies
                print(f'=== REPLY ===')
                print(f'From: {frm}')
                print(f'Subject: {subj}')
                print(f'Message-ID: {mid}')
                print(f'In-Reply-To: {irt}')
                # Check for Reviewed-by
                for line in body_text.split('\n'):
                    if 'Reviewed-by:' in line:
                        print(f'REVIEWED-BY: {line.strip()}')
                print(f'---BODY---')
                print(body_text[:800])
                print(f'---END---')
                print()
walk(data)
"
```

### 4e. Claude 分析并更新状态

根据获取到的回复，Claude 分析每个回复：

1. **判断回复对应哪个补丁**：从 Subject 中的 `[PATCH N/M]` 或 In-Reply-To 的 message-id 关联
2. **提取 Reviewed-by**：如果回复中包含 `Reviewed-by:` 行
3. **提取修改意见**：如果回复中有具体的修改建议或问题
4. **判断状态**：
   - 有 `Reviewed-by:` → `approved`
   - 有修改意见 → `changes_requested`，记录 action_items
   - 无实质内容 → 保持原状态

用 `Edit` 更新 `series-state.json` 中对应 round 的 per_patch 数据。

### 4f. 汇报

用中文汇报：
- 同步了多少新邮件
- 找到多少条回复
- 每个补丁的反馈摘要
- 当前整体状态

---

## 模式 5：`--prepare-next [id]` — 准备下一轮修改

### 5a. 读取状态

读取 series-state.json，找到指定系列当前 phase 最新 round。

### 5b. 列出 action items

汇总所有 per_patch 中 status=changes_requested 的补丁及其 action_items。

### 5c. 展示修改计划

用中文列出需要修改的内容：

```
需要修改的补丁：

1. [PATCH 2/4] rust/coding-guidelines.rst
   - 代码块注释保留英文原文

2. [PATCH 4/4] rust/index.rst
   - commit 引用改为 a592a36e4937
```

### 5d. 更新状态

将当前 phase 的 status 设为 `revising`。

用 `Edit` 更新 series-state.json。

提议：_"以上是需要修改的内容。是否开始修改？（可以用 `/translate <file>` 逐个修改）"_（AskUserQuestion）

---

## 模式 6：`--advance [id]` — 推进阶段

### 6a. 读取状态

读取 series-state.json，确认当前 phase 和 status。

### 6b. 内审 → 上游

**前置条件**：phase=internal_review, status=approved 或用户确认推进。

1. **收集所有 Reviewed-by**：
   遍历最新 round 的 per_patch，收集所有 reviewed_by。

2. **Soft reset commits**：
   ```bash
   cd <ROOT>/linux && git log --oneline docs-next..HEAD
   ```
   确认 commit 数量后：
   ```bash
   cd <ROOT>/linux && git reset --soft docs-next
   ```

3. **重新 commit 带 Reviewed-by**：
   对每个文件重新 commit，在 commit message 中加入对应的 Reviewed-by tag。

   对于每个文件：
   ```bash
   cd <ROOT>/linux && git add Documentation/translations/zh_CN/<file>
   ```

   Commit message 中在 Signed-off-by 之前插入 Reviewed-by 行：
   ```
   docs/zh_CN: Add/Update <path> translation

   Translate/Update Documentation/<path> into Chinese.

   Translate/Update through commit <hash> ("<subject>")

   Reviewed-by: Name <email>
   Signed-off-by: Your Name <your@email.com>
   ```

4. **重新 format-patch**：
   ```bash
   rm -rf <ROOT>/outgoing && mkdir -p <ROOT>/outgoing
   ```
   ```bash
   cd <ROOT>/linux && git format-patch docs-next..HEAD -o <ROOT>/outgoing --cover-letter --thread=shallow
   ```
   （上游 v1，不加 --reroll-count）

5. **更新状态**：
   - internal_review.status = "approved"
   - phase = "upstream"
   - upstream.status = "pending"
   - 更新 commits 为新的 hash

用 `Edit` 更新 series-state.json。

### 6c. 上游 → 合并

**前置条件**：phase=upstream, status=approved 或用户确认。

- phase = "merged"
- 汇报完成

### 6d. 安全确认

每次 advance 前用 AskUserQuestion 确认：
- 当前阶段 → 目标阶段
- 将要执行的操作（soft reset, rebase, etc.）

---

## 模式 7：`--dashboard` — 全景面板

读取 `<ROOT>/scripts/series-state.json`，在对话中直接渲染格式化面板。

对**每个活跃系列**（phase ≠ merged），按以下模板输出：

````
## 📋 <series-id>

**<subject>**

| 字段 | 值 |
|------|----|
| 阶段 | <phase> |
| 状态 | <current phase status> |
| 文件 | <N> 个 |
| 版本 | v<latest round version>（<sent_at>） |

### 补丁状态

| # | 文件 | 状态 | Reviewed-by |
|---|------|------|-------------|
| 1 | rust/arch-support.rst | ✅ approved | Dongliang Mu |
| 2 | rust/coding-guidelines.rst | ❌ changes_requested | — |
| 3 | rust/quick-start.rst | ⏳ no_feedback | — |
| 4 | rust/index.rst | ❌ changes_requested | — |

### 待办事项

- [ ] 代码块注释保留英文原文（patch 2）
- [ ] commit 引用改为 a592a36e4937（patch 4）

### 生命周期

`翻译 ✓ → 检查 ✓ → 补丁 ✓ → 自审 ✓ → 【内审】 → 上游 → 合并`
````

**状态图标映射**：approved → ✅，changes_requested → ❌，no_feedback → ⏳

**生命周期阶段映射**：
- phase=internal_review → 高亮"内审"，之前的阶段标 ✓
- phase=upstream → 高亮"上游"
- phase=merged → 高亮"合并"

如果没有活跃系列，输出：_"当前没有活跃的补丁系列。用 `/series --create` 创建新系列。"_

如果有多个系列，逐个输出，之间用 `---` 分隔。

---

## 错误处理

- 如果 series-state.json 不存在，提示运行 `/setup`
- 如果指定的 series id 不存在，列出可用 id
- 如果 mbsync 或 notmuch 不可用，提示安装并配置
- 如果 notmuch 搜索无结果，告知用户暂无回复

## 注意事项

- 所有向用户的汇报使用中文
- message-id 存储时不带尖括号，使用时按需添加
- `--check-feedback` 同时支持 notmuch 本地邮件和 lore.kernel.org 远程查询（本地优先）
- `--advance` 的 soft reset + recommit 是破坏性操作，必须用户确认
