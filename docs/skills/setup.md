# 初始化内核翻译环境

使用 `bin/kt-setup` 完成环境初始化。

> **路径约定**：`<ROOT>` 为项目根目录（包含 `docs/` 和 `bin/` 的目录）。
> 每条命令用 `cd <ROOT> && ...` 显式切换。

## 步骤 1：完整初始化

如果用户要求完整初始化（首次使用或无参数）：

```bash
cd <ROOT> && python3 bin/kt-setup
```

如果仓库不存在，这会自动克隆 Alex Shi 的 `docs-next` 分支（约 200 层深度）并初始化目录结构。工作分支由 `kt-series --create` 按需创建（`zh-work/<series-id>`）。

## 步骤 2：依赖检查

如果用户只想检查依赖：

```bash
cd <ROOT> && python3 bin/kt-setup --check-deps
```

## 步骤 3：状态报告

```bash
cd <ROOT> && python3 bin/kt-setup --status
```

## 步骤 4：Git 身份检查

```bash
cd <ROOT>/linux && git config user.name && git config user.email
```

如果未配置，提示用户设置。

## 汇报

用中文汇报初始化结果：
- 项目根目录路径
- 仓库状态（克隆/更新）
- 当前分支和 HEAD commit
- 英文/中文文件数量和覆盖率
- 活跃补丁系列（如有）
- 依赖检查结果

建议下一步运行 `diff`（见 `docs/skills/diff.md`）查看翻译状态。
