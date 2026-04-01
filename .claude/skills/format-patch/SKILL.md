---
name: format-patch
description: Generate formatted kernel patches from translation commits
allowed-tools: Bash, Read, Glob
argument-hint: "[--cover-letter] [--version <N>] [--series <id>]"
---

# 生成补丁

从工作分支的翻译提交生成格式化补丁，不调用外部脚本。

> **路径约定**：Bash cwd 可能被污染，**不可假设为项目根目录**。
> 项目根目录（`<ROOT>`）从 skill 的 Base directory 推导：`Base directory` 往上 3 级。
> 每条 Bash 命令用 `cd <ROOT>/linux && ...` 或 `cd <ROOT> && ...` 显式切换。

解析 `$ARGUMENTS`：提取 `--cover-letter`、`--version <N>`、`--series <id>`。

## 步骤 0（可选）：从 series-state 读取参数

如果指定了 `--series <id>`：

1. 读取 `<ROOT>/scripts/series-state.json`
2. 找到对应系列，获取当前 phase 和最新 round
3. 自动计算 version：`len(phase.rounds) + 1`（如果已有 rounds），否则不加 `--reroll-count`
4. 如果 phase=upstream 且 rounds 为空，上游 v1，不加 `--reroll-count`
5. 覆盖 `--version` 参数（series-state 优先）

## 步骤 1：检查提交

```bash
cd <ROOT>/linux && git log --oneline docs-next..HEAD
```

如果没有提交，告知用户并退出。统计提交数量。

## 步骤 2：清理并创建输出目录

```bash
rm -rf <ROOT>/outgoing && mkdir -p <ROOT>/outgoing
```

## 步骤 3：生成补丁

构建 `git format-patch` 命令（参考官方规范）：

**单补丁**：

```bash
cd <ROOT>/linux && git format-patch docs-next..HEAD -o <ROOT>/outgoing [--reroll-count=N]
```

**多补丁**（提交数 > 1）：

```bash
cd <ROOT>/linux && git format-patch docs-next..HEAD -o <ROOT>/outgoing --cover-letter --thread=shallow [--reroll-count=N]
```

- 提交数 > 1 时**必须**加 `--cover-letter --thread=shallow`
- 如果指定了 `--version N`，使用 `--reroll-count=N`

## 步骤 4：列出生成的补丁

用 `Glob("outgoing/*.patch")` 列出所有生成的补丁文件。
用 `Read` 读取每个补丁的 Subject 行。

## 步骤 5：推荐收件人

检查 `get_maintainer.pl` 是否存在：

```bash
test -x <ROOT>/linux/scripts/get_maintainer.pl && echo "exists"
```

**如果存在**：对每个非 cover-letter 补丁运行：

```bash
cd <ROOT>/linux && perl scripts/get_maintainer.pl --no-rolestats <ROOT>/outgoing/<patch>
```

**如果不存在**：显示默认收件人：
- To: Alex Shi <alexs@kernel.org>
- Cc: linux-doc@vger.kernel.org

## 步骤 6：验证补丁

生成补丁后，**必须**运行以下检查：

### 6a. checkpatch

对每个非 cover-letter 补丁运行 checkpatch：

```bash
cd <ROOT>/linux && perl scripts/checkpatch.pl <ROOT>/outgoing/<patch>
```

汇报每个补丁的 errors / warnings 数量。如果有 error，必须修复后重新生成。
warning 视情况而定（如 commit subject 引用上游原文过长属于 false positive，可忽略）。

### 6b. RST 构建

```bash
cd <ROOT>/linux && make htmldocs SPHINXOPTS="-j$(nproc)" 2>&1 | grep -E "WARNING|ERROR" | grep zh_CN
```

只关注 `zh_CN` 相关的 WARNING/ERROR。如果有，修复后重新生成补丁。

### 6c. 汇报

用表格汇报每个补丁的 checkpatch 结果 + htmldocs 构建结果。
全部通过后再进入下一步。

## 步骤 7：Cover letter 提醒

如果生成了 cover letter（`outgoing/0000-cover-letter.patch`），提醒用户编辑。

## 步骤 8（可选）：更新 series-state

如果指定了 `--series <id>`，生成补丁后更新 series-state.json：

```bash
python3 -c "
import json
with open('<ROOT>/scripts/series-state.json') as f: data = json.load(f)
s = data['series']['<id>']
# 更新 commits
import subprocess
result = subprocess.run(['git', '-C', '<ROOT>/linux', 'log', '--format=%h', 'docs-next..HEAD'], capture_output=True, text=True)
s['commits'] = result.stdout.strip().split('\n')
with open('<ROOT>/scripts/series-state.json', 'w') as f: json.dump(data, f, ensure_ascii=False, indent=2); f.write('\n')
"
```

## 结果汇报

用中文汇报：
1. 生成了多少个补丁
2. 每个补丁的文件名和主题
3. 推荐收件人列表
4. 如果有 `--series`，显示系列 ID 和当前版本
5. 建议下一步运行 `/send-patch --self` 先发给自己测试
