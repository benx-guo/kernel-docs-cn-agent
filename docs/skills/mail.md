# 邮件列表查看与回复

使用 `bin/kt-mail` 获取邮件数据，AI 负责总结和起草回复。

> **路径约定**：`<ROOT>` 为项目根目录。

## 模式 1：`--search [query]` — 搜索邮件

```bash
cd <ROOT> && python3 bin/kt-mail --search "<query>" [--local] --json
```

用中文汇报搜索结果：编号列表，每条包含标题、作者、日期、URL。

## 模式 2：`--thread <id|url>` — 查看完整线程

```bash
cd <ROOT> && python3 bin/kt-mail --thread "<id_or_url>" [--local] --json
```

用中文总结线程内容。

## 模式 3：`--replies <id|url>` — 只看回复

同模式 2，但只展示 `is_reply=true` 的消息。

用中文总结审核意见。

## 模式 4：`--reply <id|url>` — 起草回复（AI 处理）

这个模式由 AI 自行处理：

1. 先用模式 2 获取完整线程内容
2. 用中文总结审核者的意见和建议
3. 根据审核意见，用英文起草回复邮件：
   - 使用 bottom-posting 风格
   - 逐条回应审核意见
   - 语气礼貌专业
   - 如果涉及代码修改，说明会在 v2/vN 补丁中修复
4. 将起草的回复展示给用户确认

## 注意事项

- 所有对用户的汇报使用中文
- 起草的回复邮件使用英文（内核社区通用语言）
- `--local` 模式使用本地 notmuch 数据库，速度更快
