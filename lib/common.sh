#!/bin/bash
# common.sh - 共享函数库
# 提供技能发现、元数据解析、配置管理、交互式菜单等功能

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 仓库根目录
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_DIR="$REPO_DIR/skills"
CONFIG_FILE="$REPO_DIR/install-config.json"
INSTALL_LOG="$REPO_DIR/.install-log"

# 回滚栈
ROLLBACK_STACK=()

# ============================================================================
# 技能发现
# ============================================================================

# 扫描所有可用技能
scan_skills() {
    local exclude_patterns=('*-workspace' '*.old' '*.bak')

    for dir in "$SKILLS_DIR"/*/; do
        [ ! -d "$dir" ] && continue
        local name
        name=$(basename "$dir")

        # 排除模式匹配
        [[ "$name" == *-workspace ]] && continue
        [[ "$name" == *.old ]] && continue
        [[ "$name" == *.bak ]] && continue

        # 必须有 SKILL.md
        [ ! -f "$dir/SKILL.md" ] && continue

        echo "$name"
    done
}

# 获取技能数量
count_skills() {
    scan_skills | wc -l | tr -d ' '
}

# ============================================================================
# 元数据解析
# ============================================================================

# 解析 SKILL.md frontmatter
# 使用全局变量返回：META_NAME, META_VERSION, META_DESCRIPTION, META_DISPLAY_NAME, META_REQUIRED_ENV_VARS
parse_skill_meta() {
    local skill_dir="$1"
    local skill_file="$skill_dir/SKILL.md"

    # 初始化默认值
    META_NAME=""
    META_VERSION=""
    META_DESCRIPTION=""
    META_DISPLAY_NAME=""
    META_REQUIRED_ENV_VARS=()

    [ ! -f "$skill_file" ] && return 1

    # 提取 frontmatter（两个 --- 之间的内容）
    local frontmatter
    frontmatter=$(sed -n '/^---$/,/^---$/p' "$skill_file" | sed '1d;$d')

    # 解析各个字段
    META_NAME=$(echo "$frontmatter" | grep -E '^name:' | sed 's/^name: *//' | tr -d '"' | tr -d "'")
    META_VERSION=$(echo "$frontmatter" | grep -E '^version:' | sed 's/^version: *//' | tr -d '"' | tr -d "'")
    META_DISPLAY_NAME=$(echo "$frontmatter" | grep -E '^display_name:' | sed 's/^display_name: *//' | tr -d '"' | tr -d "'")

    # description 可能是多行的，取第一行
    META_DESCRIPTION=$(echo "$frontmatter" | grep -A1 '^description:' | head -2 | tr '\n' ' ' | sed 's/^description: *//' | sed 's/^[[:space:]]*//' | head -c 60)

    # 解析 required_env_vars 数组
    local in_env_vars=0
    local env_line
    while IFS= read -r env_line; do
        if [[ "$env_line" =~ ^required_env_vars: ]]; then
            in_env_vars=1
            # 检查是否在同一行有值
            local inline
            inline=$(echo "$env_line" | sed 's/^required_env_vars: *//')
            if [ -n "$inline" ] && [ "$inline" != "[]" ]; then
                META_REQUIRED_ENV_VARS+=("$inline")
            fi
        elif [ $in_env_vars -eq 1 ]; then
            if [[ "$env_line" =~ ^[[:space:]]*-[[:space:]]*(.*) ]]; then
                local var_name
                var_name=$(echo "${BASH_REMATCH[1]}" | tr -d '"' | tr -d "'")
                META_REQUIRED_ENV_VARS+=("$var_name")
            elif [[ "$env_line" =~ ^[a-zA-Z_] ]]; then
                in_env_vars=0
            fi
        fi
    done <<< "$frontmatter"

    # 如果没有 version，尝试从 _meta.json 获取
    if [ -z "$META_VERSION" ] && [ -f "$skill_dir/_meta.json" ]; then
        META_VERSION=$(grep -o '"version": *"[^"]*"' "$skill_dir/_meta.json" | sed 's/"version": *"//' | tr -d '"')
    fi

    return 0
}

# 检查环境变量是否已设置
check_env_var() {
    local var_name="$1"
    [ -n "${!var_name+x}" ] && [ -n "${!var_name}" ]
}

# 获取缺失的环境变量列表
get_missing_env_vars() {
    local skill_dir="$1"
    local missing=()

    parse_skill_meta "$skill_dir" > /dev/null 2>&1

    for var in "${META_REQUIRED_ENV_VARS[@]}"; do
        if ! check_env_var "$var"; then
            missing+=("$var")
        fi
    done

    echo "${missing[@]}"
}

# ============================================================================
# 配置文件管理
# ============================================================================

# 加载配置文件
load_config() {
    if [ ! -f "$CONFIG_FILE" ]; then
        # 返回默认配置
        echo '{"version":1,"agents":{},"last_installed":null}'
        return
    fi
    cat "$CONFIG_FILE"
}

# 保存配置文件
save_config() {
    local config="$1"
    echo "$config" | python3 -m json.tool > "$CONFIG_FILE" 2>/dev/null || echo "$config" > "$CONFIG_FILE"
}

# 获取指定智能体的已安装技能列表
get_installed_skills() {
    local agent="$1"
    local config
    config=$(load_config)

    # 使用 Python 解析 JSON（更可靠）
    echo "$config" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    skills = data.get('agents', {}).get('$agent', {}).get('skills', [])
    print('\n'.join(skills))
except:
    pass
" 2>/dev/null
}

# 检查技能是否已安装
is_installed() {
    local agent="$1"
    local skill="$2"
    get_installed_skills "$agent" | grep -q "^${skill}$"
}

# 添加技能到配置
add_to_config() {
    local agent="$1"
    local skill="$2"
    local config
    config=$(load_config)

    echo "$config" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if 'agents' not in data:
    data['agents'] = {}
if '$agent' not in data['agents']:
    data['agents']['$agent'] = {'enabled': True, 'skills': []}
skills = data['agents']['$agent'].get('skills', [])
if '$skill' not in skills:
    skills.append('$skill')
data['agents']['$agent']['skills'] = skills
print(json.dumps(data, indent=2, ensure_ascii=False))
" > "$CONFIG_FILE" 2>/dev/null
}

# 从配置中移除技能
remove_from_config() {
    local agent="$1"
    local skill="$2"
    local config
    config=$(load_config)

    echo "$config" | python3 -c "
import sys, json
data = json.load(sys.stdin)
skills = data.get('agents', {}).get('$agent', {}).get('skills', [])
if '$skill' in skills:
    skills.remove('$skill')
    data['agents']['$agent']['skills'] = skills
print(json.dumps(data, indent=2, ensure_ascii=False))
" > "$CONFIG_FILE" 2>/dev/null
}

# ============================================================================
# 交互式菜单
# ============================================================================

# 显示技能选择菜单
# 返回：用户选择的技能列表（换行分隔）
show_skill_menu() {
    local agent="$1"
    local skills
    skills=($(scan_skills))

    if [ ${#skills[@]} -eq 0 ]; then
        echo -e "${RED}未找到可用技能${NC}" >&2
        return 1
    fi

    # 获取已安装的技能
    local installed
    installed=($(get_installed_skills "$agent"))

    # 选择状态数组
    local selected=()
    for skill in "${skills[@]}"; do
        local is_sel=0
        for inst in "${installed[@]}"; do
            [ "$skill" = "$inst" ] && is_sel=1 && break
        done
        selected+=($is_sel)
    done

    while true; do
        # 清屏并显示菜单
        clear
        echo -e "${CYAN}=== Skill Installer v2.0 ===${NC}"
        echo ""
        echo -e "智能体: ${GREEN}${agent}${NC}"
        echo ""
        echo -e "${YELLOW}可用技能:${NC}"

        for i in "${!skills[@]}"; do
            local skill="${skills[$i]}"
            local mark=" "
            [ "${selected[$i]}" -eq 1 ] && mark="x"

            # 解析元数据
            parse_skill_meta "$SKILLS_DIR/$skill" > /dev/null 2>&1

            local version="${META_VERSION:-未知}"
            local desc="${META_DESCRIPTION:-}"

            # 检查缺失的环境变量
            local env_hint=""
            local missing
            missing=($(get_missing_env_vars "$SKILLS_DIR/$skill"))
            if [ ${#missing[@]} -gt 0 ]; then
                env_hint=" ${YELLOW}(需要: ${missing[*]})${NC}"
            fi

            printf "  [%s] %2d. %-25s %-10s %s%s\n" "$mark" $((i+1)) "$skill" "v$version" "$desc" "$env_hint"
        done

        echo ""
        echo -e "${CYAN}切换: 1-${#skills[@]}  |  [a] 全选  [n] 取消全选  [q] 确认${NC}"
        echo -n -e "${GREEN}> ${NC}"

        read -n1 key
        echo ""

        case "$key" in
            q|Q|"$'\n"|"")
                break
                ;;
            a|A)
                for i in "${!selected[@]}"; do
                    selected[$i]=1
                done
                ;;
            n|N)
                for i in "${!selected[@]}"; do
                    selected[$i]=0
                done
                ;;
            [0-9])
                local idx=$((key - 1))
                if [ $idx -ge 0 ] && [ $idx -lt ${#skills[@]} ]; then
                    if [ "${selected[$idx]}" -eq 1 ]; then
                        selected[$idx]=0
                    else
                        selected[$idx]=1
                    fi
                fi
                ;;
        esac
    done

    # 输出选中的技能
    for i in "${!skills[@]}"; do
        if [ "${selected[$i]}" -eq 1 ]; then
            echo "${skills[$i]}"
        fi
    done
}

# 确认对话框
confirm() {
    local prompt="$1"
    local default="${2:-y}"

    if [ "$default" = "y" ]; then
        echo -n -e "${prompt} [Y/n]: "
    else
        echo -n -e "${prompt} [y/N]: "
    fi

    read -n1 answer
    echo ""

    case "$answer" in
        y|Y|"")
            [ "$default" = "y" ] && return 0 || return 1
            ;;
        n|N)
            [ "$default" = "y" ] && return 1 || return 0
            ;;
        *)
            [ "$default" = "y" ] && return 0 || return 1
            ;;
    esac
}

# ============================================================================
# 回滚机制
# ============================================================================

# 添加回滚操作
push_rollback() {
    ROLLBACK_STACK+=("$1")
}

# 执行回滚
execute_rollback() {
    if [ ${#ROLLBACK_STACK[@]} -eq 0 ]; then
        return
    fi

    echo -e "${YELLOW}正在回滚...${NC}"
    for (( i=${#ROLLBACK_STACK[@]}-1; i>=0; i-- )); do
        eval "${ROLLBACK_STACK[$i]}" 2>/dev/null
    done
    ROLLBACK_STACK=()
    echo -e "${YELLOW}回滚完成${NC}"
}

# 清空回滚栈
clear_rollback() {
    ROLLBACK_STACK=()
}

# ============================================================================
# 日志记录
# ============================================================================

# 记录安装操作
log_operation() {
    local action="$1"
    local src="$2"
    local dst="$3"
    local success="$4"

    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    echo "{\"timestamp\":\"$timestamp\",\"action\":\"$action\",\"src\":\"$src\",\"dst\":\"$dst\",\"success\":$success}" >> "$INSTALL_LOG"
}

# ============================================================================
# 工具函数
# ============================================================================

# 打印成功信息
print_success() {
    echo -e "${GREEN}  ✓ $1${NC}"
}

# 打印警告信息
print_warning() {
    echo -e "${YELLOW}  ⚠ $1${NC}"
}

# 打印错误信息
print_error() {
    echo -e "${RED}  ✗ $1${NC}"
}

# 打印信息
print_info() {
    echo -e "${BLUE}  ℹ $1${NC}"
}
