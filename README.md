# kernel-docs-cn-agent

Linux 内核中文翻译工具集。提供从翻译、质量检查、补丁生成到邮件发送的完整工作流。

支持多种使用方式：任何 AI 编程工具，或纯 CLI（无 AI）。

> **AI Agent 入口**：请先阅读 [`docs/guide.md`](docs/guide.md)，其中包含完整的文档索引、操作指引和工作流说明。

## 快速开始

### 前置条件

- Python 3.10+
- Git, Perl, Make
- `git send-email`（发送补丁用）

### 安装

```bash
git clone https://github.com/benx-guo/kernel-docs-cn-agent.git
cd kernel-docs-cn-agent
```

### 初始化

```bash
python3 bin/kt-setup
```

这会克隆 Alex Shi 的 `docs-next` 分支到 `linux/` 目录，创建工作分支，检查依赖环境。

## 使用方式

### AI 工具用户

1. 将 `docs/guide.md` 加入 AI 上下文作为入口
2. `docs/skills/` 中的 9 个操作指引是纯 Markdown，任何 AI 工具都可以直接使用
3. AI 调用 `bin/` CLI 工具处理数据，自身负责翻译和交互

```bash
python3 bin/kt-setup          # 初始化
python3 bin/kt-diff --status  # 找文件
# ... AI 按 docs/skills/translate.md 翻译 ...
python3 bin/kt-check --file <path>    # 质量检查
python3 bin/kt-format-patch           # 生成补丁
python3 bin/kt-send-patch --self      # 测试发送
```

### 纯 CLI 用户（无 AI）

```bash
python3 bin/kt-setup                  # 1. 初始化
python3 bin/kt-diff --status          # 2. 找需要翻译/更新的文件
# 手动翻译（参考 docs/translation-rules.md）
python3 bin/kt-check --file <path>    # 3. 质量检查
python3 bin/kt-format-patch           # 4. 生成补丁
python3 bin/kt-send-patch --self      # 5. 发给自己测试
python3 bin/kt-send-patch --submit    # 6. 提交到邮件列表
```

## 项目结构

```
.
├── docs/                        # 知识文档 + 操作指引（框架无关）
│   ├── skills/                  # 各功能操作指引（任何 AI 工具可读）
├── lib/                         # 共享 Python 库（仅 stdlib，无需 pip）
├── bin/                         # 独立 CLI 工具
│   ├── kt-setup                 # 环境初始化
│   ├── kt-diff                  # 翻译差异分析
│   ├── kt-check                 # 质量检查
│   ├── kt-format-patch          # 补丁生成 + 验证
│   ├── kt-send-patch            # 补丁发送
│   ├── kt-series                # 补丁系列管理
│   ├── kt-mail                  # 邮件列表搜索/查看
│   └── kt-work                  # 工作流状态管理
├── config/
│   ├── email.conf.example       # 邮件配置模板
│   └── glossary.txt             # 内核术语表（246 个术语）
└── scripts/                     # Web/TUI 辅助工具
    ├── diff-web.py              # 翻译状态 Web 仪表盘
    ├── series-dashboard.py      # 补丁系列 TUI
    └── serve-docs.py            # 文档实时预览服务器
```

## CLI 工具

所有 `bin/kt-*` 工具支持 `--json` 参数输出 JSON，方便其他工具集成。

| 工具 | 用途 | 示例 |
|------|------|------|
| `kt-setup` | 环境初始化 | `kt-setup --check-deps` |
| `kt-diff` | 翻译差异分析 | `kt-diff --status --json` |
| `kt-check` | 质量检查 | `kt-check --file <path> --fix` |
| `kt-format-patch` | 补丁生成 | `kt-format-patch --series <id>` |
| `kt-send-patch` | 补丁发送 | `kt-send-patch --self` |
| `kt-series` | 系列管理 | `kt-series --dashboard` |
| `kt-mail` | 邮件搜索 | `kt-mail --search "docs/zh_CN"` |
| `kt-work` | 工作流状态 | `kt-work --next` |

## 翻译规范

详见 `docs/translation-rules.md` 和[内核官方翻译指南](https://docs.kernel.org/translations/zh_CN/how-to.html)。

要点：
- 每行不超过 80 显示列宽（中文字符 = 2 列）
- 首次出现的术语标注英文：内存屏障（memory barrier）
- 代码、命令、路径保留英文原文
- 使用中文标点，中英文之间加空格

## 邮件配置

参考 `config/email.conf.example` 配置 `git send-email`。Gmail 用户需要[应用专用密码](https://myaccount.google.com/apppasswords)。

## License

工具代码（bin/、lib/、docs/）采用 [MIT](LICENSE) 许可。翻译内容遵循 Linux 内核 [GPL-2.0](https://www.gnu.org/licenses/old-licenses/gpl-2.0.html)。
