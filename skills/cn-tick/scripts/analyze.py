#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
A股实时行情与分时量能分析工具 v2.0

增强功能：
- 同时段量能对比（增量/缩量判断）
- 交易金额维度分析
- 承接力判断（量价配合）
- 换手率计算（需配合 cn-financial 获取流通股数据）

数据源：新浪财经（统一接口）
支持：沪市(sh)、深市(sz) 股票

Usage:
    uv run analyze.py 600789              # 单只股票
    uv run analyze.py 600789 002446       # 多只股票
    uv run analyze.py 600789 --minute     # 分时量能分析
    uv run analyze.py 600789 --json       # JSON输出
    uv run analyze.py 600789 --float-shares 1252270215  # 指定流通股数计算换手率
"""

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from typing import Optional

_STOCK_CODE_RE = re.compile(r'^\d{6}$')
_MAX_RESPONSE_BYTES = 2 * 1024 * 1024  # 2 MB


def get_sina_symbol(code: str) -> str:
    """根据股票代码生成新浪格式代码"""
    code = code.strip().upper().replace("SH", "").replace("SZ", "").replace(".", "")

    # 严格验证：必须为6位纯数字
    if not _STOCK_CODE_RE.match(code):
        raise ValueError(f"无效的股票代码: {code!r}，应为6位数字")

    # 沪市: 6开头
    if code.startswith("6"):
        return "sh" + code
    # 深市: 0/3开头
    elif code.startswith(("0", "3")):
        return "sz" + code
    # 北交所: 8/4开头
    elif code.startswith(("8", "4")):
        return "bj" + code
    else:
        return "sh" + code


def fetch_realtime_sina(symbols: list[str]) -> dict[str, dict]:
    """从新浪获取实时行情（支持批量）

    新浪接口返回格式:
    var hq_str_sh600789="名称,今开,昨收,现价,最高,最低,买一,卖一,成交量(股),成交额(元),...";

    字段说明:
    0: 名称
    1: 今开
    2: 昨收
    3: 现价
    4: 最高
    5: 最低
    6: 买一价
    7: 卖一价
    8: 成交量(股)
    9: 成交额(元)
    """
    result = {}

    try:
        codes_str = urllib.parse.quote(",".join(symbols), safe=",")
        url = f"https://hq.sinajs.cn/list={codes_str}"

        req = urllib.request.Request(url, headers={
            "Referer": "https://finance.sina.com.cn",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        })
        resp = urllib.request.urlopen(req, timeout=10)
        text = resp.read(_MAX_RESPONSE_BYTES).decode("gbk")

        # 解析每行
        for line in text.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            # var hq_str_sh600789="数据";
            match = re.match(r'var hq_str_(\w+)="([^"]*)"', line)
            if not match:
                continue

            symbol = match.group(1)
            data_str = match.group(2)

            if not data_str:
                continue

            fields = data_str.split(",")
            if len(fields) < 32:
                continue

            name = fields[0]
            open_price = float(fields[1]) if fields[1] else None
            pre_close = float(fields[2]) if fields[2] else None
            price = float(fields[3]) if fields[3] else None
            high = float(fields[4]) if fields[4] else None
            low = float(fields[5]) if fields[5] else None
            volume = int(float(fields[8])) if fields[8] else 0  # 股
            amount = float(fields[9]) if fields[9] else 0  # 元

            if not price or price <= 0:
                continue

            # 计算涨跌
            change_amt = price - pre_close if pre_close else 0
            change_pct = (change_amt / pre_close * 100) if pre_close and pre_close > 0 else 0

            # 换手率需要总股本，这里先留空
            result[symbol] = {
                "code": symbol[2:],  # 去掉sh/sz前缀
                "name": name,
                "price": price,
                "open": open_price,
                "pre_close": pre_close,
                "high": high,
                "low": low,
                "volume": volume // 100,  # 转换为手
                "amount": amount,
                "change_amt": round(change_amt, 2),
                "change_pct": round(change_pct, 2),
                "turnover": None,  # 新浪实时接口不提供换手率
            }

    except Exception as e:
        print(f"新浪实时接口错误: {e}", file=sys.stderr)

    return result


def fetch_minute_data_sina(symbol: str, count: int = 500) -> list[dict]:
    """从新浪获取分时K线数据（默认500条覆盖2-3个交易日）

    接口: CN_MarketDataService.getKLineData
    返回JSON数组，每条记录包含:
    - day: 时间 (2026-01-27 09:31:00)
    - open/high/low/close: OHLC价格
    - volume: 成交量(股)
    - amount: 成交额(元)
    """
    encoded_symbol = urllib.parse.quote(symbol, safe="")
    url = f"https://quotes.sina.cn/cn/api/jsonp_v2.php/var%20_{encoded_symbol}=/CN_MarketDataService.getKLineData?symbol={encoded_symbol}&scale=1&ma=no&datalen={count}"

    try:
        req = urllib.request.Request(url, headers={
            "Referer": "https://finance.sina.com.cn",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
        resp = urllib.request.urlopen(req, timeout=10)
        text = resp.read(_MAX_RESPONSE_BYTES).decode("utf-8")

        # 解析JSONP: var _xxx=([...])  使用非贪婪匹配避免 ReDoS
        match = re.search(r"\(\[(.+?)\]\)", text, re.DOTALL)
        if not match:
            return []

        data = json.loads("[" + match.group(1) + "]")
        result = []
        for item in data:
            result.append({
                "time": item["day"],
                "open": float(item["open"]),
                "high": float(item["high"]),
                "low": float(item["low"]),
                "close": float(item["close"]),
                "volume": int(item["volume"]),  # 股
                "amount": float(item["amount"]),  # 元
            })
        return result

    except Exception as e:
        print(f"新浪分时接口错误: {e}", file=sys.stderr)

    return []


def split_by_day(minute_data: list[dict]) -> dict[str, list[dict]]:
    """按交易日分割分时数据"""
    days = {}
    for item in minute_data:
        date_str = item["time"][:10]  # "2026-05-15"
        if date_str not in days:
            days[date_str] = []
        days[date_str].append(item)
    return days


def calc_period_stats(data: list[dict], start: str, end: str) -> dict:
    """计算指定时段的量能统计"""
    period_data = [
        d for d in data
        if start <= d["time"][-8:-3] < end and d["volume"] > 0
    ]

    volume = sum(d["volume"] for d in period_data)
    amount = sum(d["amount"] for d in period_data)

    return {
        "volume": volume,  # 股
        "volume_lots": volume // 100,  # 手
        "amount": amount,  # 元
        "count": len(period_data),
    }


def compare_same_period(today: dict, prev: dict, period_name: str) -> dict:
    """对比同一时段的量能变化"""
    if prev["volume"] == 0:
        return {
            "period": period_name,
            "today_volume": today["volume_lots"],
            "today_amount": today["amount"],
            "prev_volume": prev["volume_lots"],
            "prev_amount": prev["amount"],
            "volume_ratio": None,
            "amount_ratio": None,
            "trend": "无对比数据",
        }

    vol_ratio = today["volume"] / prev["volume"] if prev["volume"] > 0 else 0
    amt_ratio = today["amount"] / prev["amount"] if prev["amount"] > 0 else 0

    # 判断趋势
    if vol_ratio > 1.3:
        trend = "明显增量"
    elif vol_ratio > 1.1:
        trend = "温和增量"
    elif vol_ratio < 0.7:
        trend = "明显缩量"
    elif vol_ratio < 0.9:
        trend = "温和缩量"
    else:
        trend = "基本持平"

    return {
        "period": period_name,
        "today_volume": today["volume_lots"],
        "today_amount": today["amount"],
        "prev_volume": prev["volume_lots"],
        "prev_amount": prev["amount"],
        "volume_ratio": round(vol_ratio, 2),
        "amount_ratio": round(amt_ratio, 2),
        "trend": trend,
    }


def analyze_support_power(today_data: list[dict], prev_data: list[dict]) -> dict:
    """分析承接力（量价配合判断）

    基于参考资料：
    - 缩量下跌不破支撑 = 洗盘，承接力强
    - 放量下跌破支撑 = 出货，承接力弱
    - 涨放量跌缩量 = 健康上涨
    - 涨缩量跌放量 = 主力出货
    """
    if not today_data or not prev_data:
        return {"signal": "数据不足，无法判断"}

    # 计算今日价格变动
    today_start = today_data[0]["close"]
    today_end = today_data[-1]["close"]
    today_price_change = (today_end - today_start) / today_start * 100

    # 计算今日总量能
    today_total_vol = sum(d["volume"] for d in today_data if d["volume"] > 0)

    # 计算前一日同时段（截至当前时间）的量能
    today_time = today_data[-1]["time"][-8:-3]  # 当前时间 HH:MM
    prev同期 = [
        d for d in prev_data
        if d["time"][-8:-3] <= today_time and d["volume"] > 0
    ]
    prev_total_vol = sum(d["volume"] for d in prev同期) if prev同期 else 0

    # 计算量比
    vol_ratio = today_total_vol / prev_total_vol if prev_total_vol > 0 else 0

    # 承接力判断
    signal = ""
    power = ""

    if today_price_change < 0:  # 价格下跌
        if vol_ratio < 0.8:
            signal = "缩量回调"
            power = "承接力强（主力护盘，散户惜售）"
        elif vol_ratio > 1.2:
            signal = "放量下跌"
            power = "承接力弱（主力出货，恐慌抛售）"
        else:
            signal = "平量回调"
            power = "承接力一般"
    elif today_price_change > 0:  # 价格上涨
        if vol_ratio > 1.2:
            signal = "放量上涨"
            power = "量价配合好（主力积极做多）"
        elif vol_ratio < 0.8:
            signal = "缩量上涨"
            power = "量价背离（主力控盘或散户推动）"
        else:
            signal = "平量上涨"
            power = "量价正常"
    else:
        signal = "横盘整理"
        power = "多空平衡"

    return {
        "price_change_pct": round(today_price_change, 2),
        "volume_ratio": round(vol_ratio, 2),
        "signal": signal,
        "power": power,
    }


def calc_turnover_rate(volume_lots: int, float_shares: int) -> float:
    """计算换手率"""
    if float_shares <= 0:
        return 0
    volume_shares = volume_lots * 100  # 手 -> 股
    return round(volume_shares / float_shares * 100, 2)


def get_turnover_rating(turnover: float) -> str:
    """换手率评级"""
    if turnover < 1:
        return "极度低迷"
    elif turnover < 3:
        return "低迷"
    elif turnover < 7:
        return "正常"
    elif turnover < 10:
        return "活跃"
    elif turnover < 15:
        return "高度活跃"
    else:
        return "异常放量（筹码剧烈交换）"


def analyze_minute_volume(minute_data: list[dict], float_shares: int = 0) -> dict:
    """分析分时量能（增强版）"""
    if not minute_data:
        return {"error": "无分时数据"}

    # 按天分割数据
    days = split_by_day(minute_data)
    sorted_dates = sorted(days.keys())

    if len(sorted_dates) < 1:
        return {"error": "无有效交易日数据"}

    # 获取今日数据
    today_date = sorted_dates[-1]
    today_data = days[today_date]

    # 获取前一日数据（如果有）
    prev_date = sorted_dates[-2] if len(sorted_dates) >= 2 else None
    prev_data = days.get(prev_date, []) if prev_date else []

    # 过滤今日交易时段数据
    trading_data = [
        d for d in today_data
        if d["volume"] > 0 and "09:25" <= d["time"][-8:-3] <= "15:00"
    ]

    if not trading_data:
        return {"error": "无有效交易数据"}

    # 统计各时段成交量和金额
    total_vol = sum(d["volume"] for d in trading_data)
    total_amt = sum(d["amount"] for d in trading_data)

    def period_stats(start: str, end: str) -> dict:
        return calc_period_stats(trading_data, start, end)

    open_30 = period_stats("09:30", "10:00")
    mid_am = period_stats("10:00", "11:30")
    mid_pm = period_stats("13:00", "14:30")
    close_30 = period_stats("14:30", "15:01")

    # 前一日同时段统计
    prev_comparison = {}
    if prev_data:
        prev_trading = [
            d for d in prev_data
            if d["volume"] > 0 and "09:25" <= d["time"][-8:-3] <= "15:00"
        ]
        prev_open_30 = calc_period_stats(prev_trading, "09:30", "10:00")
        prev_mid_am = calc_period_stats(prev_trading, "10:00", "11:30")
        prev_mid_pm = calc_period_stats(prev_trading, "13:00", "14:30")
        prev_close_30 = calc_period_stats(prev_trading, "14:30", "15:01")

        prev_comparison = {
            "open_30min": compare_same_period(open_30, prev_open_30, "早盘30分"),
            "mid_am": compare_same_period(mid_am, prev_mid_am, "上午中段"),
            "mid_pm": compare_same_period(mid_pm, prev_mid_pm, "下午中段"),
            "close_30min": compare_same_period(close_30, prev_close_30, "尾盘30分"),
            "prev_date": prev_date,
        }

    # 放量时段 TOP 10
    sorted_by_vol = sorted(trading_data, key=lambda x: x["volume"], reverse=True)[:10]
    top_volumes = [
        {
            "time": d["time"][-8:],
            "price": d["close"],
            "volume": d["volume"] // 100,  # 转换为手
            "amount": d["amount"],
        }
        for d in sorted_by_vol
    ]

    # 主力动向判断
    signals = []
    if total_vol > 0:
        if close_30["volume"] / total_vol > 0.25:
            signals.append("尾盘大幅放量，可能有主力抢筹或出货")
        elif close_30["volume"] / total_vol > 0.15:
            signals.append("尾盘有一定放量")
        if open_30["volume"] / total_vol > 0.30:
            signals.append("早盘主力抢筹明显")
        if open_30["volume"] / total_vol > 0.40:
            signals.append("早盘放量异常，主力强势介入")

    # 检测涨停/跌停
    last_price = trading_data[-1]["close"] if trading_data else 0
    highest_vol_price = sorted_by_vol[0]["close"] if sorted_by_vol else 0
    if last_price > 0 and abs(last_price - highest_vol_price) < 0.01:
        signals.append("封板状态，关注封单量")

    # 承接力分析
    support_power = analyze_support_power(trading_data, prev_data)

    # 换手率
    turnover_rate = calc_turnover_rate(total_vol // 100, float_shares) if float_shares > 0 else None
    turnover_rating = get_turnover_rating(turnover_rate) if turnover_rate else None

    return {
        "today_date": today_date,
        "total_volume": total_vol // 100,  # 手
        "total_amount": total_amt,
        "distribution": {
            "open_30min": {
                "volume": open_30["volume_lots"],
                "amount": open_30["amount"],
                "percent": round(open_30["volume"] / total_vol * 100, 1) if total_vol else 0,
            },
            "mid_am": {
                "volume": mid_am["volume_lots"],
                "amount": mid_am["amount"],
                "percent": round(mid_am["volume"] / total_vol * 100, 1) if total_vol else 0,
            },
            "mid_pm": {
                "volume": mid_pm["volume_lots"],
                "amount": mid_pm["amount"],
                "percent": round(mid_pm["volume"] / total_vol * 100, 1) if total_vol else 0,
            },
            "close_30min": {
                "volume": close_30["volume_lots"],
                "amount": close_30["amount"],
                "percent": round(close_30["volume"] / total_vol * 100, 1) if total_vol else 0,
            },
        },
        "prev_comparison": prev_comparison,
        "top_volumes": top_volumes,
        "signals": signals,
        "support_power": support_power,
        "turnover_rate": turnover_rate,
        "turnover_rating": turnover_rating,
    }


def format_realtime(data: dict) -> str:
    """格式化实时行情输出"""
    change_symbol = "+" if data["change_pct"] >= 0 else ""
    turnover_str = f"换手: {data['turnover']:.2f}%" if data.get("turnover") else ""

    lines = [
        f"{'='*60}",
        f"股票: {data['name']} ({data['code']})",
        f"{'='*60}",
        f"",
        f"【实时行情】",
        f"  现价: {data['price']:.2f}  涨跌: {change_symbol}{data['change_pct']:.2f}%",
        f"  今开: {data['open']:.2f}  最高: {data['high']:.2f}  最低: {data['low']:.2f}",
        f"  昨收: {data['pre_close']:.2f}  {turnover_str}",
        f"  成交量: {data['volume']/10000:.1f}万手  成交额: {data['amount']/100000000:.2f}亿",
    ]
    return "\n".join(lines)


def format_minute_analysis(analysis: dict, name: str = "") -> str:
    """格式化分时分析输出（增强版）"""
    if "error" in analysis:
        return f"分时分析错误: {analysis['error']}"

    lines = [
        f"",
        f"{'='*60}",
        f"【分时量能分析】{name} ({analysis.get('today_date', '')})",
        f"{'='*60}",
        f"",
        f"  全天成交: {analysis['total_volume']}手 ({analysis['total_amount']/10000:.1f}万元)",
    ]

    # 换手率
    if analysis.get("turnover_rate") is not None:
        lines.append(f"  换手率: {analysis['turnover_rate']:.2f}% ({analysis['turnover_rating']})")

    lines.append(f"")
    lines.append(f"  【成交分布】")
    lines.append(f"    时段              量(手)      金额(万)    占比")
    lines.append(f"    ─────────────────────────────────────────────")

    for period_key, period_name in [
        ("open_30min", "早盘30分(9:30-10:00)"),
        ("mid_am", "上午中段(10:00-11:30)"),
        ("mid_pm", "下午中段(13:00-14:30)"),
        ("close_30min", "尾盘30分(14:30-15:00)"),
    ]:
        d = analysis["distribution"][period_key]
        lines.append(f"    {period_name:<18} {d['volume']:>8}    {d['amount']/10000:>8.1f}    {d['percent']}%")

    # 同时段对比
    if analysis.get("prev_comparison"):
        pc = analysis["prev_comparison"]
        lines.append(f"")
        lines.append(f"  【同时段对比】vs {pc.get('prev_date', '前一日')}")
        lines.append(f"    时段          今日量    前日量   量比   今日额(万) 前日额(万) 额比   趋势")
        lines.append(f"    ─────────────────────────────────────────────────────────────────────────────")

        for period_key, period_name in [
            ("open_30min", "早盘30分"),
            ("mid_am", "上午中段"),
            ("mid_pm", "下午中段"),
            ("close_30min", "尾盘30分"),
        ]:
            if period_key in pc:
                c = pc[period_key]
                vol_ratio_str = f"{c['volume_ratio']:.2f}" if c['volume_ratio'] else "N/A"
                amt_ratio_str = f"{c['amount_ratio']:.2f}" if c.get('amount_ratio') else "N/A"
                today_amt = c['today_amount'] / 10000
                prev_amt = c['prev_amount'] / 10000
                lines.append(f"    {period_name:<12} {c['today_volume']:>8}  {c['prev_volume']:>8}  {vol_ratio_str:>5}  {today_amt:>10.1f}  {prev_amt:>10.1f}  {amt_ratio_str:>5}  {c['trend']}")

    # 承接力分析
    if analysis.get("support_power"):
        sp = analysis["support_power"]
        lines.append(f"")
        lines.append(f"  【承接力判断】")
        lines.append(f"    价格变动: {sp['price_change_pct']:+.2f}%  |  量比: {sp['volume_ratio']:.2f}")
        lines.append(f"    信号: {sp['signal']}  →  {sp['power']}")

    # 早盘量能预期判断（基于参考资料）
    if analysis.get("prev_comparison"):
        pc = analysis["prev_comparison"]
        if "open_30min" in pc:
            open_info = pc["open_30min"]
            lines.append(f"")
            lines.append(f"  【早盘量能预期】")
            # 计算早盘30分占全天的比例（基于前一日）
            if open_info["volume_ratio"]:
                ratio = open_info["volume_ratio"]
                if ratio > 1.5:
                    signal = "放量加速  →  主力强势介入，积极做多"
                    icon = "🟢"
                elif ratio > 1.2:
                    signal = "温和放量  →  资金正常流入"
                    icon = "🟢"
                elif ratio > 0.8:
                    signal = "量能持平  →  多空平衡"
                    icon = "🟡"
                elif ratio > 0.5:
                    signal = "缩量明显  →  主力观望或控盘"
                    icon = "🟠"
                else:
                    signal = "极度缩量  →  资金离场或高度控盘"
                    icon = "🔴"
                lines.append(f"    {icon} 早盘额比: {open_info['amount_ratio']:.2f}  |  {signal}")

    # 放量时段 TOP 10
    lines.append(f"")
    lines.append(f"  【放量时段 TOP 10】")
    for item in analysis["top_volumes"]:
        lines.append(f"    {item['time']} 价格:{item['price']:.2f} 成交:{item['volume']}手 金额:{item['amount']/10000:.1f}万")

    # 主力动向判断
    if analysis["signals"]:
        lines.append(f"")
        lines.append(f"  【主力动向判断】")
        for signal in analysis["signals"]:
            lines.append(f"    🔥 {signal}")

    # 综合交易信号
    lines.append(f"")
    lines.append(f"  {'='*50}")
    lines.append(f"  【综合信号】")

    # 收集所有信号
    all_signals = []
    if analysis.get("support_power"):
        sp = analysis["support_power"]
        if "缩量回调" in sp["signal"]:
            all_signals.append(("🟢", "承接力强", "缩量回调不破支撑，主力护盘"))
        elif "放量下跌" in sp["signal"]:
            all_signals.append(("🔴", "承接力弱", "放量下跌，警惕出货"))
        elif "放量上涨" in sp["signal"]:
            all_signals.append(("🟢", "量价配合", "放量上涨，主力做多"))
        elif "缩量上涨" in sp["signal"]:
            all_signals.append(("🟡", "量价背离", "缩量上涨，关注后续量能"))

    if analysis.get("prev_comparison") and "open_30min" in analysis["prev_comparison"]:
        open_ratio = analysis["prev_comparison"]["open_30min"].get("amount_ratio", 1)
        if open_ratio > 1.3:
            all_signals.append(("🟢", "早盘放量", "资金加速流入"))
        elif open_ratio < 0.7:
            all_signals.append(("🟠", "早盘缩量", "资金观望"))

    for signal in analysis.get("signals", []):
        if "抢筹" in signal:
            all_signals.append(("🟢", "主力抢筹", signal))
        elif "出货" in signal:
            all_signals.append(("🔴", "主力出货", signal))

    if all_signals:
        for icon, title, desc in all_signals:
            lines.append(f"    {icon} {title}: {desc}")
    else:
        lines.append(f"    🟡 暂无明显信号，建议观望")

    lines.append(f"  {'='*50}")

    return "\n".join(lines)


def analyze_stock(code: str, with_minute: bool = False, realtime_cache: dict = None, float_shares: int = 0) -> dict:
    """分析单只股票"""
    sina_symbol = get_sina_symbol(code)

    # 获取实时行情（支持缓存以批量获取）
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

    # 分时分析
    if with_minute:
        minute_data = fetch_minute_data_sina(sina_symbol)
        minute_analysis = analyze_minute_volume(minute_data, float_shares)
        result["minute_analysis"] = minute_analysis

    return result


def main():
    parser = argparse.ArgumentParser(description="A股实时行情与分时量能分析 v2.0")
    parser.add_argument("codes", nargs="+", help="股票代码，如 600789 002446")
    parser.add_argument("--minute", "-m", action="store_true", help="包含分时量能分析")
    parser.add_argument("--json", "-j", action="store_true", help="JSON格式输出")
    parser.add_argument("--float-shares", "-f", type=int, default=0, help="流通股数（用于计算换手率，可从 cn-financial 获取）")

    args = parser.parse_args()

    # 批量获取实时行情
    sina_symbols = [get_sina_symbol(code) for code in args.codes]
    realtime_cache = fetch_realtime_sina(sina_symbols)

    results = []
    for code in args.codes:
        result = analyze_stock(code, with_minute=args.minute, realtime_cache=realtime_cache, float_shares=args.float_shares)
        results.append(result)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for result in results:
            if "error" in result:
                print(f"错误: {result['error']}")
                continue

            print(format_realtime(result["realtime"]))

            if args.minute and "minute_analysis" in result:
                print(format_minute_analysis(result["minute_analysis"], result["name"]))

            print()


if __name__ == "__main__":
    main()
