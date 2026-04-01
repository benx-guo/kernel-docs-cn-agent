# 生成补丁

使用 `bin/kt-format-patch` 生成补丁并验证。

> **路径约定**：`<ROOT>` 为项目根目录。

## 生成并验证补丁

```bash
cd <ROOT> && python3 bin/kt-format-patch [用户参数] --json
```

此命令自动完成：
- 如果指定 `--series`（或当前在 `zh-work/*` 分支时自动推断），切到该 series 的工作分支
- 检查 docs-next..HEAD 的提交
- 清理并生成补丁到 `outgoing/<series-id>/`（无 series 时生成到 `outgoing/`）
- 多补丁时自动加 `--cover-letter --thread=shallow`
- 运行 `checkpatch.pl` 验证每个补丁
- 运行 `make htmldocs` 检查 RST 构建
- 从 series-state.json 读取版本号并更新 commits
- 完成后切回原分支

## 解析结果

解析 JSON 输出，用中文汇报：
1. 生成了多少个补丁，每个的文件名和主题
2. 推荐收件人列表
3. checkpatch 结果（每个补丁的 errors/warnings）
4. htmldocs 构建结果
5. 如果有 `--series`，显示系列 ID 和当前版本

## 验证结果

如果 checkpatch 有 error 或 htmldocs 有 zh_CN 相关 error：
- 列出问题
- 提示修复后重新运行

如果全部通过，建议下一步发送补丁（`send-patch --self`）。

## Cover Letter 提醒

如果生成了 cover letter（`outgoing/0000-cover-letter.patch`），提醒用户编辑其内容。

Commit message 格式参见 `docs/commit-format.md`。
