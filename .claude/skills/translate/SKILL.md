---
name: translate
description: Translate or update a kernel documentation file from English to Chinese
allowed-tools: Bash, Read, Write, Edit, Grep, Glob
argument-hint: "<file-path> [--batch]"
---

# 翻译内核文档

将指定的英文文档翻译为中文，或更新已有的中文翻译。不调用外部脚本。

> **路径约定**：Bash cwd 可能被污染，**不可假设为项目根目录**。
> 项目根目录（`<ROOT>`）从 skill 的 Base directory 推导：`Base directory` 往上 3 级。
> 每条 Bash 命令用 `cd <ROOT>/linux && ...` 或 `cd <ROOT> && ...` 显式切换。

`$ARGUMENTS` 是要翻译的文件路径（相对于 Documentation/，如 `admin-guide/README.rst`）。

如果 `$ARGUMENTS` 包含 `--batch`，则启用批量模式（由 `/work` 编排调用，此处不单独处理批量逻辑）。

## 步骤 1：加载术语表

用 `Read` 读取 `config/glossary.txt`，在翻译过程中严格按照术语表保持一致性。

## 步骤 2：确定文件路径

- 英文原文: `linux/Documentation/$ARGUMENTS`
- 中文翻译: `linux/Documentation/translations/zh_CN/$ARGUMENTS`

用 `Read` 读取英文原文。检查中文翻译是否存在（用 `Glob` 或直接 `Read`）。

## 步骤 3：判断工作类型

- 如果中文文件不存在 → **新翻译**
- 如果中文文件存在 → **更新翻译**

对于更新翻译，需要查看英文变更：

```bash
cd <ROOT>/linux && git log -1 --format="%H" -- Documentation/translations/zh_CN/$ARGUMENTS
```

然后：

```bash
cd <ROOT>/linux && git diff <zh_commit>..HEAD -- Documentation/$ARGUMENTS
```

用 `Read` 读取现有中文翻译。

## 步骤 4：翻译规范

严格遵守以下规范：

**行宽**: 每行不超过 80 个显示列宽（中文字符 = 2 列宽）

**术语**: 参考 `config/glossary.txt` 中的术语表保持一致性。首次出现的术语用"中文（English）"格式。

**保留不翻译的内容**:
- 代码块（`.. code-block::`）内容
- 命令、路径、文件名、函数名、变量名
- RST 指令名（`.. note::`, `.. warning::` 等）
- 交叉引用标签（`:ref:`, `:doc:` 中的标签）
- 所有缩写（CPU, DMA, IRQ 等）

**标点**: 使用中文标点（，。；：""（）），中英文/数字间加空格。

**RST 格式**:
- 标题下划线：一个英文字符对应一个下划线符号，一个中文字符对应两个下划线符号
- 保持与原文一致的 RST 结构
- 空行分隔段落

**文件头部**（参考 https://docs.kernel.org/translations/zh_CN/how-to.html ）：

```rst
.. SPDX-License-Identifier: GPL-2.0
.. include:: ../disclaimer-zh_CN.rst

:Original: Documentation/<path>

:翻译:

 <姓名> <<邮箱>>
```

- SPDX 和 include 紧挨（无空行）
- `:Original:` 指向英文原文路径
- `:翻译:` 后空一行，译者信息前有一个空格缩进
- 译者姓名和邮箱从 `git config user.name` / `user.email` 获取

## 步骤 5：新翻译流程

1. 确保目标目录存在：

```bash
mkdir -p <ROOT>/linux/Documentation/translations/zh_CN/$(dirname $ARGUMENTS)
```

2. 逐段翻译英文原文，用 `Write` 创建中文文件
3. 添加文件头部（SPDX + disclaimer include + Original + 翻译，见步骤 4 中的头部规范）
4. 检查目录是否有 `index.rst`，如需要将新文件加入 toctree

## 步骤 6：更新翻译流程

1. 对照英文变更 diff 逐处更新中文翻译
2. 只用 `Edit` 修改受英文变更影响的部分，保留已有翻译

## 步骤 7：内联质量检查

翻译完成后，直接执行质量检查（不调用 check-warnings.sh）：

1. **行尾空白**: `Grep(pattern=" +$", path="<zh_file>")` → 用 `Edit` 修复
2. **行宽检查**:

```bash
python3 -c "
import unicodedata, sys
for i, line in enumerate(open(sys.argv[1]), 1):
    w = sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in line.rstrip('\n'))
    if w > 80: print(f'  Line {i}: width {w}')
" <ROOT>/linux/Documentation/translations/zh_CN/$ARGUMENTS
```

3. 如有问题，用 `Edit` 修复后重新检查

## 步骤 8：提交

翻译和检查完成后，提示用户确认是否提交。

先获取英文原文当前 HEAD commit 信息（用于记录翻译基准）：

```bash
cd <ROOT>/linux && git log -1 --format="%h (\"%s\")" -- Documentation/$ARGUMENTS
```

获取 git 身份：

```bash
cd <ROOT>/linux && git config user.name && git config user.email
```

Commit message 固定 4 行（用空行分隔），参考
https://docs.kernel.org/translations/zh_CN/how-to.html ：

**新翻译**：

```
docs/zh_CN: Add <path> Chinese translation

Translate Documentation/<path> into Chinese.

Translate through commit <hash>
("<subject>")

Signed-off-by: <name> <<email>>
```

**更新翻译**：

```
docs/zh_CN: Update <path> translation

Update the translation of .../<path> into Chinese.

Update the translation through commit <hash>
("<subject>")

Signed-off-by: <name> <<email>>
```

4 行缺一不可（以上四行，缺少任何一行，都将在第一轮审阅后返工）：
1. subject（`docs/zh_CN: Add/Update ...`）
2. description（`Translate/Update ...`）
3. through commit（`git log --oneline` 获取）
4. Signed-off-by
