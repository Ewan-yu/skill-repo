#!/bin/bash
# cursor.sh - Cursor 适配器
# 安装方式：复制 SKILL.md 内容作为规则文件

# 目标目录
ADAPTER_TARGET="${HOME}/.cursor/rules"
ADAPTER_NAME="cursor"

# 安装技能
adapter_install() {
    local src="$1"
    local name
    name=$(basename "$src")
    local dst="$ADAPTER_TARGET/${name}.md"
    local skill_file="$src/SKILL.md"

    # 检查 SKILL.md 是否存在
    if [ ! -f "$skill_file" ]; then
        print_error "$name: SKILL.md 不存在"
        return 1
    fi

    # 确保目标目录存在
    mkdir -p "$ADAPTER_TARGET"

    # 检查是否已存在
    if [ -f "$dst" ]; then
        print_warning "$name 已存在于 $ADAPTER_TARGET"
        if confirm "是否覆盖？"; then
            rm "$dst"
        else
            return 1
        fi
    fi

    # 提取 frontmatter 后的内容
    local body
    body=$(sed '1,/^---$/d' "$skill_file" | sed '1,/^---$/d')

    # 解析元数据
    parse_skill_meta "$src" > /dev/null 2>&1

    # 写入规则文件
    {
        echo "<!-- Skill: $name v${META_VERSION:-unknown} -->"
        echo "<!-- Agent: cursor -->"
        echo ""
        echo "$body"
    } > "$dst"

    print_success "$name -> $dst"
    log_operation "copy" "$skill_file" "$dst" "true"
    push_rollback "rm '$dst'"
    return 0
}

# 卸载技能
adapter_uninstall() {
    local name="$1"
    local dst="$ADAPTER_TARGET/${name}.md"

    if [ -f "$dst" ]; then
        rm "$dst"
        print_success "$name 已从 Cursor 卸载"
        log_operation "remove" "" "$dst" "true"
        return 0
    else
        print_info "$name 未安装在 Cursor"
        return 0
    fi
}

# 列出已安装的技能
adapter_list() {
    if [ ! -d "$ADAPTER_TARGET" ]; then
        return
    fi

    for item in "$ADAPTER_TARGET"/*.md; do
        [ ! -f "$item" ] && continue
        local name
        name=$(basename "$item" .md)
        # 检查是否是技能文件（以 <!-- Skill: 开头）
        if head -1 "$item" | grep -q '<!-- Skill:'; then
            echo "$name"
        fi
    done
}

# 检查技能是否已安装
adapter_is_installed() {
    local name="$1"
    local dst="$ADAPTER_TARGET/${name}.md"
    [ -f "$dst" ] && head -1 "$dst" | grep -q '<!-- Skill:'
}

# 获取目标目录
adapter_get_target() {
    echo "$ADAPTER_TARGET"
}
