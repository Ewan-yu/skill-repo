#!/bin/bash
# install.sh - 创建符号链接将技能安装到 Claude Code
set -e

SKILL_REPO="$(cd "$(dirname "$0")/skills" && pwd)"
CLAUDE_SKILLS="${HOME}/.claude/skills"

# 技能列表
SKILLS=(cn-stock-analysis mx-data mx-moni mx-search mx-xuangu mx-zixuan stock-valuation wxcj)

echo "安装技能..."
echo "源目录: $SKILL_REPO"
echo "目标目录: $CLAUDE_SKILLS"
echo ""

for skill in "${SKILLS[@]}"; do
    src="$SKILL_REPO/$skill"
    dst="$CLAUDE_SKILLS/$skill"

    if [ ! -d "$src" ]; then
        echo "  警告: 源目录不存在: $src (跳过 $skill)"
        continue
    fi

    if [ -L "$dst" ]; then
        echo "  已存在（符号链接）: $skill"
    elif [ -d "$dst" ]; then
        echo "  已存在（目录）: $skill -- 需手动迁移"
        echo "    迁移命令: rm -rf '$dst' && ln -s '$src' '$dst'"
    else
        ln -s "$src" "$dst"
        echo "  已安装: $skill -> $src"
    fi
done

echo ""
echo "完成。重启 Claude Code 生效。"
