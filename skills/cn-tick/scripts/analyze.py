#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""A股实时行情与分时量能分析工具 v5.0"""

import argparse
import json
import os
import re
import sys

# 修复 Windows 终端中文乱码
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 确保同目录模块可导入
sys.path.insert(0, os.path.dirname(__file__))

from fetcher import get_sina_symbol, fetch_realtime_sina, fetch_minute_data_sina
from analysis import analyze_minute_volume
from report import (
    build_realtime_report, build_minute_report,
    render_report_text, render_report_md,
)

_STOCK_CODE_RE = re.compile(r'^\d{6}$')

from datetime import datetime


def analyze_stock(code: str, with_minute: bool = False,
                  realtime_cache: dict = None, float_shares: int = 0,
                  auction_today_shares: int = 0, auction_prev_shares: int = 0) -> dict:
    """分析单只股票"""
    sina_symbol = get_sina_symbol(code)

    if realtime_cache and sina_symbol in realtime_cache:
        realtime = realtime_cache[sina_symbol]
    else:
        realtime_data = fetch_realtime_sina([sina_symbol])
        realtime = realtime_data.get(sina_symbol)

    if not realtime:
        return {"error": f"无法获取 {code} 的行情数据"}

    result = {
        "code": code,
        "name": realtime["name"],
        "realtime": realtime,
        "updated_at": datetime.now().isoformat(),
    }

    if with_minute:
        minute_data = fetch_minute_data_sina(sina_symbol)
        pre_close = realtime.get("pre_close")
        minute_analysis = analyze_minute_volume(
            minute_data,
            float_shares=float_shares,
            pre_close=pre_close,
            code=code,
            auction_today_shares=auction_today_shares,
            auction_prev_shares=auction_prev_shares,
        )
        if realtime.get("volume_ratio") is not None:
            minute_analysis["absolute_volume_ratio"] = realtime["volume_ratio"]
        result["minute_analysis"] = minute_analysis

    return result


# ---- 向后兼容接口（portfolio.py 依赖）----

def format_realtime(data: dict) -> str:
    return render_report_text(build_realtime_report(data))


def format_minute_analysis(analysis: dict, name: str = "") -> str:
    return "\n" + render_report_text(build_minute_report(analysis, name))


def format_realtime_md(data: dict) -> str:
    return render_report_md(build_realtime_report(data))


def format_minute_analysis_md(analysis: dict, name: str = "") -> str:
    return render_report_md(build_minute_report(analysis, name))


def main():
    parser = argparse.ArgumentParser(description="A股实时行情与分时量能分析 v5.0")
    parser.add_argument("codes", nargs="+", help="股票代码，如 600789 002446")
    parser.add_argument("--minute", "-m", action="store_true", help="包含分时量能分析")
    parser.add_argument("--review", "-r", action="store_true", help="盘后复盘模式")
    parser.add_argument("--json", "-j", action="store_true", help="JSON格式输出")
    parser.add_argument("--format", "-fmt", choices=["text", "md"], default="text",
                        help="输出格式: text / md")
    parser.add_argument("--float-shares", "-f", type=int, default=0,
                        help="流通股数(用于计算换手率)")
    parser.add_argument("--auction-today-shares", type=int, default=0,
                        help="今日集合竞价成交量(股)，来自 mx-data，如 719500")
    parser.add_argument("--auction-prev-shares", type=int, default=0,
                        help="前日集合竞价成交量(股)，来自 mx-data，如 564200")

    args = parser.parse_args()

    if args.review:
        args.minute = True

    sina_symbols = [get_sina_symbol(code) for code in args.codes]
    realtime_cache = fetch_realtime_sina(sina_symbols)

    results = []
    for code in args.codes:
        result = analyze_stock(
            code, with_minute=args.minute,
            realtime_cache=realtime_cache,
            float_shares=args.float_shares,
            auction_today_shares=args.auction_today_shares,
            auction_prev_shares=args.auction_prev_shares,
        )
        results.append(result)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    use_md = args.format == "md"
    fmt_realtime = format_realtime_md if use_md else format_realtime

    for i, result in enumerate(results):
        if "error" in result:
            print(f"错误: {result['error']}")
            continue

        print(fmt_realtime(result["realtime"]))

        if args.minute and "minute_analysis" in result:
            report = build_minute_report(
                result["minute_analysis"],
                result["name"],
                review_mode=args.review,
            )
            rendered = render_report_md(report) if use_md else render_report_text(report)
            print("\n" + rendered)

        if not use_md and i < len(results) - 1:
            print()


if __name__ == "__main__":
    main()
