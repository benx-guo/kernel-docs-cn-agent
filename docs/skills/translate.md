# 翻译内核文档

将指定的英文文档翻译为中文，或更新已有的中文翻译。翻译是 AI 核心工作，不委托脚本。

翻译规范参见 `docs/translation-rules.md`。

> **路径约定**：`<ROOT>` 为项目根目录。每条命令用 `cd <ROOT>/linux && ...` 显式切换。

用户参数是要翻译的文件路径（相对于 Documentation/，如 `admin-guide/README.rst`）。

## 步骤 1：加载术语表

读取 `config/glossary.txt`，在翻译过程中严格按照术语表保持一致性。

## 步骤 2：确定文件路径

- 英文原文: `linux/Documentation/<文件路径>`
- 中文翻译: `linux/Documentation/translations/zh_CN/<文件路径>`

读取英文原文。检查中文翻译是否存在。

## 步骤 3：判断工作类型

- 如果中文文件不存在 → **新翻译**
- 如果中文文件存在 → **更新翻译**

对于更新翻译，查看英文变更：

```bash
cd <ROOT>/linux && git log -1 --format="%H" -- Documentation/translations/zh_CN/<文件路径>
```

```bash
cd <ROOT>/linux && git diff <zh_commit>..HEAD -- Documentation/<文件路径>
```

读取现有中文翻译。

## 步骤 4：翻译规范

严格遵守 `docs/translation-rules.md` 中的全部规范：

- **行宽**: 每行不超过 80 个显示列宽（中文字符 = 2 列宽）
- **术语**: 参考 `config/glossary.txt`，首次出现用"中文（English）"格式
- **保留不翻译**: 代码块、命令、路径、函数名、RST 指令、交叉引用标签
- **标点**: 中文标点，中英文/数字间加空格
- **RST 格式**: 标题下划线（一个英文→一个符号，一个中文→两个符号）
- **文件头部**（参考 https://docs.kernel.org/translations/zh_CN/how-to.html ）：

```rst
.. SPDX-License-Identifier: GPL-2.0
.. include:: ../disclaimer-zh_CN.rst

:Original: Documentation/<path>

:翻译:

 <姓名> <<邮箱>>
```

SPDX 和 include 紧挨无空行；用 `:翻译:` 不用 `:Translator:`。

## 步骤 5：新翻译流程

1. 确保目标目录存在：
   ```bash
   mkdir -p <ROOT>/linux/Documentation/translations/zh_CN/$(dirname <文件路径>)
   ```
2. 逐段翻译英文原文，创建中文文件
3. 添加文件头部
4. 检查目录是否有 `index.rst`，如需要将新文件加入 toctree

## 步骤 6：更新翻译流程

1. 对照英文变更 diff 逐处更新中文翻译
2. 只修改受英文变更影响的部分，保留已有翻译

## 步骤 7：质量检查

翻译完成后，用 `bin/kt-check` 检查：

```bash
cd <ROOT> && python3 bin/kt-check --file linux/Documentation/translations/zh_CN/<文件路径>
```

如有问题，修复后重新检查。

## 步骤 8：提交

翻译和检查完成后，提示用户确认是否提交。

Commit message 格式参见 `docs/commit-format.md`。

获取英文原文当前 commit 信息：

```bash
cd <ROOT>/linux && git log -1 --no-merges --format="%h (\"%s\")" -- Documentation/<文件路径>
```

获取 git 身份：

```bash
cd <ROOT>/linux && git config user.name && git config user.email
```

Commit message 固定 4 行（用空行分隔），缺一不可。
