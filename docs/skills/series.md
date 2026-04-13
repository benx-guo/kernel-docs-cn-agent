# 补丁系列生命周期管理

使用 `bin/kt-series` 管理数据，AI 负责反馈分析和交互决策。

生命周期模型和状态 schema 参见 `docs/series-lifecycle.md`。

> **路径约定**：`<ROOT>` 为项目根目录。

需要用户选择或确认时，直接输出编号选项，等待用户文字回复。

## 数据查询

### `--list`

```bash
cd <ROOT> && python3 bin/kt-series --list --json
```

### `--show <id>`

```bash
cd <ROOT> && python3 bin/kt-series --show <id> --json
```

### `--create`

确认系列 ID、Subject、文件列表后执行：

```bash
cd <ROOT> && python3 bin/kt-series --create --json
```

创建时自动：
- 生成 `zh-work/<series-id>` 工作分支（基于 `docs-next`）
- 如果当前分支有该模块的 commit，cherry-pick 到新分支
- 将 `branch` 字段写入 series-state

### `--delete <id>`

删除 series 及其工作分支：

```bash
cd <ROOT> && python3 bin/kt-series --delete <id> --json
```

### `--dashboard`

```bash
cd <ROOT> && python3 bin/kt-series --dashboard
```

---

## `--check-feedback [id]` — 检查邮件反馈（AI 分析）

### 确定系列

如果未指定 id：

```bash
cd <ROOT> && python3 bin/kt-series --list --json
```

从活跃系列中选 status 为 sent 或 feedback_received 的。多个时询问用户。

### 获取反馈

使用 `bin/kt-mail` 获取线程回复：

```bash
cd <ROOT> && python3 bin/kt-mail --thread "<cover_message_id>" --local --json
```

从 series-state.json 中读取 cover_message_id。

### AI 分析反馈

根据获取到的回复，分析每个回复：

1. **判断回复对应哪个补丁**：从 Subject 中的 `[PATCH N/M]` 或 In-Reply-To 关联
2. **提取标签**：Reviewed-by、Acked-by 等（以完整标签行格式存入 `tags` 字段，如 `"Reviewed-by: Name <email>"`）
3. **提取修改意见**
4. **判断 per_patch status**：有 Reviewed-by / Acked-by → `approved`，有意见 → `changes_requested`
5. **更新决策变更**：如果经过邮件讨论后决策发生变更（如 changes_requested → approved），也应更新 per_patch status 并将决策原因记录到 action_items（如 `"讨论后决定按现有版本接受"`）

### 更新 series-state.json

更新对应 round 的 per_patch 数据（tags、status、action_items）。

### 汇报

用中文汇报反馈摘要。根据结果主动提示下一步操作：

- 所有补丁 approved/acked → _"所有补丁已通过审阅，建议推进到下一阶段。是否执行 `--advance`？"_
- 有 changes_requested → _"以下补丁需要修改，建议执行 `--prepare-next` 开始修订。"_
- 无反馈 → _"暂无反馈，建议稍后再检查。"_

---

## `--prepare-next [id]` — 准备下一轮修改

### 读取状态

```bash
cd <ROOT> && python3 bin/kt-series --show <id> --json
```

### 列出 action items

汇总所有 changes_requested 的补丁及其 action_items。

### 更新状态

将 status 设为 `revising`（更新 series-state.json）。

提议：_"以上是需要修改的内容。是否开始修改？"_

---

## `--advance <id>` — 推进阶段

```bash
cd <ROOT> && python3 bin/kt-series --advance <id> --json
```

### 内审 → 上游

**前置条件**：phase=internal_review, status=approved。

自动将 phase 设为 `upstream`。

推进后，AI 应完成以下步骤：
1. 收集所有标签（Reviewed-by、Acked-by 等，从 series-state.json 最新 round 的 `tags` 字段）
2. Soft reset commits：
   ```bash
   cd <ROOT>/linux && git reset --soft docs-next
   ```
3. 对每个文件重新 commit，带收集到的标签（Reviewed-by、Acked-by 等）
4. 重新 format-patch：
   ```bash
   cd <ROOT> && python3 bin/kt-format-patch --series <id> --json
   ```

### 上游 → 合并

**自动检测**：检查 series 的所有 commits 是否已被 `docs-next` 包含（`is_ancestor`）。

- 如果已合并：标记 phase="merged"，工作分支保留，需用 `--delete <id>` 手动清理
- 如果未合并：报错退出，提示补丁尚未被合并

### 安全确认

每次 advance 前向用户确认操作。

---

## 错误处理

- series-state.json 不存在 → 提示运行 setup
- 指定 id 不存在 → 列出可用 id
- mbsync/notmuch 不可用 → 提示安装
