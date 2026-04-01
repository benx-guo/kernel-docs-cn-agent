---
name: work
description: Orchestrate the full translation workflow — check, translate, patch, review circles, and submission
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, AskUserQuestion, WebFetch, Agent
argument-hint: "[<file-path>] [--batch N] [--dir <subdir>]"
---

# 翻译全流程编排

自动驱动翻译全流程。每步暂停等用户确认后再继续。所有操作直接使用原生工具，不调用 shell 脚本。

> **路径约定**：Bash cwd 可能被污染，**不可假设为项目根目录**。
> 项目根目录（`<ROOT>`）从 skill 的 Base directory 推导：`Base directory` 往上 3 级。
> 每条 Bash 命令用 `cd <ROOT>/linux && ...` 或 `cd <ROOT> && ...` 显式切换。
> 如果 `<ROOT>/linux/`、`<ROOT>/config/glossary.txt`、`<ROOT>/scripts/workflow-state.json` 不存在，提示用户先运行 `/setup`。

```
1(CHK) → 2(TL) → 3(QA) → 4(PAT) → 5(E1) → 6(E2)
                                                ↓
                                        ┌── 7(W1) ←─┐
                                        │    ↓       │
                                        │  8(RV1) ───┘  内审 circle
                                        │    ↓ (approved)
                                        └→ 9(E3)
                                              ↓
                                       ┌── 10(W2) ←─┐
                                       │     ↓       │
                                       │  11(RV2) ───┘  邮件列表 circle
                                       │     ↓ (accepted)
                                       └→ 12(ARC)
```

## 参数解析

`$ARGUMENTS` 可以是：

| 输入 | 行为 |
|------|------|
| `<file-path>` | 对指定文件走流水线（如 `process/howto.rst`） |
| 空（无参数） | 自动选文件（先查在途，再查 diff） |
| `--batch N` | 选 N 个文件排队处理 |
| `--batch N --dir <subdir>` | 从指定子目录选 N 个文件排队处理 |

文件路径相对于 `Documentation/`（如 `admin-guide/README.rst`）。

### 参数处理步骤

1. 解析 `$ARGUMENTS`，提取 `file`、`--batch N`、`--dir <subdir>`
2. 如果指定了文件：files = [该文件]
3. 如果 `--batch N`：循环 N 次自动选文件，收集 N 个文件
4. 如果无参数：自动选一个文件

---

## 工作流状态管理

**读状态**：

```bash
python3 -c "
import json
with open('<ROOT>/scripts/workflow-state.json') as f: data = json.load(f)
entry = data.get('files', {}).get('<file>')
print(entry['stage'] if entry else 0)
"
```

**写状态**：

```bash
python3 -c "
import json
from datetime import datetime, timezone
with open('<ROOT>/scripts/workflow-state.json') as f: data = json.load(f)
data.setdefault('files', {})['<file>'] = {'stage': <N>, 'updated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')}
with open('<ROOT>/scripts/workflow-state.json', 'w') as f: json.dump(data, f, ensure_ascii=False, indent=2); f.write('\n')
"
```

---

## 自动选文件

替代 `workflow-update.sh next`：

### Step 1：检查在途文件

```bash
python3 -c "
import json
with open('<ROOT>/scripts/workflow-state.json') as f: data = json.load(f)
files = data.get('files', {})
dir_filter = '<dir_filter>'  # 空字符串表示不过滤
candidates = []
for path, info in files.items():
    s = info.get('stage', 0)
    if 1 <= s <= 11:
        if dir_filter and not path.startswith(dir_filter.rstrip('/') + '/'):
            continue
        candidates.append((s, path))
if candidates:
    candidates.sort()
    print(candidates[0][1])
"
```

### Step 2：如果没有在途文件

运行 diff 逻辑找 outdated/missing 文件：
1. 用 `Glob` 获取英文和中文文件列表
2. 计算缺失文件和交集文件
3. 对交集文件检查过期状态（用 git log 对比 commit）
4. 优先选择 outdated（commits behind 最少的），其次 missing

---

## Agent 并行模式（`--batch N`）

### 翻译阶段（1-3）

为每个文件 launch 独立 Agent，最多 3 个并行：

```
Agent(subagent_type="general-purpose", prompt="
你是内核文档中文翻译 agent。请翻译以下文件：

文件：<ROOT>/linux/Documentation/<file>
目标：<ROOT>/linux/Documentation/translations/zh_CN/<file>

1. 读取 <ROOT>/config/glossary.txt 术语表
2. 读取英文原文
3. 如果中文翻译已存在，检查英文变更（git log + git diff）
4. 执行翻译/更新，严格遵守以下规范：
   - 新翻译文件头部（参考 docs.kernel.org/translations/zh_CN/how-to.html）：
     .. SPDX-License-Identifier: GPL-2.0
     .. include:: ../disclaimer-zh_CN.rst
     （空行）
     :Original: Documentation/<path>
     （空行）
     :翻译:
     （空行）
      <姓名> <<邮箱>>
     注意：SPDX 和 include 紧挨无空行；用 :翻译: 不用 :Translator:
   - 行宽 ≤ 80 显示列宽（中文字符 = 2 列宽）
   - 术语使用 glossary.txt，首次出现用"中文（English）"格式
   - 保留代码块、命令、路径、函数名、RST 指令、交叉引用标签
   - 中文标点，中英文/数字间加空格
   - 标题下划线：一个英文一个符号、一个中文两个符号
5. 翻译后运行行宽检查：
   python3 -c \"import unicodedata, sys
   for i, line in enumerate(open(sys.argv[1]), 1):
       w = sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in line.rstrip('\\n'))
       if w > 80: print(f'  Line {i}: width {w}')
   \" <zh_file>
6. 修复所有问题
7. 完成后报告翻译结果
")
```

### 提交阶段（4）

等所有翻译 agent 完成后，在主 context 中统一：
- `git add` 所有翻译文件
- 逐文件 commit（或统一 commit + `--cover-letter`）
- `git format-patch docs-next..HEAD -o <ROOT>/outgoing [--cover-letter]`

### 邮件阶段（5-12）

保持串行，涉及邮件发送需要用户确认。

---

## 单文件模式

不使用 Agent，直接在主 context 中执行全流程。

---

## 恢复机制

每个文件开始前，先读取 workflow-state.json 检查已有状态。

如果返回非 0 stage，从该 stage 恢复：
- stage 2：检查 `git diff` 是否已有翻译修改 → 有则可跳到 3
- stage 4：检查 `git log` 是否已 commit → 有则可跳到 5
- stage 5-6：询问用户上次发送是否成功
- stage 7/10：询问用户是否已收到回复
- stage 8/11：检查是否已有修订修改
- 向用户汇报恢复点，确认是否从该阶段继续

---

## 阶段 1 — CHK（检查是否需要翻译）

写状态：stage 1

- 英文原文: `<ROOT>/linux/Documentation/<file>`
- 中文翻译: `<ROOT>/linux/Documentation/translations/zh_CN/<file>`
- 用 `Read` 读取英文原文，检查中文翻译是否存在
- 若存在：用 git 查看英文变更

```bash
cd <ROOT>/linux && git log -1 --format="%H" -- Documentation/translations/zh_CN/<file>
```

```bash
cd <ROOT>/linux && git log --oneline <zh_commit>..HEAD -- Documentation/<file>
```

- 统计文件行数和变更摘要

汇报：新翻译 / 更新 / 已最新 + 文件长度 + 变更摘要

提议：_"此文件需要 [新翻译/更新]，是否继续？"_（AskUserQuestion）

## 阶段 2 — TL（执行翻译）

写状态：stage 2

按 CLAUDE.md 和 translate skill 的规范执行翻译：
- 用 `Read` 读取英文原文 + 已有中文翻译（如果有） + `config/glossary.txt`
- **新翻译**：逐段翻译 + 加文件头（SPDX + disclaimer + Original + 翻译，见 Agent prompt 规范） + 检查 index.rst toctree
- **更新翻译**：对照 git diff 只改变更部分

翻译规范（严格遵守）：
- 行宽 ≤ 80 显示列宽（中文字符 = 2 列宽）
- 术语使用 `config/glossary.txt`，首次出现用"中文（English）"格式
- 保留代码块、命令、路径、函数名、RST 指令、交叉引用标签
- 中文标点，中英文/数字间加空格
- 标题下划线：一个英文一个符号、一个中文两个符号

提议：_"翻译完成（修改 N 行）。请审阅后确认继续质检。"_（AskUserQuestion）

## 阶段 3 — QA（质量检查）

写状态：stage 3

直接执行质量检查：

1. **行尾空白**: `Grep(pattern=" +$", path="<zh_file>")` → `Edit` 修复
2. **行宽检查**:

```bash
python3 -c "
import unicodedata, sys
for i, line in enumerate(open(sys.argv[1]), 1):
    w = sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in line.rstrip('\n'))
    if w > 80: print(f'  Line {i}: width {w}')
" <ROOT>/linux/Documentation/translations/zh_CN/<file>
```

3. **Windows 换行**: `Grep(pattern="\r$")` → 修复
4. 可修复问题自动修复，手动问题逐一修复后重检

提议：_"质检通过。是否提交并生成补丁？"_（AskUserQuestion）

## 阶段 4 — PAT（提交 + 补丁）

写状态：stage 4

**单文件**：
1. 获取英文原文当前 commit 信息：
   ```bash
   cd <ROOT>/linux && git log -1 --format="%h (\"%s\")" -- Documentation/<file>
   ```
2. 展示 4 行 commit message（从 git config 获取 name/email）：
   - 第 1 行 subject: `docs/zh_CN: Add <path> Chinese translation` 或 `docs/zh_CN: Update <path> translation`
   - 第 2 行 description: `Translate Documentation/<path> into Chinese.`
   - 第 3 行 through commit: `Translate through commit <hash> ("<subject>")`
   - 第 4 行 sign-off: `Signed-off-by: Name <email>`
   （参考 https://docs.kernel.org/translations/zh_CN/how-to.html ，4 行缺一不可）
3. 用户确认后：

```bash
cd <ROOT>/linux && git add Documentation/translations/zh_CN/<file>
```

```bash
cd <ROOT>/linux && git commit -m "docs/zh_CN: Add <path> Chinese translation

Translate Documentation/<path> into Chinese.

Translate through commit <hash>
(\"<subject>\")

Signed-off-by: Name <email>"
```

```bash
cd <ROOT>/linux && git format-patch docs-next..HEAD -o <ROOT>/outgoing
```

**批量**：所有文件到 QA 后统一 commit + format-patch：

```bash
cd <ROOT>/linux && git format-patch docs-next..HEAD -o <ROOT>/outgoing --cover-letter --thread=shallow
```

### 4-verify：验证补丁（必须）

补丁生成后，**必须**运行验证：

1. **checkpatch**：对每个非 cover-letter 补丁运行：
   ```bash
   cd <ROOT>/linux && perl scripts/checkpatch.pl <ROOT>/outgoing/<patch>
   ```
   error 必须修复，warning 视情况而定。

2. **RST 构建**：
   ```bash
   cd <ROOT>/linux && make htmldocs SPHINXOPTS="-j$(nproc)" 2>&1 | grep -E "WARNING|ERROR" | grep zh_CN
   ```
   只关注 `zh_CN` 相关的 WARNING/ERROR。

用表格汇报结果，全部通过后再继续。如果有问题，修复后重新生成补丁。

### 4-series：自动创建 series 条目

补丁生成后，自动在 `series-state.json` 中创建系列条目：

1. 从 git log 获取 commit hash 列表：
   ```bash
   cd <ROOT>/linux && git log --format="%h" docs-next..HEAD
   ```
2. 从 commit 中提取文件路径，推导子目录名和系列 ID（格式 `<subdir>-YYYY-MM`）
3. 用 Python 更新 series-state.json：
   ```bash
   python3 -c "
   import json
   from datetime import datetime, timezone
   with open('<ROOT>/scripts/series-state.json') as f: data = json.load(f)
   data['series']['<series-id>'] = {
       'subject': '<subject>',
       'files': [<file_list>],
       'commits': [<commit_list>],
       'phase': 'internal_review',
       'phases': {
           'internal_review': {'status': 'pending', 'rounds': []},
           'upstream': {'status': 'pending', 'rounds': []}
       }
   }
   with open('<ROOT>/scripts/series-state.json', 'w') as f: json.dump(data, f, ensure_ascii=False, indent=2); f.write('\n')
   "
   ```
4. 向用户汇报：已创建系列 `<series-id>`，可用 `/series --show <id>` 查看

提议：_"补丁已生成，系列已创建。建议先发给自己测试。"_（AskUserQuestion）

## 阶段 5 — E1（发给自己测试）

写状态：stage 5

```bash
cd <ROOT>/linux && git send-email --to="$(git config user.email)" --confirm=never <ROOT>/outgoing/*.patch
```

用户确认后执行。提示检查邮箱确认格式正常。

## 阶段 6 — E2（发给内审人员）

写状态：stage 6

用 AskUserQuestion 询问审阅者邮箱（或跳过内审直接到阶段 9）。

```bash
cd <ROOT>/linux && git send-email --to="<review_email>" --cc="$(git config user.email)" --confirm=never <ROOT>/outgoing/*.patch
```

### 6-series：记录 Message-ID 到 series round

发送成功后，从 git send-email 输出中提取 cover letter 的 Message-ID，创建新的 round：

```bash
python3 -c "
import json
from datetime import datetime, timezone
with open('<ROOT>/scripts/series-state.json') as f: data = json.load(f)
s = data['series']['<series-id>']
phase = s['phases'][s['phase']]
phase['status'] = 'sent'
version = len(phase['rounds']) + 1
per_patch = {}
for i, f in enumerate(s['files'], 1):
    per_patch[str(i)] = {'file': f, 'status': 'no_feedback', 'reviewed_by': [], 'action_items': []}
phase['rounds'].append({
    'version': version,
    'sent_at': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
    'cover_message_id': '<extracted-message-id>',
    'per_patch': per_patch
})
with open('<ROOT>/scripts/series-state.json', 'w') as f: json.dump(data, f, ensure_ascii=False, indent=2); f.write('\n')
"
```

---

## 内审 Review Circle（阶段 7 ↔ 8）

### 阶段 7 — W1（等待内审回复）

写状态：stage 7

#### 7-series：自动检查本地邮件

先尝试用 notmuch 检查本地邮件（如果可用）：

```bash
which notmuch 2>/dev/null && echo "available"
```

如果 notmuch 可用，且 series-state.json 中有当前系列的 cover_message_id：

```bash
mbsync -a 2>&1 | tail -3
```

```bash
notmuch new 2>&1
```

```bash
notmuch search "thread:{id:<cover_message_id>}" 2>&1
```

如果找到回复，用 `notmuch show --format=json` 获取并解析（同 `/series --check-feedback` 的解析逻辑），自动更新 series-state.json。

然后向用户汇报反馈情况，而不是直接询问。

#### 7-fallback：如果 notmuch 不可用或无系列数据

用 AskUserQuestion 提问：
- **"审阅者已通过"** → 进入阶段 9 (E3)
- **"有修改意见"** → 用户粘贴或描述反馈内容 → 进入阶段 8 (RV1)
- **"还没收到回复"** → 保持 stage 7，提议稍后再 `/work <file>` 检查

#### 7-post-check：基于 series-state 结果

如果自动检查了邮件，根据 series-state 中的反馈状态：
- 所有补丁 approved → 提议进入阶段 9
- 有 changes_requested → 提议进入阶段 8，展示 action items
- 无回复 → 保持 stage 7

### 阶段 8 — RV1（内审修订）

写状态：stage 8

#### 8a. 分析反馈

从 series-state.json 读取当前系列最新 round 的 per_patch，列出所有 status=changes_requested 的补丁及其 action_items。

如果 series-state 无数据，则从用户粘贴的反馈中分析。

列出需要修改的内容，向用户确认修改计划。

#### 8b. 修改翻译
按反馈修改翻译文件，同阶段 2 的规范。用 `Edit` 修改。

#### 8c. 质量检查
同阶段 3 的内联检查。

#### 8d. 重新生成补丁

```bash
cd <ROOT>/linux && git add Documentation/translations/zh_CN/<file> && git commit --amend --no-edit
```

确定版本号（从 series-state 最新 round version + 1）：

```bash
rm -rf <ROOT>/outgoing && mkdir -p <ROOT>/outgoing
```

```bash
cd <ROOT>/linux && git format-patch docs-next..HEAD -o <ROOT>/outgoing [--reroll-count=<version>] [--cover-letter --thread=shallow]
```

#### 8e. 验证补丁

同 4-verify 步骤，对重新生成的补丁运行 checkpatch + htmldocs 检查。

#### 8f. 重新发给审阅者

```bash
cd <ROOT>/linux && git send-email --to="<review_email>" --cc="$(git config user.email)" --confirm=never <ROOT>/outgoing/*.patch
```

#### 8-series：更新 series-state

发送后，在 series-state.json 中创建新的 round（同阶段 6 的逻辑），将 status 设为 `sent`。

发送后回到阶段 7（W1），写状态：stage 7

---

## 阶段 9 — E3（正式提交到邮件列表）

写状态：stage 9

### 9-series：调用 advance 推进到上游

如果 series-state.json 中有当前系列且 phase=internal_review：

1. **收集 Reviewed-by**：从 series-state 最新 round 的 per_patch 中收集所有 reviewed_by
2. **Soft reset commits**：
   ```bash
   cd <ROOT>/linux && git reset --soft docs-next
   ```
3. **重新 commit 带 Reviewed-by**：对每个文件重新 `git add` + `git commit`，commit message 中在 Signed-off-by 之前插入 Reviewed-by 行
4. **重新 format-patch**：
   ```bash
   rm -rf <ROOT>/outgoing && mkdir -p <ROOT>/outgoing
   ```
   ```bash
   cd <ROOT>/linux && git format-patch docs-next..HEAD -o <ROOT>/outgoing --cover-letter --thread=shallow
   ```
   （上游 v1，不加 --reroll-count）
5. **更新 series-state**：phase → upstream, internal_review.status → approved, upstream.status → pending

用 AskUserQuestion 确认后执行 advance。如果用户跳过了内审（无 series 数据），直接走原逻辑。

### 9-submit：发送到邮件列表

**警告**：将发到公开邮件列表（linux-doc@vger.kernel.org）。

收集收件人（同 send-patch skill 的 `--submit` 逻辑）。

先 dry-run：

```bash
cd <ROOT>/linux && git send-email --dry-run --to="Alex Shi <alexs@kernel.org>" --cc="linux-doc@vger.kernel.org" --confirm=never <ROOT>/outgoing/*.patch
```

展示预览，用户**明确确认**后正式发送。

发送成功后，记录 Message-ID 并在 series-state.json 中创建 upstream round（同阶段 6 的 round 创建逻辑，phase=upstream）。

---

## 邮件列表 Review Circle（阶段 10 ↔ 11）

### 阶段 10 — W2（等待邮件列表回复）

写状态：stage 10

#### 10-series：先检查本地邮件（同阶段 7 的 notmuch 模式）

如果 notmuch 可用且 series-state.json 中有 upstream round 的 cover_message_id：

```bash
mbsync -a 2>&1 | tail -3
```

```bash
notmuch new 2>&1
```

```bash
notmuch search "thread:{id:<cover_message_id>}" 2>&1
```

如果找到回复，用 `notmuch show --format=json` 解析并更新 series-state.json（同 `/series --check-feedback`）。

#### 10-lore：同时查询 lore.kernel.org

搜索邮件列表上的回复。构建搜索 URL 并用 `WebFetch` 获取：

```
WebFetch(url="https://lore.kernel.org/linux-doc/?q=docs/zh_CN+<file>&x=A", prompt="Extract all Atom feed entries...")
```

如果找到线程，用 curl + Python 获取回复（同 mail skill 的 `--replies` 逻辑）。

#### 10-report：向用户汇报

合并本地邮件和 lore 的结果。向用户汇报：线程链接 + 回复数量 + 每条回复的中文摘要。

三种结果：
1. **无回复** → 保持 stage 10，提议稍后再 `/work <file>` 检查
2. **有 review 意见** → 中文总结审核意见，展示 series-state 中的 action items，提议进入修订（阶段 11）
3. **maintainer 已 apply** → 更新 series-state phase=merged，提议归档（阶段 12）

### 阶段 11 — RV2（邮件列表修订）

写状态：stage 11

#### 11a. 分析反馈

从 series-state.json 读取 upstream 最新 round 的 per_patch（如有），结合 lore 获取的反馈。

逐条列出审核意见，向用户确认修改计划。

#### 11b. 起草回复邮件
同 mail skill 的 `--reply` 逻辑：
1. 用中文总结审核意见
2. 用英文起草 bottom-posting 回复
3. 展示给用户确认

#### 11c. 修改翻译
按审核意见用 `Edit` 修改翻译文件，同阶段 2 的规范。

#### 11d. 质量检查
同阶段 3 的内联检查。

#### 11e. 创建修订补丁 (vN)

从 series-state.json 的 upstream rounds 获取当前版本号，+1。

```bash
cd <ROOT>/linux && git add Documentation/translations/zh_CN/<file> && git commit --amend --no-edit
```

```bash
rm -rf <ROOT>/outgoing && mkdir -p <ROOT>/outgoing
```

```bash
cd <ROOT>/linux && git format-patch docs-next..HEAD -o <ROOT>/outgoing --reroll-count=N [--cover-letter --thread=shallow]
```

如果有 cover letter，提示用户编辑 changelog。

#### 11f. 验证补丁

同 4-verify 步骤，对重新生成的补丁运行 checkpatch + htmldocs 检查。

#### 11g. 重新发送

先自测：

```bash
cd <ROOT>/linux && git send-email --to="$(git config user.email)" --confirm=never <ROOT>/outgoing/*.patch
```

确认后正式提交，带 `--in-reply-to` 串联到原始线程（从 series-state 获取 upstream 第一轮的 cover_message_id）：

```bash
cd <ROOT>/linux && git send-email --to="Alex Shi <alexs@kernel.org>" --cc="linux-doc@vger.kernel.org" --in-reply-to="<cover_message_id>" --confirm=never <ROOT>/outgoing/*.patch
```

#### 11-series：更新 series-state

发送后，在 series-state.json 中创建新的 upstream round，status 设为 `sent`。

发送后回到阶段 10（W2），写状态：stage 10

---

## 阶段 12 — ARC（归档）

写状态：stage 12

汇报完成：
- 文件名
- 翻译类型（新翻译/更新）
- 最终版本号（v1 / v2 / ...）
- 内审修订次数 + 列表修订次数
- 邮件列表线程链接

## 批量模式特殊处理

- **翻译阶段（1-3）**：用 Agent 并行翻译，每个文件一个 Agent，最多 3 个并行
- **提交阶段（4）**：等所有翻译 agent 完成后，统一 commit + `format-patch --cover-letter`
- **邮件阶段（5-6）**：统一发送
- **内审 circle（7-8）**：统一等待/修订
- **提交阶段（9）**：统一发送
- **列表 circle（10-11）**：统一等待/修订
- **归档（12）**：统一更新所有文件状态

## 错误处理

- 任何阶段失败时，保持当前 workflow-state 不变，向用户汇报错误
- 用户可以修复问题后重新 `/work <file>` 从失败阶段恢复
- 如果用户在某阶段选择"跳过"或"取消"，保持当前状态，不推进到下一阶段
