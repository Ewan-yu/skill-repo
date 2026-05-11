#!/bin/bash
# install.sh - 技能安装脚本 v2.0
# 支持多智能体、交互式选择、批量安装

set -e

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 加载共享函数
source "$SCRIPT_DIR/lib/common.sh"

# 默认值
ACTION="install"
AGENT=""
SKILLS=()
YES_MODE=false
DRY_RUN=false

# ============================================================================
# 帮助信息
# ============================================================================

show_help() {
    cat << EOF
Skill Installer v2.0

用法: install.sh [action] [options]

Actions:
  install     安装选中的技能（默认）
  uninstall   卸载已安装的技能
  list        列出已安装的技能
  scan        列出所有可用技能

Options:
  -a, --agent <agent>       目标智能体: claude-code, cursor, windsurf, cline, all
  -s, --skills <names>      要安装的技能（逗号分隔）
  -y, --yes                 非交互模式，安装所有技能
  -c, --config <path>       使用自定义配置文件
  --dry-run                 显示将要执行的操作，但不实际执行
  -h, --help                显示此帮助信息

示例:
  ./install.sh install --agent claude-code                           # 交互式安装
  ./install.sh install --agent cursor --skills cn-stock-analysis,mx-data  # 批量安装
  ./install.sh install --agent all --yes                             # 全部安装
  ./install.sh uninstall --skills mx-data --agent all                # 卸载
  ./install.sh list --agent claude-code                              # 列出已安装
  ./install.sh scan                                                  # 列出可用技能

EOF
}

# ============================================================================
# 参数解析
# ============================================================================

parse_args() {
    while [ $# -gt 0 ]; do
        case "$1" in
            install|uninstall|list|scan)
                ACTION="$1"
                ;;
            -a|--agent)
                AGENT="$2"
                shift
                ;;
            -s|--skills)
                IFS=',' read -ra SKILLS <<< "$2"
                shift
                ;;
            -y|--yes)
                YES_MODE=true
                ;;
            -c|--config)
                CONFIG_FILE="$2"
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                echo "未知参数: $1"
                echo "使用 -h 查看帮助"
                exit 1
                ;;
        esac
        shift
    done
}

# ============================================================================
# 智能体管理
# ============================================================================

# 获取所有支持的智能体
get_all_agents() {
    echo "claude-code cursor windsurf cline"
}

# 加载智能体适配器
load_adapter() {
    local agent="$1"
    local adapter_file="$SCRIPT_DIR/lib/adapters/${agent}.sh"

    if [ ! -f "$adapter_file" ]; then
        print_error "不支持的智能体: $agent"
        return 1
    fi

    source "$adapter_file"
    return 0
}

# 选择智能体
select_agent() {
    if [ -n "$AGENT" ]; then
        # 验证智能体
        local valid_agents
        valid_agents=($(get_all_agents))
        local valid=false
        for a in "${valid_agents[@]}"; do
            [ "$a" = "$AGENT" ] && valid=true && break
        done

        if [ "$valid" = false ]; then
            print_error "不支持的智能体: $AGENT"
            echo "支持的智能体: ${valid_agents[*]}"
            exit 1
        fi
        return
    fi

    # 交互式选择
    echo -e "${CYAN}选择智能体:${NC}"
    echo "  1. Claude Code"
    echo "  2. Cursor"
    echo "  3. Windsurf"
    echo "  4. Cline"
    echo "  5. All"
    echo ""
    echo -n -e "${GREEN}> ${NC}"

    read -n1 choice
    echo ""

    case "$choice" in
        1) AGENT="claude-code" ;;
        2) AGENT="cursor" ;;
        3) AGENT="windsurf" ;;
        4) AGENT="cline" ;;
        5) AGENT="all" ;;
        *)
            print_error "无效选择"
            exit 1
            ;;
    esac
}

# ============================================================================
# 安装操作
# ============================================================================

# 安装单个技能到单个智能体
install_skill_to_agent() {
    local skill="$1"
    local agent="$2"
    local src="$SKILLS_DIR/$skill"

    load_adapter "$agent"

    if [ "$DRY_RUN" = true ]; then
        print_info "[DRY RUN] 将安装: $skill -> $(adapter_get_target)"
        return 0
    fi

    adapter_install "$src" "$skill"
    local result=$?

    # 添加到配置
    if [ $result -eq 0 ]; then
        add_to_config "$agent" "$skill"
    fi

    return $result
}

# 卸载单个技能从单个智能体
uninstall_skill_from_agent() {
    local skill="$1"
    local agent="$2"

    load_adapter "$agent"

    if [ "$DRY_RUN" = true ]; then
        print_info "[DRY RUN] 将卸载: $skill"
        return 0
    fi

    adapter_uninstall "$skill"
    local result=$?

    if [ $result -eq 0 ]; then
        remove_from_config "$agent" "$skill"
    fi

    return $result
}

# 安装技能到所有智能体
install_to_all_agents() {
    local skills=("$@")
    local agents
    agents=($(get_all_agents))

    for agent in "${agents[@]}"; do
        echo ""
        echo -e "${CYAN}安装到 $agent:${NC}"
        for skill in "${skills[@]}"; do
            install_skill_to_agent "$skill" "$agent" || true
        done
    done
}

# 从所有智能体卸载技能
uninstall_from_all_agents() {
    local skills=("$@")
    local agents
    agents=($(get_all_agents))

    for agent in "${agents[@]}"; do
        echo ""
        echo -e "${CYAN}从 $agent 卸载:${NC}"
        for skill in "${skills[@]}"; do
            uninstall_skill_from_agent "$skill" "$agent" || true
        done
    done
}

# ============================================================================
# 主流程
# ============================================================================

# 安装操作
do_install() {
    select_agent

    # 如果没有指定技能，进入交互模式
    if [ ${#SKILLS[@]} -eq 0 ]; then
        if [ "$YES_MODE" = true ]; then
            # 非交互模式：选择所有技能
            SKILLS=($(scan_skills))
        else
            # 交互模式：显示菜单
            if [ "$AGENT" = "all" ]; then
                # 对于 all，先选择一个智能体的菜单
                SKILLS=($(show_skill_menu "claude-code"))
            else
                SKILLS=($(show_skill_menu "$AGENT"))
            fi
        fi
    fi

    if [ ${#SKILLS[@]} -eq 0 ]; then
        print_warning "未选择任何技能"
        return
    fi

    echo ""
    echo -e "${CYAN}准备安装 ${#SKILLS[@]} 个技能:${NC}"
    for skill in "${SKILLS[@]}"; do
        echo "  - $skill"
    done

    if [ "$DRY_RUN" = true ]; then
        echo ""
        print_info "[DRY RUN] 以上操作将被执行，但未实际执行"
        return
    fi

    if [ "$YES_MODE" = false ]; then
        echo ""
        if ! confirm "确认安装？" true; then
            print_warning "已取消"
            return
        fi
    fi

    echo ""

    if [ "$AGENT" = "all" ]; then
        install_to_all_agents "${SKILLS[@]}"
    else
        for skill in "${SKILLS[@]}"; do
            install_skill_to_agent "$skill" "$AGENT" || true
        done
    fi

    echo ""
    print_success "安装完成！"
    echo ""

    # 显示环境变量提示
    local env_hint_shown=false
    for skill in "${SKILLS[@]}"; do
        local missing
        missing=($(get_missing_env_vars "$SKILLS_DIR/$skill"))
        if [ ${#missing[@]} -gt 0 ]; then
            if [ "$env_hint_shown" = false ]; then
                echo -e "${YELLOW}注意: 以下技能需要环境变量:${NC}"
                env_hint_shown=true
            fi
            echo "  $skill: ${missing[*]}"
        fi
    done

    if [ "$env_hint_shown" = true ]; then
        echo ""
        echo "请确保已设置上述环境变量，否则相关功能可能无法正常工作。"
    fi
}

# 卸载操作
do_uninstall() {
    select_agent

    if [ ${#SKILLS[@]} -eq 0 ]; then
        print_error "请指定要卸载的技能 (-s/--skills)"
        exit 1
    fi

    echo ""
    echo -e "${CYAN}准备卸载 ${#SKILLS[@]} 个技能:${NC}"
    for skill in "${SKILLS[@]}"; do
        echo "  - $skill"
    done

    if [ "$YES_MODE" = false ]; then
        echo ""
        if ! confirm "确认卸载？" false; then
            print_warning "已取消"
            return
        fi
    fi

    echo ""

    if [ "$AGENT" = "all" ]; then
        uninstall_from_all_agents "${SKILLS[@]}"
    else
        for skill in "${SKILLS[@]}"; do
            uninstall_skill_from_agent "$skill" "$AGENT" || true
        done
    fi

    echo ""
    print_success "卸载完成！"
}

# 列出已安装的技能
do_list() {
    select_agent

    echo ""
    echo -e "${CYAN}已安装的技能 ($AGENT):${NC}"

    if [ "$AGENT" = "all" ]; then
        local agents
        agents=($(get_all_agents))
        for agent in "${agents[@]}"; do
            load_adapter "$agent"
            local target
            target=$(adapter_get_target)
            echo ""
            echo -e "${YELLOW}$agent ($target):${NC}"
            local installed
            installed=($(adapter_list 2>/dev/null || true))
            if [ ${#installed[@]} -eq 0 ]; then
                echo "  (无)"
            else
                for item in "${installed[@]}"; do
                    echo "  - $item"
                done
            fi
        done
    else
        load_adapter "$AGENT"
        local target
        target=$(adapter_get_target)
        echo -e "${YELLOW}目标目录: $target${NC}"
        local installed
        installed=($(adapter_list 2>/dev/null || true))
        if [ ${#installed[@]} -eq 0 ]; then
            echo "  (无)"
        else
            for item in "${installed[@]}"; do
                echo "  - $item"
            done
        fi
    fi
}

# 列出所有可用技能
do_scan() {
    echo ""
    echo -e "${CYAN}可用技能:${NC}"
    echo ""

    local skills
    skills=($(scan_skills))
    local count=0

    for skill in "${skills[@]}"; do
        count=$((count + 1))
        parse_skill_meta "$SKILLS_DIR/$skill" > /dev/null 2>&1

        local version="${META_VERSION:-未知}"
        local desc="${META_DESCRIPTION:-}"
        local display_name="${META_DISPLAY_NAME:-}"

        printf "  %2d. %-25s" $count "$skill"

        if [ -n "$display_name" ] && [ "$display_name" != "$skill" ]; then
            printf " %s" "$display_name"
        fi

        if [ -n "$version" ] && [ "$version" != "未知" ]; then
            printf " v%s" "$version"
        fi

        echo ""

        if [ -n "$desc" ]; then
            echo "      $desc"
        fi

        # 检查环境变量
        local missing
        missing=($(get_missing_env_vars "$SKILLS_DIR/$skill"))
        if [ ${#missing[@]} -gt 0 ]; then
            echo -e "      ${YELLOW}需要: ${missing[*]}${NC}"
        fi

        echo ""
    done

    echo -e "${BLUE}共 $count 个技能${NC}"
}

# ============================================================================
# 入口
# ============================================================================

main() {
    parse_args "$@"

    case "$ACTION" in
        install)
            do_install
            ;;
        uninstall)
            do_uninstall
            ;;
        list)
            do_list
            ;;
        scan)
            do_scan
            ;;
        *)
            print_error "未知操作: $ACTION"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
