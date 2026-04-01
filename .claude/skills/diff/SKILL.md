---
name: diff
description: Compare English kernel docs with zh_CN translations to find missing or outdated files
allowed-tools: Bash, Read, Grep, Glob, AskUserQuestion
argument-hint: "[--status] [--dir [subdir]] [--detail [file]] [--search <keyword>]"
---

# 翻译差异比对

直接使用 git 和文件系统操作比较英文文档与中文翻译差异，不调用外部脚本。

> **路径约定**：Bash cwd 可能被污染，**不可假设为项目根目录**。
> 项目根目录（`<ROOT>`）从 skill 的 Base directory 推导：`Base directory` 往上 3 级。
> 每条 Bash 命令用 `cd <ROOT>/linux && ...` 显式切换。
> 如果 `<ROOT>/linux/` 不存在，提示用户先运行 `/setup`。

## 交互方式

需要用户选择时，使用 `AskUserQuestion` 弹出选项列表。
`AskUserQuestion` 的 options 最多 4 个。如果候选项超过 4 个，按以下策略处理：
- 取最相关/最常用的前 3 个作为选项
- 用户可通过 "Other" 自行输入

## 参数解析

解析 `$ARGUMENTS`：

| 参数 | 说明 |
|------|------|
| （无参数） | 用 `AskUserQuestion` 让用户选择模式 |
| `--status` | 全局概览，Top 10 过期文件 |
| `--dir` | 用 `AskUserQuestion` 列出目录让用户选 |
| `--dir <subdir>` | 直接执行指定目录的翻译状态 |
| `--detail` | 用 `AskUserQuestion` 列出文件让用户选 |
| `--detail <file>` | 直接执行指定文件的详细差异 |
| `--search <keyword>` | 搜索文件，结果用 `AskUserQuestion` 让用户选 |

有明确参数值时直接执行，不再询问。

---

## 无参数 — 让用户选择模式

1. 获取当前分支、HEAD、翻译目录列表（同时执行）：

```bash
cd <ROOT>/linux && git branch --show-current && git log --oneline -1
```

```bash
cd <ROOT>/linux && find Documentation/translations/zh_CN/ -name '*.rst' | sed 's|Documentation/translations/zh_CN/||' | sed 's|/[^/]*$||' | sort | uniq -c | sort -rn | head -20
```

2. 用文本输出当前状态信息（分支、HEAD、目录概览）。

3. 用 `AskUserQuestion` 让用户选择模式：

   选项：
   - **全局概览** — 显示 Top 10 过期文件
   - **选择目录** — 按目录查看翻译状态
   - **选择文件** — 查看指定文件差异
   - **搜索文件** — 按关键词搜索

4. 根据用户选择进入对应流程。

---

## `--dir`（不带目录名）— 选择目录

1. 获取顶级目录列表：

```bash
cd <ROOT>/linux && find Documentation/translations/zh_CN/ -name '*.rst' | sed 's|Documentation/translations/zh_CN/||' | sed 's|/[^/]*$||' | grep -v '/' | sort | uniq -c | sort -rn
```

2. 用 `AskUserQuestion` 列出前 3 个最大的目录作为选项（label 格式：`<目录名> (<N> 个文件)`），用户可通过 "Other" 输入其他目录名。

3. 用户选择后，进入 `--dir <subdir>` 模式执行。

---

## `--detail`（不带文件名）— 选择文件

1. 获取已翻译文件列表：

```bash
cd <ROOT>/linux && find Documentation/translations/zh_CN/ -name '*.rst' | sed 's|Documentation/translations/zh_CN/||' | sort
```

2. 先用 `AskUserQuestion` 让用户选择目录范围（前 3 大目录 + Other）。

3. 用户选择目录后，列出该目录下的文件，再用 `AskUserQuestion` 让用户选择具体文件（取前 3 个 + Other）。

4. 用户选择后，进入 `--detail <file>` 模式执行。

---

## `--search <keyword>` — 搜索文件

1. 在已翻译文件中搜索：

```bash
cd <ROOT>/linux && find Documentation/translations/zh_CN/ -name '*.rst' | sed 's|Documentation/translations/zh_CN/||' | grep -i "<keyword>"
```

2. 如无匹配，扩大到英文文件：

```bash
cd <ROOT>/linux && find Documentation/ -name '*.rst' -not -path '*/translations/*' | sed 's|Documentation/||' | grep -i "<keyword>"
```

3. 用 `AskUserQuestion` 列出匹配结果（前 3 个 + Other），label 中标注"已翻译"或"未翻译"。

4. 用户选择后，进入 `--detail <file>` 模式执行。

---

## `--detail <file>` 模式

`<file>` 是相对于 `Documentation/` 的路径（如 `admin-guide/README.rst`）。

### 步骤

1. 确认英文文件存在：用 `Read` 读取 `linux/Documentation/<file>`
2. 确认中文文件存在：用 `Read` 读取 `linux/Documentation/translations/zh_CN/<file>`
   - 不存在则报告"此文件尚未翻译"并退出
3. 获取中文文件最后更新 commit：

```bash
cd <ROOT>/linux && git log -1 --format="%H %ai %s" -- Documentation/translations/zh_CN/<file>
```

4. 查看英文自该 commit 以来的变更：

```bash
cd <ROOT>/linux && git log --oneline <zh_commit>..HEAD -- Documentation/<file>
```

5. 如有变更，显示详细 diff：

```bash
cd <ROOT>/linux && git diff <zh_commit>..HEAD -- Documentation/<file>
```

6. 检查合并状态：

```bash
cd <ROOT>/linux && git merge-base --is-ancestor <zh_commit> docs-next && echo "merged" || echo "local"
```

7. 用中文汇报：
   - **Diff 范围**：`<zh_commit_short>..HEAD`（中文最后更新 → 当前 HEAD）
   - **状态**：已合并 / 本地未合并
   - 中文翻译最后更新时间和 commit
   - 英文在此范围内的变更次数
   - 变更内容摘要（分析 diff，总结哪些部分改了）

---

## `--status` 模式

快速概览，显示 top 10 过期文件。

### 步骤

1. 统计英文和中文文件数量：

```bash
cd <ROOT>/linux && find Documentation/ -name '*.rst' -not -path '*/translations/*' | wc -l
```

```bash
cd <ROOT>/linux && find Documentation/translations/zh_CN/ -name '*.rst' | wc -l
```

2. 获取所有中文翻译文件列表，批量检查过期状态和合并状态：

```bash
cd <ROOT>/linux && find Documentation/translations/zh_CN/ -name '*.rst' | while read zh_file; do
  rel="${zh_file#Documentation/translations/zh_CN/}"
  en_file="Documentation/$rel"
  [ -f "$en_file" ] || continue
  zh_commit=$(git log -1 --format="%H" -- "$zh_file" 2>/dev/null)
  [ -n "$zh_commit" ] || continue
  count=$(git log --oneline "$zh_commit..HEAD" -- "$en_file" 2>/dev/null | wc -l)
  date=$(git log -1 --format="%as" -- "$zh_file")
  short=$(git log -1 --format="%h" -- "$zh_file")
  if git merge-base --is-ancestor "$zh_commit" docs-next 2>/dev/null; then
    status="merged"
  else
    status="local"
  fi
  echo "$rel|$count|$date|$short|$status"
done | sort -t'|' -k2 -nr | head -10
```

3. 汇总报告（中文）：
   - **当前 HEAD**：`<short-hash> <subject>`
   - 总英文文件数 / 中文文件数 / 覆盖率
   - Top 10 过期文件（按 commits behind 降序），每行标注：中文最后更新日期、基准 commit、**状态**（已合并 / 本地未合并）
   - 推荐优先更新的文件

---

## `--dir <subdir>` 模式

同 `--status`，但限定在指定子目录下。

### 步骤

同 `--status` 模式（含合并状态检测），但 find 范围限制为：

```bash
cd <ROOT>/linux && find Documentation/<subdir>/ -name '*.rst' -not -path '*/translations/*' | wc -l
```

```bash
cd <ROOT>/linux && find Documentation/translations/zh_CN/<subdir>/ -name '*.rst' 2>/dev/null | wc -l
```

过期检查也限定在 `<subdir>/` 下，不截断为 top 10，列出全部。

同时列出缺失文件：

```bash
cd <ROOT>/linux && find Documentation/<subdir>/ -name '*.rst' -not -path '*/translations/*' | while read en_file; do
  rel="${en_file#Documentation/}"
  zh_file="Documentation/translations/zh_CN/$rel"
  [ -f "$zh_file" ] || echo "$rel"
done
```

---

## 结果展示

用中文向用户汇报：
1. 按优先级推荐需要更新的文件（变更少的优先，更容易完成）
2. 推荐适合翻译的缺失文件（短文件优先）
3. 建议使用 `/translate <file>` 开始翻译工作
