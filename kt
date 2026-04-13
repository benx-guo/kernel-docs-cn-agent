#!/bin/bash
# kt - Linux 内核中文翻译工具集入口
cd "$(dirname "$0")"

# Generate CLAUDE.md, .claude/commands/, and settings (skip if already correct)
ensure_link() { [ "$(readlink "$2" 2>/dev/null)" = "$1" ] || ln -sf "$1" "$2"; }
ensure_link docs/guide.md CLAUDE.md
mkdir -p .claude/commands
for skill in docs/skills/*.md; do
  ensure_link "../../$skill" ".claude/commands/$(basename "$skill")"
done
# Seed settings from example if not yet configured
if [ ! -f .claude/settings.local.json ]; then
  cp config/claude-settings.example.json .claude/settings.local.json
  echo "已从 config/claude-settings.example.json 初始化权限配置。"
fi

cat <<'EOF'
Linux 内核中文翻译工具集

▸ 新手           /guide    8 步引导，从零走完一次完整翻译
▸ 老手           /work     全流程编排（自动处理环境，直接开干）

单独命令：
  /setup          初始化翻译环境
  /diff           查找需要翻译/更新的文件
  /translate      翻译或更新文件
  /check          质量检查（RST、行宽、checkpatch）
  /format-patch   生成内核补丁
  /send-patch     发送补丁（自测/内审/提交）
  /mail           搜索/查看内核邮件列表
  /series         管理补丁系列生命周期

完整流程（12 个 work stages）：

  CHK → TL → QA → PAT → E1 → E2
  选文件  翻译  质检  补丁  自测  内审
                                  ↓
                          ┌── W1 ←──┐
                          │    ↓     │  内审循环
                          │  RV1 ───┘  （修订→重发）
                          │    ↓ approved
                          └→  E3  正式提交到邮件列表
                                ↓
                         ┌── W2 ←──┐
                         │    ↓     │  社区评审循环
                         │  RV2 ───┘  （修订→重发）
                         │    ↓ accepted
                         └→ ARC  归档，翻译合入内核
EOF

exec claude
