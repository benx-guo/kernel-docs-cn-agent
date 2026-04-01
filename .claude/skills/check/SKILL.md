---
name: check
description: Run quality checks on translation files (RST syntax, line width, checkpatch)
allowed-tools: Bash, Read, Edit, Grep
argument-hint: "[--all] [--file <path>] [--fix]"
---

# 翻译质量检查

直接使用工具进行质量检查，不调用外部脚本。

> **路径约定**：Bash cwd 可能被污染，**不可假设为项目根目录**。
> 项目根目录（`<ROOT>`）从 skill 的 Base directory 推导：`Base directory` 往上 3 级。
> 每条 Bash 命令用 `cd <ROOT>/linux && ...` 或 `cd <ROOT> && ...` 显式切换。
> `<file>` 参数须为从 `<ROOT>` 起算的路径（如 `linux/Documentation/translations/zh_CN/process/howto.rst`）。

解析 `$ARGUMENTS`：提取 `--all`、`--file <path>`、`--fix`。无参数时默认 `--all`。

---

## 确定待检查文件

**`--file <path>`**: 检查指定文件（路径相对于项目根目录或 `linux/`）。

**`--all`**（默认）: 查找所有已修改的中文 .rst 文件：

```bash
cd <ROOT>/linux && { git diff --name-only HEAD 2>/dev/null; git diff --cached --name-only 2>/dev/null; } | grep 'translations/zh_CN/.*\.rst$' | sort -u
```

如果没有修改过的文件，告知用户并建议用 `--file` 指定文件。

---

## 检查项目

对每个文件执行以下检查：

### 1. 行尾空白

用 `Grep` 搜索行尾空白：

```
Grep(pattern=" +$", path="<file>", output_mode="content")
```

如有问题：
- 报告行号和数量
- 如果 `--fix`：用 `Edit` 移除每行末尾空白

### 2. Tab 字符

用 `Grep` 搜索 tab：

```
Grep(pattern="\t", path="<file>", output_mode="content")
```

报告包含 tab 的行号。Tab 不自动修复，仅报告。

### 3. 行宽检查（CJK 感知）

用 Python 一行命令精确计算显示宽度：

```bash
python3 -c "
import unicodedata, sys
for i, line in enumerate(open(sys.argv[1]), 1):
    w = sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in line.rstrip('\n'))
    if w > 80: print(f'  Line {i}: width {w}')
" <file>
```

报告超宽行的行号和宽度。行宽问题不自动修复，仅报告（需要人工判断断行位置）。

### 4. Windows 换行符

用 `Grep` 搜索 `\r`：

```
Grep(pattern="\r$", path="<file>", output_mode="count")
```

如有问题：
- 报告检测到 CRLF
- 如果 `--fix`：

```bash
sed -i 's/\r$//' <file>
```

### 5. checkpatch.pl（可选）

如果 `<ROOT>/outgoing/` 下有补丁文件：

```bash
cd <ROOT>/linux && ./scripts/checkpatch.pl <ROOT>/outgoing/*.patch
```

报告 checkpatch 发现的 ERROR 和 WARNING。

可忽略的 warning：`WARNING: added, moved or deleted file(s), does MAINTAINERS need updating?`

---

## 汇总报告

用中文汇报：
1. 每个文件的检查结果
2. 总 error 数和 warning 数
3. 如果有可自动修复的问题且未使用 `--fix`，提示可以用 `--fix` 自动修复
4. 如果使用了 `--fix`，报告修复了哪些问题，然后重新运行检查确认
