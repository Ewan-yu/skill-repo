#!/bin/bash
# claude-code.sh - Claude Code 适配器
# 安装方式：符号链接到 ~/.claude/skills/

# 目标目录
ADAPTER_TARGET="${HOME}/.claude/skills"
ADAPTER_NAME="claude-code"

# 安装技能
adapter_install() {
    local src="$1"
    local name
    name=$(basename "$src")
    local dst="$ADAPTER_TARGET/$name"

    # 确保目标目录存在
    mkdir -p "$ADAPTER_TARGET"

    # 检查是否已存在
    if [ -L "$dst" ]; then
        # 检查是否指向同一源
        local current_target
        current_target=$(readlink "$dst")
        if [ "$current_target" = "$src" ]; then
            print_info "$name 已安装（符号链接）"
            return 0
        else
            # 指向不同源，询问是否替换
            print_warning "$name 已存在符号链接，指向: $current_target"
            if confirm "是否替换为当前版本？"; then
                rm "$dst"
            else
                return 1
            fi
        fi
    elif [ -d "$dst" ]; then
        # 存在实际目录，需要手动迁移
        print_error "$name 已存在为实际目录（非符号链接）"
        echo "    请手动迁移："
        echo "    rm -rf '$dst' && ln -s '$src' '$dst'"
        return 1
    elif [ -f "$dst" ]; then
        # 存在文件
        print_error "$name 已存在为文件"
        return 1
    fi

    # 创建符号链接
    if ln -s "$src" "$dst" 2>/dev/null; then
        print_success "$name -> $src"
        log_operation "symlink" "$src" "$dst" "true"
        push_rollback "rm '$dst'"
        return 0
    else
        # Windows Git Bash 可能需要 different approach
        print_error "创建符号链接失败: $name"
        echo "    如果是 Windows，请确保以管理员权限运行"
        echo "    或手动运行: mklink /D \"$dst\" \"$src\""
        log_operation "symlink" "$src" "$dst" "false"
        return 1
    fi
}

# 卸载技能
adapter_uninstall() {
    local name="$1"
    local dst="$ADAPTER_TARGET/$name"

    if [ -L "$dst" ]; then
        rm "$dst"
        print_success "$name 已卸载"
        log_operation "remove" "" "$dst" "true"
        return 0
    elif [ -d "$dst" ]; then
        print_warning "$name 是实际目录，跳过（请手动删除）"
        return 1
    else
        print_info "$name 未安装"
        return 0
    fi
}

# 列出已安装的技能
adapter_list() {
    if [ ! -d "$ADAPTER_TARGET" ]; then
        return
    fi

    for item in "$ADAPTER_TARGET"/*; do
        [ ! -e "$item" ] && continue
        local name
        name=$(basename "$item")
        if [ -L "$item" ]; then
            local target
            target=$(readlink "$item")
            echo "$name -> $target"
        fi
    done
}

# 检查技能是否已安装
adapter_is_installed() {
    local name="$1"
    local dst="$ADAPTER_TARGET/$name"
    [ -L "$dst" ]
}

# 获取目标目录
adapter_get_target() {
    echo "$ADAPTER_TARGET"
}
