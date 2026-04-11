# 翻译全流程编排

自动驱动翻译全流程。每步暂停等用户确认后再继续。使用 `bin/` 工具处理数据，AI 负责翻译和交互。

工作流模型参见 `docs/workflow.md`。翻译规范参见 `docs/translation-rules.md`。

> **路径约定**：`<ROOT>` 为项目根目录。

### 前置条件（自动处理）

启动时自动检测并处理环境：

1. 如果 `<ROOT>/linux/` 不存在，用 Agent 委托执行 `/setup`：
   ```
   使用 Agent 工具执行 /setup 技能。
   subagent_type: "general-purpose"
   prompt: "执行 /setup 技能。完成后汇报结果。"
   ```
2. 如果 `<ROOT>/linux/` 已存在，运行 `kt-sync` 同步到最新：
   ```bash
   cd <ROOT> && python3 bin/kt-sync
   ```
3. 确认 `<ROOT>/config/glossary.txt` 存在（/setup 会创建）。

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

## 参数

| 输入 | 行为 |
|------|------|
| `<file-path>` | 对指定文件走流水线 |
| 空（无参数） | 列出待翻译文件供用户选择（见下方流程） |
| `--batch N` | 选 N 个文件排队处理 |
| `--batch N --dir <subdir>` | 从指定子目录选 N 个文件 |

文件路径相对于 `Documentation/`。

### 无参数时的文件选择流程

禁止自动选择。必须让用户从列表中挑选。

**Step 1：同步**

```bash
cd <ROOT> && python3 bin/kt-sync --json
```

自动 fetch + pull docs-next，命中缓存则秒回，否则重算并写缓存。

**Step 2：选择文件类型**

向用户展示两类文件供选择：
- **待更新翻译**（N 个）— 已有翻译但英文原文已变更
- **未翻译文件**（N 个）— 从未被翻译的文件

**Step 3：选择浏览方式**

根据文件类型提供不同的浏览入口：

待更新翻译：
1. **按排名** — 按落后 commits 排序，分页翻看
2. **按目录** — 先选目录再选文件
3. **搜索** — 输入关键词模糊匹配

未翻译文件：
1. **按目录** — 先选目录再选文件
2. **搜索** — 输入关键词模糊匹配

每种方式对应 `kt-diff` 的不同参数：
- 按排名：`kt-diff --type outdated|missing --page N`
- 按目录：`kt-diff --dirs [DIR] --type outdated|missing --page N`
- 搜索：`kt-diff --search KEYWORD --type outdated|missing`

**Step 4：分页浏览与选择**

交互控制：
- 编号选中文件（支持多选：`1,3,5` 或 `1-5`）
- `-编号` 取消选中（如 `-3`）
- `n` 下一页 / `p` 上一页
- `b` 返回上级
- `s` 切换到搜索
- `done` 确认选择

选中状态跨页保持，用 `✓` 标记已选文件、`·` 标记未选文件。
顶部始终显示当前已选文件数量和列表。

**Step 5：确认**

用户输入 `done` 后，展示已选文件列表（含行数），请求确认后进入流水线。

---

## 工作流状态管理

**读状态**：
```bash
cd <ROOT> && python3 bin/kt-work --stage <file> --json
```

**写状态**：
```bash
cd <ROOT> && python3 bin/kt-work --set <file> <N>
```

---

## 分支管理

每个 series 有独立的工作分支 `zh-work/<series-id>`，由 `kt-series --create` 自动创建。流水线阶段切换时自动切到对应分支（切分支前检查工作区干净）。

## 恢复机制

每个文件开始前，先读取 workflow-state，如果返回非 0 stage，从该 stage 恢复。根据 series-id 自动切到对应分支。向用户汇报恢复点，确认是否继续。

---

## 阶段 1 — CHK（检查是否需要翻译）

**前置条件**：需要最新代码。先运行：
```bash
cd <ROOT> && python3 bin/kt-sync
```

设置 stage 1。从 `kt-sync` 或 `kt-diff --json` 的缓存结果中查找该文件的状态（`commits_behind`）：

- 文件不在中文目录 → 新翻译
- `commits_behind > 0` → 需要更新
- `commits_behind == 0` → 已最新

汇报：新翻译 / 更新 / 已最新。

提议：_"此文件需要 [新翻译/更新]，是否继续？"_

## 阶段 2 — TL（执行翻译）

设置 stage 2。

如果还没有 series，先创建（自动建 `zh-work/<id>` 分支并切过去）：
```bash
cd <ROOT> && python3 bin/kt-series --create --json
```
确保已在 series 分支上，再开始翻译。

**AI 核心工作**，按 `docs/translation-rules.md` 规范翻译。

- **更新翻译**时，先获取详细变更：
  ```bash
  cd <ROOT> && python3 bin/kt-diff --detail <file> --json
  ```
  用返回的 commit 列表和 diff 内容确定英文改了什么，只改对应部分。
- 读取英文原文 + 已有中文翻译 + `config/glossary.txt`
- **新翻译**：逐段翻译 + 加文件头 + 检查 index.rst toctree
- **更新翻译**：对照 diff 只改变更部分

提议：_"翻译完成。请审阅后确认继续质检。"_

## 阶段 3 — QA（质量检查）

设置 stage 3。

```bash
cd <ROOT> && python3 bin/kt-check --file linux/Documentation/translations/zh_CN/<file> --json
```

可修复问题自动修复（`--fix`），行宽问题手动修复。

提议：_"质检通过。是否提交并生成补丁？"_

## 阶段 4 — PAT（提交 + 补丁）

设置 stage 4。此时已在 series 分支上（阶段 2 创建）。

1. 获取英文原文当前 commit 信息
2. 构建 4 行 commit message（参见 `docs/commit-format.md`）
3. 用户确认后 commit
4. 生成补丁（自动按 series 分支隔离）：
   ```bash
   cd <ROOT> && python3 bin/kt-format-patch --series <id> --json
   ```
5. **必须**验证 checkpatch + htmldocs（bin/kt-format-patch 自动完成）
6. 启动本地预览，供用户在浏览器中检查渲染效果：
   ```bash
   cd <ROOT> && python3 bin/kt-check --file <file> --serve
   ```
   在对话中展示预览 URL，用户确认后停止服务器。

提议：_"补丁已生成。建议先发给自己测试。"_

## 阶段 5 — E1（发给自己测试）

设置 stage 5。

```bash
cd <ROOT> && python3 bin/kt-send-patch --self --series <id>
```

从输出中提取 `git send-email` 命令，在对话中用代码块展示给用户（含收件人、补丁文件），用户确认后加 `--confirm` 执行：

```bash
cd <ROOT> && python3 bin/kt-send-patch --self --series <id> --confirm
```

提示检查邮箱确认格式。

## 阶段 6 — E2（发给内审人员）

设置 stage 6。

询问审阅者邮箱（或跳过内审直接到阶段 9）。

```bash
cd <ROOT> && python3 bin/kt-send-patch --review <email> --series <id>
```

从输出中提取 `git send-email` 命令，在对话中用代码块展示给用户（含收件人、补丁文件），用户确认后加 `--confirm` 执行：

```bash
cd <ROOT> && python3 bin/kt-send-patch --review <email> --series <id> --confirm
```

---

## 内审 Review Circle（阶段 7 ↔ 8）

### 阶段 7 — W1（等待内审回复）

设置 stage 7。

内审回复在你的**个人邮箱**中（通过 `mbsync` 同步到本地、`notmuch` 索引查询）。

**前置检查**：先确认本地邮件环境可用：

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
```

**检查回复**（series-state 有 cover_message_id 时）：

```bash
cd <ROOT> && python3 bin/kt-mail --thread "<cover_message_id>" --local --json
```

这会自动执行 `mbsync -a`（拉取最新邮件）→ `notmuch new`（索引）→ 按 message-id 查询线程。

分析反馈后，更新 series-state.json 中对应 round 的 per_patch 数据（tags、status、action_items）。如果讨论后决策变更（如 changes_requested → approved），同步更新 status 并记录原因。

根据反馈：
- 所有补丁 approved/acked → 主动提议：_"内审通过，是否推进到上游提交（阶段 9）？"_ 用户确认后进入阶段 9
- 有 changes_requested → 展示 action items，进入阶段 8
- 无回复 → 提示用户稍后再来检查，保持 stage 7

### 阶段 8 — RV1（内审修订）

设置 stage 8。

1. 从 series-state 读取 action_items
2. 按反馈修改翻译
3. 质量检查（`bin/kt-check`）
4. `git add && git commit --amend --no-edit`
5. 重新生成补丁（`bin/kt-format-patch --series <id>`）
6. 验证通过后重新发给审阅者
7. 回到阶段 7

---

## 阶段 9 — E3（正式提交到邮件列表）

设置 stage 9。（`kt-format-patch` 会自动 sync + rebase，无需手动运行 `kt-sync`。）

如果从内审推进，调用 advance 逻辑（soft reset，重新 commit，重新 format-patch）：

自动完成准备工作：
- soft reset，重新 commit（不带内审标签，只保留 Signed-off-by）
- 重新 format-patch（上游 v1）

然后运行 `kt-send-patch --submit` 生成 `git send-email` 命令：

```bash
cd <ROOT> && python3 bin/kt-send-patch --submit --series <id>
```

从输出中提取 `git send-email` 命令，在对话中用代码块展示给用户（含 To、Cc、补丁文件），用户确认后再执行该命令。确认后推进到阶段 10。

---

## 邮件列表 Review Circle（阶段 10 ↔ 11）

### 阶段 10 — W2（等待邮件列表回复）

设置 stage 10。

正式提交后，回复会出现在公开的邮件列表存档 **lore.kernel.org** 上。通过远程查询检查（不需要本地邮件环境）：

```bash
cd <ROOT> && python3 bin/kt-mail --thread "<cover_message_id>" --json
```

注意：**不带 `--local`**，直接从 lore.kernel.org 拉取线程。

分析反馈后，更新 series-state.json 中对应 round 的 per_patch 数据（tags、status、action_items）。如果讨论后决策变更，同步更新 status 并记录原因。

根据反馈：
- 收到 Reviewed-by / Acked-by（所有补丁 approved） → 主动提议：_"补丁已被接受，是否归档（阶段 12）？"_ 用户确认后进入阶段 12
- 有修改意见 → 展示 action items，进入阶段 11
- 无回复 → 提示用户：维护者回复通常需要几天到几周，可以先用 `/work` 翻译其他文件，稍后再来检查。保持 stage 10

### 阶段 11 — RV2（邮件列表修订）

设置 stage 11。（`kt-format-patch` 会自动 sync + rebase，无需手动运行 `kt-sync`。）同阶段 8 逻辑，但：
- 起草英文回复邮件
- 重新 format-patch 带版本号
- 带 `--in-reply-to` 串联到原始线程

---

## 阶段 12 — ARC（归档）

设置 stage 12。推进 series 到 merged（自动检测 commits 是否已在 docs-next 中）：

```bash
cd <ROOT> && python3 bin/kt-series --advance <id> --json
```

这会标记 phase=merged。

归档前，检查是否有未完成的后续任务（如依赖上游其他改动的更新）。如果有，写入 series 的 `follow_up` 字段：

```python
# 示例：通过 update_series_field 写入
update_series_field(ssp, series_id, follow_up=[
    {"file": "rust/quick-start.rst", "description": "等 rust-next 改动落入后更新", "waiting_for": "rust-next merge window"}
])
```

汇报时提醒用户有待跟进的后续任务。

向用户确认是否删除工作分支：

```bash
cd <ROOT> && python3 bin/kt-series --delete <id> --json
```

汇报完成。

## 批量模式

翻译阶段（1-3）可并行，提交阶段（4+）统一处理。

## 错误处理

任何阶段失败时保持当前 stage 不变，用户可重新运行 work 恢复。
