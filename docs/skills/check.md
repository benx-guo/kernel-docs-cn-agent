# 翻译质量检查

使用 `bin/kt-check` 执行质量检查。

> **路径约定**：`<ROOT>` 为项目根目录。

## 执行检查

```bash
cd <ROOT> && python3 bin/kt-check [用户参数] --json
```

解析 JSON 输出，用中文向用户汇报：

1. 每个文件的检查结果：
   - 行尾空白（数量和行号）
   - Tab 字符
   - 行宽超限（CJK 感知，80 列）
   - CRLF 换行符
2. 补丁 checkpatch 结果（如有 outgoing/ 补丁）
3. 总 error 和 warning 数

## 自动修复

如果有可修复问题且用户未使用 `--fix`，提示：

> 发现 N 个可自动修复的问题（行尾空白、CRLF）。用 `--fix` 自动修复。

如果用户使用了 `--fix`：

```bash
cd <ROOT> && python3 bin/kt-check [用户参数] --fix --json
```

修复后重新运行检查确认。

## 行宽问题

行宽超限需要人工判断断行位置，不自动修复。如果用户要求修复，在合适位置手动断行。

翻译规范参见 `docs/translation-rules.md`。
