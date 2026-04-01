# 翻译差异比对

使用 `bin/kt-diff` 获取数据，用 AI 交互引导用户选择。

> **路径约定**：`<ROOT>` 为项目根目录。如果 `<ROOT>/linux/` 不存在，提示用户先运行 setup。

## 交互方式

需要用户选择时，向用户提供选项列表（最多 3-4 个选项 + 自由输入）。

## 参数

| 参数 | 说明 |
|------|------|
| （无参数） | 让用户选择模式 |
| `--status` | 全局概览 |
| `--dir` | 列出目录让用户选 |
| `--dir <subdir>` | 直接执行指定目录的翻译状态 |
| `--detail` | 列出文件让用户选 |
| `--detail <file>` | 直接执行指定文件的详细差异 |
| `--search <keyword>` | 搜索文件 |

有明确参数值时直接执行，不再询问。

---

## 无参数 — 让用户选择模式

向用户提供选项：
- **全局概览** — 显示 Top 10 过期文件
- **选择目录** — 按目录查看翻译状态
- **选择文件** — 查看指定文件差异
- **搜索文件** — 按关键词搜索

---

## `--status` / `--dir <subdir>` 模式

```bash
cd <ROOT> && python3 bin/kt-diff --status [--dir <subdir>] --json
```

解析 JSON，用中文汇报：
- HEAD 信息
- 总英文/中文文件数和覆盖率
- Top 10 过期文件（按 commits behind 降序），标注合并状态
- 缺失文件列表
- 推荐优先更新的文件

---

## `--detail <file>` 模式

```bash
cd <ROOT> && python3 bin/kt-diff --detail <file> --json
```

解析 JSON，用中文汇报：
- 中文翻译最后更新时间和 commit
- 合并状态
- 英文变更次数和 commit 列表
- 变更内容摘要（分析 diff）

---

## `--dir`（不带目录名）— 选择目录

```bash
cd <ROOT>/linux && find Documentation/translations/zh_CN/ -name '*.rst' | sed 's|Documentation/translations/zh_CN/||' | sed 's|/[^/]*$||' | grep -v '/' | sort | uniq -c | sort -rn
```

列出前 3 个最大的目录让用户选。

---

## `--detail`（不带文件名）/ `--search <keyword>` — 选择文件

先让用户选择目录，再选择文件，最后执行 `--detail <file>`。

---

## 结果展示

用中文向用户汇报，建议使用 translate（见 `docs/skills/translate.md`）开始翻译工作。
