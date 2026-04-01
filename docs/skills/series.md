# 补丁系列生命周期管理

使用 `bin/kt-series` 管理数据，AI 负责反馈分析和交互决策。

生命周期模型和状态 schema 参见 `docs/series-lifecycle.md`。

> **路径约定**：`<ROOT>` 为项目根目录。

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
2. **提取 Reviewed-by**
3. **提取修改意见**
4. **判断状态**：有 Reviewed-by → approved，有意见 → changes_requested

### 更新 series-state.json

更新对应 round 的 per_patch 数据。

### 汇报

用中文汇报反馈摘要。

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

## `--advance [id]` — 推进阶段

### 内审 → 上游

**前置条件**：phase=internal_review, status=approved。

1. 收集所有 Reviewed-by（从 series-state.json 最新 round）
2. Soft reset commits：
   ```bash
   cd <ROOT>/linux && git reset --soft docs-next
   ```
3. 对每个文件重新 commit，带 Reviewed-by tag
4. 重新 format-patch：
   ```bash
   cd <ROOT> && python3 bin/kt-format-patch --json
   ```
5. 更新 series-state：phase → upstream

### 上游 → 合并

phase = "merged"，汇报完成。

### 安全确认

每次 advance 前向用户确认操作。

---

## 错误处理

- series-state.json 不存在 → 提示运行 setup
- 指定 id 不存在 → 列出可用 id
- mbsync/notmuch 不可用 → 提示安装
