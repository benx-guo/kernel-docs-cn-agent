# 新手引导 — 渐进式翻译全流程教学

以交互式引导模式带领新手从零完成一次完整的内核文档翻译。采用渐进式披露：每步只展示当前需要的信息，概念在操作中自然引出。

> **路径约定**：`<ROOT>` 为项目根目录（包含 `docs/` 和 `bin/` 的目录）。
> 每条命令用 `cd <ROOT> && ...` 显式切换。

---

## 参数

| 参数 | 说明 |
|------|------|
| （无参数） | 自动检测状态，从合适阶段开始 |
| `--resume` | 从上次中断处继续 |
| `--phase N` | 直接跳到阶段 N（1-8） |
| `--status` | 展示当前引导进度 |

---

## 进度文件

进度保存在 `<ROOT>/data/guide-state.json`。

结构：

```json
{
  "version": 1,
  "current_phase": 2,
  "phases": {
    "1": {"status": "completed", "completed_at": "2026-04-01T10:00:00"},
    "2": {"status": "in_progress", "started_at": "2026-04-01T10:30:00"}
  },
  "context": {
    "chosen_files": [],
    "series_id": null,
    "email_configured": false
  }
}
```

### 读取进度

```python
import json
from pathlib import Path
state_path = Path("<ROOT>/data/guide-state.json")
if state_path.exists():
    state = json.loads(state_path.read_text())
else:
    state = None
```

### 写入进度

每个阶段完成或中断时更新 guide-state.json。用 Read 读取当前内容，用 Write 写回更新后的 JSON。确保 `data/` 目录存在。

---

## `--status` 模式

读取 `data/guide-state.json`，展示进度表格：

```
## 翻译引导进度

| 步骤 | 名称           | Work Stage(s) | 状态     |
|------|---------------|---------------|---------|
| 1    | 环境准备       | 前置           | ✓ 已完成 |
| 2    | 选择文件       | CHK            | → 进行中 |
| 3    | 翻译           | TL             | · 待开始 |
| 4    | 质检           | QA             | · 待开始 |
| 5    | 生成补丁       | PAT            | · 待开始 |
| 6    | 发给自己测试   | E1             | · 待开始 |
| 7    | 内审           | E2→W1↔RV1     | · 待开始 |
| 8    | 提交与社区评审 | E3→W2↔RV2→ARC | · 待开始 |
```

如果没有进度文件，显示"尚未开始引导流程。运行 `/guide` 开始。"

展示完毕后停止，不进入引导流程。

---

## 自动状态检测

当没有 `--phase` 参数时，按以下决策矩阵确定起始阶段：

| 优先级 | 条件 | 起始阶段 |
|--------|------|----------|
| 1 | `--resume` 且 guide-state.json 存在 | 从 `current_phase` 继续 |
| 2 | `--phase N` | 直接跳到 N |
| 3 | guide-state.json 存在且有 in_progress 阶段 | 从该阶段继续 |
| 4 | `<ROOT>/linux/` 不存在 | 阶段 1 |
| 5 | `<ROOT>/linux/` 存在但无 guide-state | 阶段 2 |
| 6 | workflow-state 有进行中文件 | 对应阶段（3-4） |
| 7 | series-state 有活跃 series | 阶段 5+ |

检测完毕后，**必须**向用户汇报检测结果并确认：

```
检测到以下状态：
- Linux 仓库：已克隆 ✓
- 引导进度：Step 2 进行中
- 建议从 Step 2 继续

确认从 Step 2 开始？
  [c] 从 Step 2 继续（推荐）
  [1] 从头开始
  [2] 选择其他阶段
```

---

## 欢迎信息

首次启动（无进度文件）时显示：

```markdown
# 欢迎！

我来带你完成一次 Linux 内核文档的中文翻译。
整个过程分 8 步，我们一步一步来。

先从搭建环境开始。
```

不展示阶段表格，不解释四步法。直接进入 Step 1。

---

## 技能交互方式

采用 Agent 委托模式：

- **Guide 直接执行**：输出说明 → 向用户提问 → 读/写状态文件
- **Agent 委托执行**：底层技能（/setup, /diff, /translate, /check, /format-patch, /send-patch, /mail, /series）
- **Guide 直接执行**：解读结果 → 更新 guide-state

Agent 委托示例：

```
使用 Agent 工具，prompt 为：
"执行 /setup 技能。完成后汇报结果。"
subagent_type: "general-purpose"
```

---

## 交互规则

- 每次输出控制在 **5-8 行**以内，然后等待用户确认
- **概念首次出现时用粗体标注**，后续不再重复解释
- 每阶段结束只预告下一步（一句话），不列出所有剩余步骤
- **每个选项必须带快捷键**（数字或字母），用户输入快捷键即可选择
- 交互方式：直接输出选项，等待用户文字回复（快捷键或完整文字均可）

### 快捷键规范

所有用户可操作的选项都必须有快捷键，格式为 `[键] 描述`：

```
[1] 未翻译文件（推荐新手）
[2] 待更新翻译
[3] 让我推荐一个
```

规则：
- **同类选择**用数字：`[1]` `[2]` `[3]`（如选文件类型、选文件）
- **流程控制**用字母：`[c]` 继续、`[p]` 暂停、`[m]` 了解更多、`[q]` 退出
- **确认/取消**：`[y]` 确认、`[n]` 取消/重选
- **文件浏览**：`[n]` 下一页、`[p]` 上一页、`[b]` 返回、`[s]` 搜索、`[d]` 确认选择
- 快捷键不区分大小写
- 推荐项在描述后标注 `（推荐）`

### 输出呈现

**禁止直接展示 CLI 工具的 raw 输出给用户**。Claude Code UI 会折叠超过几行的 bash 输出块，导致用户看不到内容。

正确做法：
1. 运行 CLI 工具（如 `kt-diff`）获取数据
2. 提取关键信息
3. 以**文本消息**（非 bash 输出块）呈现给用户

示例：运行 `kt-diff --type missing --dirs --json` 获取 JSON，然后自己格式化输出为文本。

**关键规则**：当用户回复为空或不明确时，**必须停下来再次确认**，绝不能自行假设用户意图。

---

## 进度显示

每步开头用进度条标记（含 stage 代号）：

```
━━━━━━━━━━━━━━━ Step X/8 · <STAGE> ━━━━━━━━━━━━━━━
```

例如 `Step 3/8 · TL`、`Step 6/8 · E1`。不展示完整阶段表格。

---

## Step 1/8 — 环境准备 [前置]

### 操作

用 Agent 委托执行 `/setup`：

```
使用 Agent 工具执行 /setup 技能。
subagent_type: "general-purpose"
prompt: "执行 /setup 技能。完成后汇报：仓库状态、当前分支、文件数量和覆盖率、依赖检查结果。"
```

Setup 完成后，运行 `kt-sync` 同步到最新：

```bash
cd <ROOT> && python3 bin/kt-sync
```

### 验证

检查环境是否就绪：

```bash
cd <ROOT>/linux && git branch --show-current
```

```bash
cd <ROOT> && test -f config/glossary.txt && echo "glossary OK"
```

```bash
cd <ROOT>/linux && git config user.name && git config user.email
```

如有问题，引导修复。

### 结果展示

操作完成后，向用户展示：

```markdown
━━━━━━━━━━━━━━━ Step 1/8 · 前置 ━━━━━━━━━━━━━━━

✓ 仓库已就绪：**docs-next** 分支，XXX 个英文文档，XXX 个已有翻译。

几个背景知识：
- 我们基于 **docs-next** 分支工作（文档变更都在这里）
- 内核用**邮件补丁**提交，不用 GitHub PR
- 术语翻译有统一规范（`config/glossary.txt`）

[c] 继续下一步  [m] 了解更多
```

### 可选深入

用户选 `m` 时，提供以下选项：

```
想了解哪方面？
  [1] 补丁文化是什么？
  [2] docs-next 和 mainline 有什么关系？
  [c] 不用了，继续
```

**补丁文化**：
```
内核开发不用 GitHub PR，而是通过邮件列表发送补丁。
开发者用 `git send-email` 把 .patch 文件发到对应的邮件列表，
维护者审阅后决定是否合入。整个过程公开透明，所有讨论都存档在
lore.kernel.org 上。
```

**docs-next 与 mainline 的关系**：
```
Linux 内核有多个维护者树（maintainer tree）。
文档维护者 Jonathan Corbet 管理 docs-next 分支，
所有文档变更先合入 docs-next，再在合并窗口期进入 mainline。
我们基于 Alex Shi 维护的翻译分支工作。
```

展开后回到"→ 继续下一步"。

### 过渡

```
✓ 环境就绪！下一步我们找一个合适的文件来翻译。

[c] 继续  [p] 暂停（下次 /guide 恢复）
```

更新 guide-state.json：阶段 1 设为 completed，current_phase 设为 2。

---

## Step 2/8 — 选择文件 [CHK]

### 操作

先同步远端并获取带缓存的 diff 数据（与 work stage 1 一致）：

```bash
cd <ROOT> && python3 bin/kt-sync --json
```

### 结果展示

```markdown
━━━━━━━━━━━━━━━ Step 2/8 · CHK ━━━━━━━━━━━━━━━

翻译现状：XX% **覆盖率**，XX 个待更新翻译，XX 个未翻译文件。

"待更新"指英文原文变更了但中文翻译还没跟上，
**commits behind** 越多说明越需要更新。

你想翻译哪种文件？
  [1] 未翻译文件（推荐新手）— 从未被翻译的文件
  [2] 待更新翻译 — 已有翻译但英文原文已变更
  [3] 让我推荐一个
  或直接输入文件路径/关键词
```

如果用户选择"让我推荐"，从 diff 结果中挑选一个行数较少（< 200 行）、内容相对独立的文件推荐。

如果用户直接输入文件路径或关键词，用 `kt-diff --search` 匹配，跳过浏览方式选择。

### 文件浏览交互

选定文件类型后，展示浏览方式。用户也可以随时直接输入文件路径或关键词，跳过菜单。

**浏览方式**（两种文件类型共用）：

```
怎么找文件？
  [1] 按目录 — 逐层钻入目录树
  [2] 按排名 — 未翻译→行数小优先；待更新→落后多优先
  [s] 搜索 — 输入关键词匹配
  或直接输入文件路径/关键词
```

每种方式对应 `kt-diff` 的不同参数：
- 按目录：`kt-diff --dirs [DIR] --type outdated|missing --page N`
- 按排名：`kt-diff --type outdated|missing --sort size|behind --page N`
  - 未翻译默认 `--sort size`（行数小优先，适合新手）
  - 待更新默认 `--sort behind`（落后多优先）
- 搜索：`kt-diff --search KEYWORD --type outdated|missing`
- 直接输入：当用户输入的内容不匹配任何快捷键时，视为文件路径或搜索关键词

**选择规则**：
- 目录和文件都可选，**支持多选**
- 编号选中：`3` 单选、`1,3,5` 或 `1-5` 多选
- `-编号` 取消选中（如 `-3`）
- **选中目录 = 选中该目录下所有文件**
- 选中状态跨页保持，用 `✓` 标记已选、`·` 标记未选
- 顶部始终显示已选数量和列表
- 随时可在两种文件类型之间切换（`[b]` 回到文件类型选择）

**导航栏**：每次展示列表时，底部必须固定输出导航栏（按上下文省略不适用的项）：

```
`[数字]` 选择  `[n]` 下一页  `[p]` 上一页  `[b]` 返回上级  `[s]` 搜索  `[d]` 确认选择
```

省略规则：
- 第一页省略 `[p]`，最后一页省略 `[n]`
- 顶层菜单（文件类型选择）省略 `[b]`
- 未选中任何文件时省略 `[d]`
- 其余项**不得省略**

### 确认文件

用户输入 `[d]` 后，对每个已选文件展示行数：

```bash
cd <ROOT>/linux && wc -l Documentation/<chosen_files>
```

```
已选 N 个文件：
  1. <file_a>（约 XX 行）
  2. <file_b>（约 XX 行）

确认翻译这些文件？
  [y] 确认，继续
  [n] 重新选择
```

确定后，将文件路径列表保存到 guide-state 的 `context.chosen_files`。

### 可选深入

```
想了解哪方面？
  [1] 怎么判断哪个文件更值得翻译？
  [2] 目录结构是怎么组织的？
  [c] 不用了，继续
```

**选文件策略**：
```
优先考虑：commits behind 多的文件（更新紧迫），
或社区关注度高的子系统（如 process/、admin-guide/）。
新手建议从短小文件（< 200 行）开始练手。
```

**目录结构**：
```
`Documentation/translations/zh_CN/` 下按子系统组织：
admin-guide/、process/、rust/、core-api/ 等。
每个翻译文件对应一个英文原文，路径结构保持一致。
```

### 创建 Series

文件确认后，立即创建 series（后续翻译、质检、提交都在 series 分支上进行）：

```
使用 Agent 工具执行 /series 技能创建新系列。
subagent_type: "general-purpose"
prompt: "执行 /series --create 技能。汇报创建的 series ID 和工作分支。"
```

将 series_id 保存到 guide-state 的 `context.series_id`。

### 过渡

```
✓ 目标文件已选定！Series 已创建，工作分支：`zh-work/<id>`。
下一步开始翻译。

[c] 继续  [p] 暂停（下次 /guide 恢复）
```

更新 guide-state.json：阶段 2 设为 completed，current_phase 设为 3。

---

## Step 3/8 — 翻译 [TL]

### 操作

确保已在 series 分支 `zh-work/<context.series_id>` 上。用 Agent 委托执行 `/translate`：

```
使用 Agent 工具，对 <context.chosen_files> 中的每个文件执行 /translate 技能。
subagent_type: "general-purpose"
prompt: "对以下文件逐个执行 /translate 技能：<context.chosen_files>。严格遵循 docs/translation-rules.md 规范。完成后汇报每个文件的翻译结果。"
```

**注意**：翻译是最耗时的阶段。Agent 完成后向用户展示结果。

### 结果展示

```markdown
━━━━━━━━━━━━━━━ Step 3/8 · TL ━━━━━━━━━━━━━━━

✓ 翻译完成！文件：`Documentation/translations/zh_CN/<chosen_files>`

翻译过程中遵循了几条关键规则：
- **行宽限制**：每行不超过 78 显示列（中文字符占 2 列）
- **术语规范**：部分术语按 `config/glossary.txt` 统一翻译
- **RST 格式**：标题、列表、代码块、交叉引用保持不变

[c] 继续下一步  [m] 了解更多
```

### 验证

基本验证（详细质检在 Step 4）：

1. 翻译文件存在
2. 文件有正确的头部信息
3. 行数与原文大致相当

```bash
cd <ROOT>/linux && test -f Documentation/translations/zh_CN/<chosen_files> && echo "file exists"
```

```bash
cd <ROOT>/linux && head -10 Documentation/translations/zh_CN/<chosen_files>
```

向用户展示文件头部，确认格式正确。

### 可选深入

```
想了解哪方面？
  [1] 行宽怎么计算？
  [2] 翻译和更新有什么区别？
  [c] 不用了，继续
```

**行宽计算**：
```
"这是一段示例文本" — 8 个中文字符 = 16 列 + 标点
"This is English"   — 15 个 ASCII 字符 = 15 列
混合行 "内核 kernel 模块" — "内核"(4) + " "(1) + "kernel"(6) + " "(1) + "模块"(4) = 16 列
每行不超过 78 显示列。
```

**翻译 vs 更新**：
```
- 新翻译：从零翻译整个文件
- 更新翻译：英文原文改了，只需修改变更部分，保留已有翻译
后者可以用 /diff 查看具体哪些行变了。
```

### 过渡

```
✓ 翻译完成！下一步我们检查一下格式有没有问题。

[c] 继续  [p] 暂停（下次 /guide 恢复）
```

更新 guide-state.json：阶段 3 设为 completed，current_phase 设为 4。

---

## Step 4/8 — 质检 [QA]

### 操作

用 Agent 委托执行 `/check`：

```
使用 Agent 工具执行 /check 技能。
subagent_type: "general-purpose"
prompt: "对以下文件逐个执行 /check 技能：<context.chosen_files>（路径前缀 linux/Documentation/translations/zh_CN/）。汇报每个文件发现的所有问题和修复建议。"
```

### 结果展示

根据检查结果分两种情况：

**无问题时**：

```markdown
━━━━━━━━━━━━━━━ Step 4/8 · QA ━━━━━━━━━━━━━━━

✓ 质量检查通过！没有发现问题。

检查涵盖了：行宽、行尾空白、RST 格式、术语一致性。
内核社区要求补丁零 error/warning 才能提交。

[c] 继续下一步
```

**有问题时**：

```markdown
━━━━━━━━━━━━━━━ Step 4/8 · QA ━━━━━━━━━━━━━━━

发现 X 个问题：

[逐个列出问题，每个问题附简短解释]

例如：
- 第 42 行：行宽超限（82 列 > 78 列）— 需要换行
- 第 15 行：行尾空白 — 可自动修复

我来修复这些问题。
```

然后用 Agent 委托修复：

```
使用 Agent 工具执行修复。
subagent_type: "general-purpose"
prompt: "对以下文件逐个执行 /check --fix 修复可自动修复的问题：<context.chosen_files>（路径前缀 linux/Documentation/translations/zh_CN/）。然后重新运行 /check 确认所有问题已解决。"
```

修复后向用户汇报结果。

### 可选深入

```
想了解哪方面？
  [1] 为什么内核对格式这么严格？
  [c] 不用了，继续
```

**格式要求的原因**：
```
内核补丁通过邮件发送，严格的格式保证：
- 补丁能被 git am 正确应用
- 代码审查工具能正确解析
- 邮件客户端不会破坏补丁内容
所以每次修改后都应运行质量检查。
```

### 过渡

```
✓ 质量检查通过！下一步把翻译打包成补丁。

[c] 继续  [p] 暂停（下次 /guide 恢复）
```

更新 guide-state.json：阶段 4 设为 completed，current_phase 设为 5。

---

## Step 5/8 — 生成补丁 [PAT]

### 操作

此时已在 series 分支上（Step 2 创建）。

1. 提交翻译文件（用 AI 构建 commit message，参见 `docs/commit-format.md`）
2. 生成补丁：

```
使用 Agent 工具执行 /format-patch 技能。
subagent_type: "general-purpose"
prompt: "执行 /format-patch --series <context.series_id> 技能。确保 checkpatch 和 htmldocs 验证通过。汇报生成的补丁文件列表。"
```

3. 启动本地预览，供用户检查渲染效果：

```bash
cd <ROOT> && python3 bin/kt-check --file <chosen_file> --serve
```

在对话中展示预览 URL，用户确认后停止服务器。

### 结果展示

```markdown
━━━━━━━━━━━━━━━ Step 5/8 · PAT ━━━━━━━━━━━━━━━

✓ 补丁已生成！

补丁文件：`outgoing/<series_id>/v1/`
- 0000-cover-letter.patch — **cover letter**（描述整体目的）
- 0001-<描述>.patch — 翻译补丁

**commit message** 遵循内核规范：
  主题行 `docs/zh_CN: <描述>` + 空行 + 原文引用 + Signed-off-by

[c] 继续下一步  [v] 查看补丁内容  [m] 了解更多
```

### 验证

```bash
cd <ROOT> && ls outgoing/<series_id>/v1/*.patch 2>/dev/null
```

### 可选深入

```
想了解哪方面？
  [1] commit message 的 4 行格式是什么？
  [2] patch series 是什么意思？
  [c] 不用了，继续
```

**commit message 4 行格式**：
```
第 1 行：主题行 — `docs/zh_CN: translate XXX into Chinese`
第 2 行：空行
第 3 行：原文 commit 引用 — `commit abc1234 ("原文标题")`（如适用）
第 4 行：Signed-off-by: Your Name <email>
```
展示 `docs/commit-format.md` 中的完整示例。

**patch series**：
```
多个相关补丁组成一个系列（series）。
第一封是 cover letter（0000），概述整体目的。
后续每个补丁（0001, 0002, ...）对应一个文件的改动。
维护者会把整个系列作为一组来审阅。
```

### 过渡

```
✓ 补丁就绪！下一步把补丁通过邮件发出去。

[c] 继续  [p] 暂停（下次 /guide 恢复）
```

更新 guide-state.json：阶段 5 设为 completed，current_phase 设为 6。

---

## Step 6/8 — 发给自己测试 [E1]

> 对应 work stage 5：E1（发给自己检查格式）

### 操作

自动检测邮件配置：

```bash
cd <ROOT>/linux && git config sendemail.smtpserver
```

如果未配置，引导查看 `config/email.conf.example` 并设置。将 `context.email_configured` 设为 true。
如果已配置，跳过直接进入发送。

先生成发送命令：

```bash
cd <ROOT> && python3 bin/kt-send-patch --self --series <context.series_id>
```

从输出中提取 `git send-email` 命令，在对话中用代码块展示给用户（含收件人、补丁文件），用户确认后加 `--confirm` 执行。

### 结果展示

```markdown
━━━━━━━━━━━━━━━ Step 6/8 · E1 ━━━━━━━━━━━━━━━

✓ 测试邮件已发到你的邮箱！

请检查邮箱确认补丁格式正确。
  [y] 格式正确，继续
  [n] 有问题，需要修复
```

### 可选深入

```
想了解哪方面？
  [1] 为什么要先发给自己？
  [c] 不用了，继续
```

**为什么先发给自己**：
```
发送分三步：先发给自己检查格式，再让熟人审阅内容，
最后才提交到公开列表。这样能避免在社区面前出现低级错误。
```

### 过渡

```
✓ 邮件格式确认无误！下一步可以找人内审。

[c] 继续  [p] 暂停（下次 /guide 恢复）
```

更新 guide-state.json：阶段 6 设为 completed，current_phase 设为 7。

---

## Step 7/8 — 内审 [E2→W1↔RV1]

> 对应 work stages 6-8：E2（发给内审）→ W1↔RV1（等待+修订循环）

### 操作

```
是否有熟悉的人可以先帮你审阅？
  [1] 有，输入邮箱地址
  [2] 没有，跳过内审（直接跳到 Step 8）
  [p] 暂停，稍后再发
```

如果有内审人员，先生成发送命令：

```bash
cd <ROOT> && python3 bin/kt-send-patch --review <email> --series <context.series_id>
```

从输出中提取 `git send-email` 命令，在对话中用代码块展示给用户（含收件人、补丁文件），用户确认后再执行。

### 内审循环

发给内审人员后，进入等待→反馈→迭代的循环。

**前置检查：本地邮件环境**

内审回复在你的个人邮箱中，需要 `mbsync` + `notmuch` 才能拉取和查询。检查是否可用：

```bash
which mbsync notmuch
```

如果缺失，提示用户：

```
⚠️ 查看内审回复需要本地邮件环境（mbsync + notmuch）。
请先配置：
  1. 安装：sudo dnf install isync notmuch
  2. 配置 ~/.mbsyncrc（IMAP 账号信息）
  3. 配置 ~/.notmuch-config（notmuch setup）
  4. 首次同步：mbsync -a && notmuch new

配置完成后再回来检查回复。
  [p] 暂停，配置好后用 /guide 回来
  [s] 跳过内审，直接到 Step 8
```

**检查内审反馈（Work Stage 7: W1）**

```
使用 Agent 工具执行 /mail --local 技能检查回复（从本地邮箱拉取最新邮件）。
subagent_type: "general-purpose"
prompt: "执行 /mail --thread <cover_message_id> --local 技能，检查 series <context.series_id> 的内审回复。汇报是否有 Reviewed-by 或修改意见。"
```

**无回复时**：

```
内审人员还没回复，这很正常。
（回复会到你的邮箱，下次回来时会自动同步最新邮件再检查。）

你可以：
  [p] 等一等，稍后用 /guide 回来检查
  [s] 跳过内审，直接到 Step 8
```

选择等待时，更新 guide-state（阶段 7 保持 in_progress）并暂停。

**收到修改意见时（Work Stage 8: RV1）**：

```
收到内审反馈：

[列出具体修改意见]

这就是**版本迭代**：根据反馈修改后，版本号从 v1 变成 v2 重新发送。
我来帮你修改并生成新版本。
```

然后依次执行（对应 work 阶段 8 RV1）：

1. 修改翻译文件
2. 重新质检（/check）
3. `git add && git commit --amend --no-edit`
4. 生成新版本补丁（/format-patch，版本号递增）
5. 重新发给内审人员（/send-patch --review）
6. 回到 W1 等待（循环直到 approved）

```
使用 Agent 工具执行迭代。
subagent_type: "general-purpose"
prompt: "根据评审意见修改 linux/Documentation/translations/zh_CN/<context.chosen_files>，然后依次执行：/check 质检 → git add && git commit --amend --no-edit → /format-patch 生成新版本补丁 → /send-patch --review 重新发给内审人员。汇报每步结果。"
```

修改完成后：

```
✓ v2 补丁已生成并重新发给内审人员。

等待新一轮反馈：
  [p] 稍后回来检查（/guide 恢复）
  [w] 继续等待
```

**循环**：回到"检查内审反馈"，直到收到 Reviewed-by 或用户决定跳过。

**收到 Reviewed-by 时**：

```
✓ 收到 **Reviewed-by** 标签！内审通过。

格式：`Reviewed-by: Name <email>`
这个标签会写入补丁，表示有人审阅并认可了你的翻译。

下一步正式提交到邮件列表。
```

### 验证

```
使用 Agent 工具查看 series 状态。
subagent_type: "general-purpose"
prompt: "执行 /series --show <context.series_id> 技能。汇报当前 series 的发送状态和版本历史。"
```

### 可选深入

```
想了解哪方面？
  [1] 为什么需要内审？
  [c] 不用了，继续
```

**为什么需要内审**：
```
内审能在正式提交前发现翻译错误、术语不一致等问题。
在公开邮件列表上出现低级错误会影响社区对你的印象。
内审相当于 code review——让熟悉的人先帮你把关。
```

### 过渡

```
✓ 内审通过！下一步正式提交到邮件列表。

[c] 继续  [p] 暂停（下次 /guide 恢复）
```

更新 guide-state.json：阶段 7 设为 completed，current_phase 设为 8。

---

## Step 8/8 — 提交与社区评审 [E3→W2↔RV2→ARC]

> 对应 work stages 9-12：E3（正式提交）→ W2↔RV2（社区评审循环）→ ARC（归档）

### 步骤 1：正式提交到邮件列表（Work Stage 9: E3）

如果从内审推进，先收集 Reviewed-by 并重新 commit、format-patch。

```markdown
━━━━━━━━━━━━━━━ Step 8/8 · E3 ━━━━━━━━━━━━━━━

现在要把补丁正式提交到公开邮件列表。
⚠️ 这是**不可逆**操作——邮件列表上的所有人都能看到。

接下来生成发送命令：
```

先运行 `kt-send-patch --submit` 获取完整的 `git send-email` 命令：

```bash
cd <ROOT> && python3 bin/kt-send-patch --submit --series <context.series_id>
```

从输出中提取 `git send-email` 命令，在对话中用代码块展示给用户（含 To、Cc、补丁文件），例如：

```
即将执行以下命令：

cd <ROOT>/linux
git send-email \
    --to='Alex Shi <alexs@kernel.org>' \
    --cc='linux-doc@vger.kernel.org' \
    --confirm=never \
    outgoing/xxx/v1/0000-cover-letter.patch \
    outgoing/xxx/v1/0001-xxx.patch

确认发送？（不可逆）
  [y] 确认，执行
  [n] 取消
```

用户确认后再执行该命令。

### 步骤 2：等待社区回复（Work Stage 10: W2）

正式提交后，回复会出现在公开的 **lore.kernel.org** 邮件列表存档上（不需要本地邮件环境）。

```
使用 Agent 工具执行 /mail 技能从 lore.kernel.org 检查回复（不带 --local）。
subagent_type: "general-purpose"
prompt: "执行 /mail --thread <cover_message_id> 技能（从 lore.kernel.org 拉取），检查 series <context.series_id> 在邮件列表上的回复。汇报是否有 Reviewed-by、Acked-by 或修改意见。"
```

**无回复时**：

```
暂时没有社区回复，这很正常——维护者可能需要几天到几周时间。
（可以在 lore.kernel.org 上搜索你的补丁标题查看最新状态。）

你可以：
  [1] 定期用 /mail 检查回复（从 lore 查询，无需本地配置）
  [2] 先去翻译其他文件（/work）
  [q] 结束引导
```

选择等待时，更新 guide-state（阶段 8 保持 in_progress）并暂停。

**收到修改意见时（Work Stage 11: RV2）**：

```
收到社区评审意见：

[列出具体修改意见]

和内审一样，需要**版本迭代**：修改 → 质检 → 生成新版本 → 重新提交。
```

然后用 Agent 委托：修改翻译 → 质检 → 重新 format-patch（版本号递增，带 `--in-reply-to`）→ 重新 `--submit`。提交新版本后回到 W2 等待，循环直到通过。

**收到 Reviewed-by / Acked-by 时**：

```
✓ 收到社区的 **Reviewed-by**！

补丁会由维护者合入 docs-next 分支。
合入后你的翻译就正式成为 Linux 内核的一部分了！
```

### 步骤 3：归档（Work Stage 12: ARC）

收到 Reviewed-by 或确认补丁已合入后，执行归档：

```
使用 Agent 工具执行归档。
subagent_type: "general-purpose"
prompt: "执行 /series --advance <context.series_id> 技能。检查补丁是否已合入 docs-next。如果已合入，标记为 merged 并询问用户是否删除工作分支。"
```

```
✓ 补丁已归档！

  - Series 状态：merged
  - 工作分支已清理（如用户确认）

这个翻译的完整生命周期到此结束。
```

### 可选深入

```
想了解哪方面？
  [1] 评审迭代一般要几轮？
  [2] 怎么在 lore.kernel.org 上查看讨论？
  [3] 归档后还能修改吗？
  [c] 不用了，继续
```

**评审轮数**：
```
通常 1-3 轮。简单的翻译补丁可能一轮就通过，
复杂的可能需要多轮修改。耐心回应每条意见，
保持专业友善的沟通态度。
```

**lore.kernel.org**：
```
lore.kernel.org 是内核邮件列表的公开存档。
你可以在上面搜索自己的补丁标题，查看完整的讨论线程。
用 /mail --search 可以直接搜索。
```

**归档后修改**：
```
归档（ARC）表示这一轮完成了。如果后续原文又有更新，
会产生新的 commits_behind，可以作为新任务重新走 /work 流程。
```

### 过渡

更新 guide-state.json：阶段 8 设为 completed。

---

## 引导完成

所有 8 步完成后：

```markdown
# 恭喜！你已完成一次完整的内核文档翻译！

从环境准备到归档（ARC），你走完了全部 12 个 work stages。

接下来你可以：
- 用 `/work` 独立完成更多翻译（不再需要引导）
- 用 `/diff --status` 查找更多待翻译文件

有用的资源：
- 翻译规范：`docs/translation-rules.md`
- 补丁提交指南：`docs/patch-submission.md`
```

---

## 暂停与恢复

### 暂停

在任何阶段用户选择"暂停"时：

1. 更新 guide-state.json，当前阶段设为 `in_progress`
2. 向用户确认：

```
引导已暂停在 Step X。
下次使用 `/guide` 即可从此处继续。
```

### 恢复

`--resume` 或自动检测到 guide-state.json 时：

1. 读取 guide-state.json
2. 找到 current_phase
3. 向用户汇报："上次做到 Step X，继续？"
4. 从该阶段重新开始

恢复时也要加载 context（chosen_files、series_id 等），避免用户重复选择。
