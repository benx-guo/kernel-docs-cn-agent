---
name: setup
description: Clone the Linux kernel docs-next repo and initialize the translation environment
allowed-tools: Bash, Read, Glob
argument-hint: ""
---

# 初始化内核翻译环境

直接检测环境并完成初始化，不调用外部脚本。

> **路径约定**：Bash 工具的 cwd 可能被前序命令污染，**不可假设为项目根目录**。
> 每条 Bash 命令必须用 `cd $ROOT &&` 显式切换到项目根目录（`$ROOT` 来自步骤 0）。
> 内核仓库操作使用 `cd $ROOT/linux && ...`。

## 步骤 0：定位项目根目录 + 创建目录结构

**定位项目根目录**：查找包含 `CLAUDE.md` 的目录。

```bash
ROOT=$(git -C "$(dirname "$(find / -maxdepth 5 -name CLAUDE.md -path "*/kernel-translations*" 2>/dev/null | head -1)")" rev-parse --show-toplevel 2>/dev/null) || ROOT=$(dirname "$(find /home -maxdepth 4 -name CLAUDE.md -path "*/kernel-translations*" 2>/dev/null | head -1)") && echo "ROOT=$ROOT"
```

如果上述方法不可靠，直接使用 skill 的 Base directory 回溯：**Base directory 是 `.claude/skills/setup/`，项目根 = 往上 3 级**。

**更简单的方式**：skill 被调用时系统会显示 `Base directory for this skill: <path>`。从这个路径提取项目根目录：

```
Base directory: /xxx/yyy/.claude/skills/setup/
项目根 = /xxx/yyy/
```

**在第一条命令中确定 ROOT 并记住它**：

```bash
echo "/home/ben/kernel-translations-agents"
```

> 注意：上面的路径从 skill 的 Base directory 推导。后续所有命令用此值作为 `$ROOT`。

**创建目录结构**（首次使用时，用户可能只有 `.claude/` 和 `CLAUDE.md`）：

```bash
cd <ROOT> && mkdir -p config scripts outgoing
```

创建术语表（如果不存在）：

```bash
cd <ROOT> && test -f config/glossary.txt || echo "# 内核术语对照表
# 格式: English term | 中文翻译 | Notes
# 标记'不翻译'的术语保留英文原文
CPU | CPU | 不翻译
DMA | DMA | 不翻译
IRQ | IRQ | 不翻译
memory barrier | 内存屏障 |
spinlock | 自旋锁 |
mutex | 互斥锁 |
scheduler | 调度器 |
preemption | 抢占 |
" > config/glossary.txt
```

创建工作流状态文件（如果不存在）：

```bash
cd <ROOT> && test -f scripts/workflow-state.json || echo '{"version": 1, "files": {}}' > scripts/workflow-state.json
```

创建补丁系列状态文件（如果不存在）：

```bash
cd <ROOT> && test -f scripts/series-state.json || echo '{"version": 1, "series": {}}' > scripts/series-state.json
```

创建邮件配置模板（如果不存在）：

```bash
cd <ROOT> && test -f config/email.conf.example || echo "# git send-email 配置
# 复制此文件为 config/email.conf 并填写你的信息
# Gmail 用户需要使用应用专用密码（App Password）
#
# REVIEW_EMAIL=reviewer@example.com
" > config/email.conf.example
```

## 步骤 1：依赖检查

```bash
which git python3 make
```

```bash
which sphinx-build || python3 -m sphinx --version
```

### 检查 mbsync / notmuch 可用性

```bash
which mbsync notmuch 2>&1
```

如果 mbsync 或 notmuch 不可用，提示（非阻塞，仅警告）：
- 这两个工具用于本地邮件同步和搜索，支持 `/series --check-feedback` 自动检查邮件反馈
- Fedora: `sudo dnf install isync notmuch`
- Ubuntu/Debian: `sudo apt install isync notmuch`
- 需要配置 `~/.mbsyncrc` 和 notmuch 数据库，详见各工具文档

如果可用，检查 notmuch 数据库状态：

```bash
notmuch config list 2>&1 | head -5
```

如果有缺失的核心依赖（git, python3, make），列出缺失工具并提示安装命令：
- Fedora: `sudo dnf install <packages>`
- Ubuntu/Debian: `sudo apt install <packages>`

等用户安装后再继续。

## 步骤 2：仓库克隆或更新

检查 `<ROOT>/linux/.git` 是否存在。

**不存在时**（首次克隆）：

```bash
cd <ROOT> && git clone --branch docs-next --single-branch --depth=200 git://git.kernel.org/pub/scm/linux/kernel/git/alexs/linux.git linux/
```

**已存在时**（更新）：

```bash
cd <ROOT>/linux && git fetch origin && git checkout docs-next && git pull --ff-only origin docs-next
```

如果 pull 因 force-push 失败（分叉），用 `git reset --hard origin/docs-next` 重置。

## 步骤 3：工作分支

```bash
cd <ROOT>/linux && git rev-parse --verify zh-translation-work 2>/dev/null && git checkout zh-translation-work
```

如果分支不存在：

```bash
cd <ROOT>/linux && git checkout -b zh-translation-work docs-next
```

## 步骤 4：Git 身份检查

```bash
cd <ROOT>/linux && git config user.name && git config user.email
```

如果未配置，提示用户设置。

## 步骤 5：状态报告

```bash
cd <ROOT>/linux && find Documentation/ -name '*.rst' -not -path '*/translations/*' | wc -l
```

```bash
cd <ROOT>/linux && find Documentation/translations/zh_CN/ -name '*.rst' | wc -l
```

```bash
cd <ROOT>/linux && git branch --show-current && git log --oneline -1
```

计算翻译覆盖率（中文数量 / 英文数量 × 100%）。

检查活跃补丁系列：

```bash
python3 -c "
import json
with open('<ROOT>/scripts/series-state.json') as f: data = json.load(f)
for sid, s in data.get('series', {}).items():
    if s.get('phase') != 'merged':
        phase = s['phase']
        status = s['phases'].get(phase, {}).get('status', '?')
        print(f'  {sid}: {phase}/{status} ({len(s.get(\"files\",[]))} files)')
" 2>/dev/null || echo "  (无活跃系列)"
```

用中文汇报：
- 项目根目录路径
- 仓库路径
- 当前分支和 HEAD commit
- 英文 / 中文 .rst 文件数量
- 翻译覆盖率
- 活跃补丁系列（如有）
- mbsync/notmuch 可用性

建议用户下一步运行 `/diff` 查看翻译状态，或 `/series --list` 查看补丁系列。
