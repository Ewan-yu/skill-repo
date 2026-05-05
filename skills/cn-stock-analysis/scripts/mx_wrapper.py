#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
妙想Skills包装脚本 - 完全解决编码问题
直接读取生成的JSON文件，返回结构化数据
"""

import sys
import json
import os
import re
from pathlib import Path
import subprocess

# 添加 mx-data 和 mx-search 路径
mx_data_path = Path(r"C:\Users\kense\.claude\skills\mx-data")
mx_search_path = Path(r"C:\Users\kense\.claude\skills\mx-search")

def run_mx_data(query: str) -> dict:
    """执行 mx-data 查询并返回结果"""
    # 执行查询
    result = subprocess.run(
        [sys.executable, str(mx_data_path / "mx_data.py"), query],
        cwd=str(mx_data_path),
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='ignore',
        env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    )
    
    # 查找最新生成的 JSON 文件
    output_dir = mx_data_path / "mx"
    json_files = list(output_dir.glob("*_raw.json"))
    if json_files:
        latest_json = max(json_files, key=lambda p: p.stat().st_mtime)
        try:
            with open(latest_json, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    
    # 如果找不到JSON，解析stdout
    if result.stdout:
        # 提取表格数据
        return {
            "success": True,
            "query": query,
            "output": result.stdout,
            "files_extracted": extract_file_info(result.stdout)
        }
    
    return {"success": False, "error": "查询失败"}

def run_mx_search(query: str) -> dict:
    """执行 mx-search 查询并返回结果"""
    # 执行查询
    result = subprocess.run(
        [sys.executable, str(mx_search_path / "mx_search.py"), query],
        cwd=str(mx_search_path),
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='ignore',
        env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    )
    
    # 查找最新生成的 JSON 文件
    output_dir = mx_search_path / "mx"
    json_files = list(output_dir.glob("*_raw.json"))
    if json_files:
        latest_json = max(json_files, key=lambda p: p.stat().st_mtime)
        try:
            with open(latest_json, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    
    # 如果找不到JSON，返回stdout
    if result.stdout:
        return {
            "success": True,
            "query": query,
            "output": result.stdout,
            "files_extracted": extract_file_info(result.stdout)
        }
    
    return {"success": False, "error": "查询失败"}

def extract_file_info(text: str) -> dict:
    """从输出中提取文件路径信息"""
    files = {}
    
    # 提取Excel文件路径
    excel_match = re.search(r'Excel 文件: ([^\n]+)', text)
    if excel_match:
        files['excel'] = excel_match.group(1).strip()
    
    # 提取描述文件路径
    desc_match = re.search(r'描述文件: ([^\n]+)', text)
    if desc_match:
        files['description'] = desc_match.group(1).strip()
    
    # 提取JSON文件路径
    json_match = re.search(r'原始JSON: ([^\n]+)', text)
    if json_match:
        files['json'] = json_match.group(1).strip()
    
    return files

def main():
    """命令行入口"""
    if len(sys.argv) < 3:
        result = {"success": False, "error": "用法: python mx_wrapper.py [data|search] \"查询内容\""}
    else:
        command = sys.argv[1].lower()
        query = ' '.join(sys.argv[2:])
        
        if command == "data":
            result = run_mx_data(query)
        elif command == "search":
            result = run_mx_search(query)
        else:
            result = {"success": False, "error": f"未知命令: {command}"}
    
    # 保存结果到文件
    output_file = Path(r"C:\Users\kense\.claude\skills\cn-stock-analysis\scripts\mx_result.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    # 简单输出
    print(f"OK")

if __name__ == "__main__":
    main()
