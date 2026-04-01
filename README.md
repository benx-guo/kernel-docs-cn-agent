# kernel-docs-cn-agent

基于 [Claude Code](https://docs.anthropic.com/en/docs/claude-code) 的 Linux 内核中文翻译 Agent。提供从翻译、质量检查、补丁生成到邮件发送的完整工作流。

## 快速开始

### 前置条件

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI
- Git, Perl, Python 3
- `git send-email`（发送补丁用）

### 安装

```bash
git clone https://github.com/benx-guo/kernel-docs-cn-agent.git
cd kernel-docs-cn-agent

# 复制配置模板
cp .claude/settings.local.json.example .claude/settings.local.json

# 启动 Claude Code
claude
```

在 Claude Code 中运行：

```
/setup
```

这会克隆 Alex Shi 的 `docs-next` 分支到 `linux/` 目录，创建工作分支，检查依赖环境。

## 工作流

```
/diff                     # 查看翻译状态，找到需要翻译/更新的文件
/diff --dir admin-guide   # 查看某个子目录
/diff --detail <file>     # 查看某个文件的英文变更

/translate <file>         # 翻译或更新文件
/check                    # 质量检查（RST 语法、行宽、术语）

/format-patch             # 生成补丁（自动 checkpatch + htmldocs 验证）

/send-patch --self        # 先发给自己检查格式
/send-patch --review      # 发给内审
/send-patch --submit      # 提交到上游邮件列表
```

### 全流程模式

```
/work <file>              # 自动驱动翻译全流程（12 阶段）
```

### 补丁系列管理

```
/series                   # 列出活跃系列
/series --show <id>       # 查看系列详情
/series --dashboard       # 全景面板
/series --check-feedback  # 检查邮件反馈
/series --prepare-next    # 准备下一轮修改
/series --advance         # 推进阶段（内审 → 上游）
```

## 项目结构

```
.
├── CLAUDE.md                 # Agent 行为指令和翻译规范
├── .claude/skills/           # Claude Code skill 定义
│   ├── setup/                # 环境初始化
│   ├── diff/                 # 翻译差异比对
│   ├── translate/            # 执行翻译
│   ├── check/                # 质量检查
│   ├── format-patch/         # 生成补丁
│   ├── send-patch/           # 发送补丁
│   ├── mail/                 # 邮件列表操作
│   ├── series/               # 补丁系列生命周期管理
│   └── work/                 # 全流程编排
├── config/
│   ├── email.conf.example    # 邮件配置模板
│   └── glossary.txt          # 内核术语表
└── scripts/                  # 辅助脚本
```

运行 `/setup` 后会生成：

```
├── linux/                    # 内核源码（docs-next 分支）
└── outgoing/                 # 生成的补丁文件
```

## 邮件配置

参考 `config/email.conf.example` 配置 `git send-email`。Gmail 用户需要[应用专用密码](https://myaccount.google.com/apppasswords)。

## 翻译规范

详见 [CLAUDE.md](CLAUDE.md) 和 [内核官方翻译指南](https://docs.kernel.org/translations/zh_CN/how-to.html)。

要点：
- 每行不超过 80 显示列宽（中文字符 = 2 列）
- 首次出现的术语标注英文：内存屏障（memory barrier）
- 代码、命令、路径保留英文原文
- 使用中文标点，中英文之间加空格

## License

翻译内容遵循 Linux 内核 [GPL-2.0](https://www.gnu.org/licenses/old-licenses/gpl-2.0.html) 许可。
