# 翻译全流程编排

自动驱动翻译全流程。每步暂停等用户确认后再继续。使用 `bin/` 工具处理数据，AI 负责翻译和交互。

工作流模型参见 `docs/workflow.md`。翻译规范参见 `docs/translation-rules.md`。

> **路径约定**：`<ROOT>` 为项目根目录。
> 如果 `<ROOT>/linux/`、`<ROOT>/config/glossary.txt`、`<ROOT>/data/workflow-state.json` 不存在，提示用户先运行 setup。

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
| 空（无参数） | 自动选文件 |
| `--batch N` | 选 N 个文件排队处理 |
| `--batch N --dir <subdir>` | 从指定子目录选 N 个文件 |

文件路径相对于 `Documentation/`。

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

## 自动选文件

```bash
cd <ROOT> && python3 bin/kt-work --next [--dir <subdir>] --json
```

---

## 分支管理

每个 series 有独立的工作分支 `zh-work/<series-id>`，由 `kt-series --create` 自动创建。流水线阶段切换时自动切到对应分支（切分支前检查工作区干净）。

## 恢复机制

每个文件开始前，先读取 workflow-state，如果返回非 0 stage，从该 stage 恢复。根据 series-id 自动切到对应分支。向用户汇报恢复点，确认是否继续。

---

## 阶段 1 — CHK（检查是否需要翻译）

设置 stage 1。用 `bin/kt-diff --detail <file> --json` 获取状态。

汇报：新翻译 / 更新 / 已最新 + 变更摘要。

提议：_"此文件需要 [新翻译/更新]，是否继续？"_

## 阶段 2 — TL（执行翻译）

设置 stage 2。**AI 核心工作**，按 `docs/translation-rules.md` 规范翻译。

- 读取英文原文 + 已有中文翻译 + `config/glossary.txt`
- **新翻译**：逐段翻译 + 加文件头 + 检查 index.rst toctree
- **更新翻译**：对照 git diff 只改变更部分

提议：_"翻译完成。请审阅后确认继续质检。"_

## 阶段 3 — QA（质量检查）

设置 stage 3。

```bash
cd <ROOT> && python3 bin/kt-check --file linux/Documentation/translations/zh_CN/<file> --json
```

可修复问题自动修复（`--fix`），行宽问题手动修复。

提议：_"质检通过。是否提交并生成补丁？"_

## 阶段 4 — PAT（提交 + 补丁）

设置 stage 4。

1. 如果还没有 series，先创建（自动建 `zh-work/<id>` 分支并切过去）：
   ```bash
   cd <ROOT> && python3 bin/kt-series --create --json
   ```
2. 确保已在 series 分支上
3. 获取英文原文当前 commit 信息
4. 构建 4 行 commit message（参见 `docs/commit-format.md`）
5. 用户确认后 commit
6. 生成补丁（自动按 series 分支隔离）：
   ```bash
   cd <ROOT> && python3 bin/kt-format-patch --series <id> --json
   ```
7. **必须**验证 checkpatch + htmldocs（bin/kt-format-patch 自动完成）

提议：_"补丁已生成，系列已创建。建议先发给自己测试。"_

## 阶段 5 — E1（发给自己测试）

设置 stage 5。

```bash
cd <ROOT> && python3 bin/kt-send-patch --self --json
```

提示检查邮箱确认格式。

## 阶段 6 — E2（发给内审人员）

设置 stage 6。

询问审阅者邮箱（或跳过内审直接到阶段 9）。

```bash
cd <ROOT> && python3 bin/kt-send-patch --review <email> --series <id> --json
```

---

## 内审 Review Circle（阶段 7 ↔ 8）

### 阶段 7 — W1（等待内审回复）

设置 stage 7。

先用 `bin/kt-mail` 检查反馈（如 series-state 有 cover_message_id）：

```bash
cd <ROOT> && python3 bin/kt-mail --thread "<cover_message_id>" --local --json
```

根据反馈：
- 所有补丁 approved → 进入阶段 9
- 有 changes_requested → 展示 action items，进入阶段 8
- 无回复 → 保持 stage 7

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

设置 stage 9。

如果从内审推进，调用 advance 逻辑（收集 Reviewed-by，soft reset，重新 commit，重新 format-patch）：

向用户确认后：
- 收集 Reviewed-by 并重新 commit
- 重新 format-patch（上游 v1）
- dry-run 预览
- 用户确认后正式发送

```bash
cd <ROOT> && python3 bin/kt-send-patch --submit --series <id> --json
```

---

## 邮件列表 Review Circle（阶段 10 ↔ 11）

### 阶段 10 — W2（等待邮件列表回复）

设置 stage 10。同阶段 7 逻辑，检查本地邮件和 lore。

### 阶段 11 — RV2（邮件列表修订）

设置 stage 11。同阶段 8 逻辑，但：
- 起草英文回复邮件
- 重新 format-patch 带版本号
- 带 `--in-reply-to` 串联到原始线程

---

## 阶段 12 — ARC（归档）

设置 stage 12。推进 series 到 merged（自动检测 commits 是否已在 docs-next 中）：

```bash
cd <ROOT> && python3 bin/kt-series --advance <id> --json
```

这会标记 phase=merged。向用户确认是否删除工作分支：

```bash
cd <ROOT> && python3 bin/kt-series --delete <id> --json
```

汇报完成。

## 批量模式

翻译阶段（1-3）可并行，提交阶段（4+）统一处理。

## 错误处理

任何阶段失败时保持当前 stage 不变，用户可重新运行 work 恢复。
