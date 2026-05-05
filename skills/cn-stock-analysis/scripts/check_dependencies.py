#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股分析技能依赖检查脚本

自动检测并引导安装所需的依赖工具：
- cn-financial MCP (必需)
- 妙想 Skills (可选但推荐)
"""

import sys
import subprocess
import json
from pathlib import Path

def print_header(text):
    """打印标题"""
    print(f"\n{'='*60}")
    print(f"{text}")
    print(f"{'='*60}\n")

def print_success(text):
    """打印成功信息"""
    print(f"  [OK] {text}")

def print_error(text):
    """打印错误信息"""
    print(f"  [ERROR] {text}")

def print_warning(text):
    """打印警告信息"""
    print(f"  [WARNING] {text}")

def print_info(text):
    """打印信息"""
    print(f"  [INFO] {text}")

def check_npm_available():
    """检查 npm 是否可用"""
    try:
        # Windows 下使用 shell=True 来确保 npm 命令能被找到
        if sys.platform == 'win32':
            result = subprocess.run(
                'npm --version',
                capture_output=True,
                text=True,
                timeout=5,
                shell=True,
                encoding='utf-8',
                errors='ignore'
            )
        else:
            result = subprocess.run(
                ['npm', '--version'],
                capture_output=True,
                text=True,
                timeout=5,
                encoding='utf-8',
                errors='ignore'
            )
        return result.returncode == 0
    except:
        return False

def check_cn_financial_mcp():
    """检查 cn-financial MCP 是否已配置"""
    print_header("检查 cn-financial MCP 工具")

    # 检查是否在 MCP 服务器列表中
    settings_paths = [
        Path.home() / '.claude' / 'settings.json',
        Path.home() / '.claude' / 'settings.local.json',
    ]

    found_in_settings = False
    config_type = None

    for settings_path in settings_paths:
        if settings_path.exists():
            try:
                with open(settings_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)

                # 方法1：检查 mcpServers 配置
                mcp_servers = settings.get('mcpServers', {})
                if 'cn-financial' in mcp_servers:
                    print_success("cn-financial MCP 已在配置文件中找到")
                    print_info(f"配置位置: {settings_path}")
                    print_info(f"配置方式: mcpServers")
                    found_in_settings = True
                    config_type = "mcpServers"
                    break

                # 方法2：检查 extraKnownMarketplaces（插件市场）配置
                marketplaces = settings.get('extraKnownMarketplaces', {})
                for marketplace_name, marketplace_config in marketplaces.items():
                    source_config = marketplace_config.get('source', {})
                    source_type = source_config.get('source', '')
                    # 检查是否是指向 cn-financial 的目录
                    if source_type == 'directory':
                        path = source_config.get('path', '')
                        if 'cn-financial' in path.lower():
                            print_success("cn-financial MCP 已在配置文件中找到")
                            print_info(f"配置位置: {settings_path}")
                            print_info(f"配置方式: extraKnownMarketplaces ({path})")
                            found_in_settings = True
                            config_type = "extraKnownMarketplaces"
                            break

                if found_in_settings:
                    break
            except Exception as e:
                print_warning(f"读取配置文件时出错: {e}")

    if not found_in_settings:
        print_error("cn-financial MCP 未在 Claude Code 配置中找到")
    else:
        print_info(f"cn-financial MCP 配置类型: {config_type}")

    return found_in_settings

def check_mx_skills():
    """检查妙想 Skills 是否可用"""
    print_header("检查妙想 Skills（可选但推荐）")

    # 检查是否有妙想相关的命令
    mx_commands = ['mx-data', 'mx-search', 'mx-zixuan']
    found_any = False

    for cmd in mx_commands:
        try:
            if sys.platform == 'win32':
                result = subprocess.run(
                    ['where', cmd],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    encoding='utf-8',
                    errors='ignore'
                )
            else:
                result = subprocess.run(
                    ['which', cmd],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    encoding='utf-8',
                    errors='ignore'
                )

            if result.returncode == 0:
                print_success(f"找到妙想命令: {cmd}")
                found_any = True
        except:
            pass

    if found_any:
        print_success("妙想 Skills 已安装")
        return True
    else:
        print_warning("妙想 Skills 未找到")
        print_info("妙想 Skills 是可选的，但不影响使用")
        return False

def show_install_guide():
    """显示安装指南"""
    print_header("cn-financial MCP 安装指南")

    # 检查 npm 是否可用
    if not check_npm_available():
        print_error("npm 未安装或不在 PATH 中")
        print_info("请先安装 Node.js 和 npm:")
        print("     访问: https://nodejs.org/")
        print("     下载并安装 LTS 版本")
        print()
        return False

    print_success("npm 已可用")

    print("\n安装步骤:")
    print("  步骤1: 安装 cn-financial MCP")
    print("     运行以下命令（推荐方法）:")
    print("     npx -y @wensor/cn-financial-mcp")
    print()
    print("     或者全局安装:")
    print("     npm install -g @wensor/cn-financial-mcp")
    print()

    print("  步骤2: 配置 MCP 服务器")
    print("     编辑 Claude Code 设置文件:")
    print("     ~/.claude/settings.json")
    print()

    print("     添加以下配置:")
    print("""
{
  "mcpServers": {
    "cn-financial": {
      "command": "npx",
      "args": ["-y", "@wensor/cn-financial-mcp"]
    }
  }
}
    """)

    print("  步骤3: 重启 Claude Code")
    print("     完全退出 Claude Code 并重新启动")
    print()

    print("  步骤4: 验证安装")
    print("     在 Claude Code 中运行:")
    print("     帮我查看一下上证指数今天的行情")
    print()

    return True

def main():
    """主函数"""
    print("""
╔══════════════════════════════════════════════════════════╗
║         A股分析技能 - 依赖检查工具                        ║
╚══════════════════════════════════════════════════════════╝
    """)

    # 检查环境
    print_header("检查运行环境")

    if sys.platform == 'win32':
        print_info(f"操作系统: Windows")
    elif sys.platform == 'darwin':
        print_info(f"操作系统: macOS")
    else:
        print_info(f"操作系统: Linux")

    if not check_npm_available():
        print_error("npm 未安装")
        print_info("cn-financial MCP 需要 Node.js 和 npm")

    # 检查依赖
    cn_financial_ok = check_cn_financial_mcp()
    mx_skills_ok = check_mx_skills()

    # 汇总结果
    print_header("检查结果汇总")

    if cn_financial_ok:
        print_success("cn-financial MCP: 已配置")
    else:
        print_error("cn-financial MCP: 未配置")

    if mx_skills_ok:
        print_success("妙想 Skills: 已安装")
    else:
        print_warning("妙想 Skills: 未安装（可选）")

    # 处理缺失的依赖
    if not cn_financial_ok:
        print()
        print_warning("cn-financial MCP 是必需的依赖")
        print()

        if show_install_guide():
            print_info("请按照上述步骤安装和配置 cn-financial MCP")
            print_info("配置完成后重启 Claude Code 即可使用")
    else:
        print()
        print_success("所有必需依赖已就绪！")
        print_info("你可以开始使用 A股分析技能了")

    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n用户取消操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n发生错误: {e}")
        sys.exit(1)
