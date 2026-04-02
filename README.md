# kernel-docs-cn-agent

Linux 内核中文翻译工具集。从翻译、质检、补丁生成到邮件发送的完整工作流。

支持任何 AI 编程工具，或纯 CLI（无 AI）。

## 快速开始

```bash
git clone https://github.com/benx-guo/kernel-docs-cn-agent.git
cd kernel-docs-cn-agent
python3 bin/kt-setup    # 克隆 docs-next 分支，检查依赖
```

前置条件：Python 3.10+、Git、Perl、Make、`git send-email`。

## 使用方式

### AI 工具

将 `docs/guide.md` 加入上下文作为入口。`docs/skills/` 下的 10 个操作指引是纯 Markdown，任何 AI 工具都能直接读取。AI 调用 `bin/` CLI 处理数据，自身负责翻译和交互。

新手可运行 `./kt` 查看可用命令，或使用 `/guide` 进入交互式引导。

### 纯 CLI

```bash
python3 bin/kt-setup                  # 初始化
python3 bin/kt-sync                   # 同步 docs-next
python3 bin/kt-diff --status          # 找需要翻译/更新的文件
# 手动翻译（参考 docs/translation-rules.md）
python3 bin/kt-check --file <path>    # 质检
python3 bin/kt-format-patch           # 生成补丁（自动 sync + rebase）
python3 bin/kt-send-patch --self      # 发给自己测试
python3 bin/kt-send-patch --submit    # 提交到邮件列表
```

## CLI 工具

所有 `bin/kt-*` 工具支持 `--json` 输出。

| 工具 | 用途 |
|------|------|
| `kt-setup` | 环境初始化 |
| `kt-sync` | 同步 docs-next + 缓存翻译状态 |
| `kt-diff` | 翻译差异分析（分页/目录/搜索） |
| `kt-check` | 质量检查（RST、行宽、checkpatch） |
| `kt-format-patch` | 补丁生成 + 验证（内置 sync + rebase） |
| `kt-send-patch` | 补丁发送（self / review / submit） |
| `kt-series` | 补丁系列生命周期管理 |
| `kt-mail` | 邮件列表搜索/查看 |
| `kt-work` | 工作流状态跟踪 |

## License

工具代码采用 [MIT](LICENSE) 许可。翻译内容遵循 Linux 内核 [GPL-2.0](https://www.gnu.org/licenses/old-licenses/gpl-2.0.html)。
