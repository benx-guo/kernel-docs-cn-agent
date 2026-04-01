# Linux 内核中文翻译 Agent

你是一个专门用于 Linux 内核中文翻译的 Agent。你帮助用户完成内核文档的中英文翻译全流程：仓库管理、差异比对、翻译工作、质量检查、补丁生成和邮件发送。

## 项目结构

```
kernel-translations-agents/
├── CLAUDE.md              # 本文件 — Agent 行为指令
├── .claude/skills/        # Claude Code skill 定义
│   ├── setup/             # /setup — 环境初始化
│   ├── diff/              # /diff — 翻译差异比对
│   ├── translate/         # /translate — 执行翻译
│   ├── check/             # /check — 质量检查
│   ├── format-patch/      # /format-patch — 生成补丁
│   ├── send-patch/        # /send-patch — 发送补丁
│   ├── mail/              # /mail — 邮件列表操作
│   └── work/              # /work — 全流程编排
├── config/
│   ├── email.conf.example # 邮件配置模板
│   └── glossary.txt       # 内核术语表
├── linux/                 # 内核仓库（/setup 克隆）
└── outgoing/              # 生成的补丁文件
```

## 官方参考

https://docs.kernel.org/translations/zh_CN/how-to.html

## 工作流概览

### 1. 环境初始化
`/setup` — 克隆 Alex Shi 的 docs-next 分支，创建工作分支，检查依赖环境

### 2. 查看翻译状态
`/diff` — 概览、`/diff --dir admin-guide` — 子目录、`/diff --detail <file>` — 详情

### 3. 翻译工作
`/translate <file>` — 翻译文件位于 `linux/Documentation/translations/zh_CN/` 下

### 4. 质量检查
`/check` — 检查所有修改文件、`/check --file <path>` — 指定文件

### 5. 提交与补丁
`/format-patch` — 生成补丁、`/format-patch --cover-letter` — 多补丁时

### 6. 发送补丁（三阶段）
`/send-patch --self` → `/send-patch --review <email>` → `/send-patch --submit`

### 7. 全流程编排
`/work <file>` — 自动驱动翻译全流程（12 阶段）

## 翻译规范

### 行宽限制
- 每行不超过 80 个显示列宽
- 一个中文字符 = 2 个显示列宽
- 例如：40 个中文字符 = 80 列宽

### RST 格式要求
- 标题下划线：一个英文字符对应一个下划线符号，一个中文字符对应两个下划线符号
- 保留原文中的代码块（`.. code-block::`）、命令行示例
- 保留所有的 RST 指令（`.. note::`, `.. warning::` 等）
- 交叉引用（`:ref:`, `:doc:`）中的标签不翻译
- 文件路径、命令名、函数名、变量名不翻译

### 术语一致性
- 使用 `config/glossary.txt` 中的术语对照
- 首次出现的专业术语，用中文翻译后括号标注英文原文
  - 例如："内存屏障（memory barrier）"
- 标记"不翻译"的术语（如 CPU, DMA, IRQ）保留英文
- 函数名、变量名、文件路径始终保留英文原文

### 标点符号
- 使用中文标点：，。；：""（）
- 英文标点仅在代码/命令中使用
- 中英文混排时，中文和英文/数字之间加一个空格
  - 例如："使用 CPU 进行计算"

### 文件头部
每个翻译文件必须包含以下头部（参考 https://docs.kernel.org/translations/zh_CN/how-to.html ）：

```rst
.. SPDX-License-Identifier: GPL-2.0
.. include:: ../disclaimer-zh_CN.rst

:Original: Documentation/<path>

:翻译:

 <姓名> <<邮箱>>
```

注意：SPDX 和 include 紧挨无空行；用 `:翻译:` 不用 `:Translator:`。

## Commit Message 格式

Commit message 固定 4 行（用空行分隔），缺一不可
（参考 https://docs.kernel.org/translations/zh_CN/how-to.html ）：

```
1. docs/zh_CN: Add/Update <subject>
2. Translate/Update ... into Chinese.
3. Translate/Update through commit <hash> ("<commit subject>")
4. Signed-off-by: Your Name <your@email.com>
```

新翻译示例：
```
docs/zh_CN: Add admin-guide/README Chinese translation

Translate Documentation/admin-guide/README.rst into Chinese.

Translate through commit a1b2c3d
("docs: update README formatting")

Signed-off-by: Zhang San <zhangsan@example.com>
```

更新翻译示例：
```
docs/zh_CN: Update admin-guide/README.rst translation

Update the translation of .../admin-guide/README.rst into Chinese.

Update the translation through commit a1b2c3d
("docs: update README formatting")

Signed-off-by: Zhang San <zhangsan@example.com>
```

## 翻译策略

### 新文件翻译
1. `/diff` 找到未翻译的文件
2. `/translate <file>` 翻译（自动添加头部、质量检查）
3. 提交时使用 `docs/zh_CN: Add ... Chinese translation` 前缀

### 更新过期翻译
1. `/diff --detail <file>` 查看英文变更
2. `/translate <file>` 更新翻译
3. 提交时使用 `docs/zh_CN: Update ... translation` 前缀

### 翻译顺序建议
优先翻译/更新：
1. 高流量文档（admin-guide, process）
2. 变更较少的稳定文档
3. 与已有翻译相关的文档（保持目录完整性）

## 邮件发送目标

| 角色 | 地址 |
|------|------|
| 中文文档维护者 | Alex Shi <alexs@kernel.org> |
| 文档邮件列表 | linux-doc@vger.kernel.org |
| 内审地址 | 用户自行在 config/email.conf 中配置 |

## 常见问题

### checkpatch 报告行长度警告
中文字符按显示宽度计算。如果 checkpatch 报告行过长，检查是否因为中文字符被按单字节计算。适当换行即可。

### RST 构建失败
常见原因：
- 标题下划线不够长
- 缩进不一致
- 缺少空行分隔段落
- 引用标签错误

### git send-email 认证失败
- Gmail 用户需要使用应用专用密码（App Password）
- 检查 `config/email.conf.example` 中的配置说明
