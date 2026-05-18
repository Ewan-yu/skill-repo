#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
A股实时行情与分时量能分析工具 v3.1

P0修复:
- 涨停/跌停检测: 基于昨收价正确判断
- 承接力价格基准: 使用昨收价而非当日第一根K线
- 趋势判断: 以额比为主、量比为辅
- 早盘占比<20%: 强烈警示
- 集合竞价过滤: 09:30开始纳入(排除09:25集合竞价)

P1新增:
- VWAP(均价线)计算与价格关系分析
- 卖出三部曲信号(基于资料实战规则)
- 实时量比(从新浪实时数据提取)
- 对比前两天均值(更稳定的缩量判断)
- 换手率阈值校正(对齐实战标准)

P2优化:
- 清理重复代码
- 信号去重
- 数据时效标注
- 额比缺失时不默认填充

数据源: 新浪财经(统一接口)
支持: 沪市(sh)、深市(sz) 股票
"""

import argparse
import json
import locale
import os
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, time

# 修复 Windows 终端中文乱码问题
# 当 stdout 不是 UTF-8 时（如 Windows bash/Cygwin），强制使用 UTF-8
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

_STOCK_CODE_RE = re.compile(r'^\d{6}$')
_MAX_RESPONSE_BYTES = 2 * 1024 * 1024  # 2 MB

# ============================================================
# 市场时间工具
# ============================================================

def get_market_status() -> tuple[str, str]:
    """判断当前市场状态，返回(状态标签, 数据时效说明)"""
    now = datetime.now()
    try:
        current_time = now.time()
        if now.weekday() >= 5:
            return ("休市(周末)", "数据为最近交易日收盘快照，非实时")
        if time(9, 30) <= current_time <= time(11, 30):
            return ("交易中(上午)", "数据为实时行情，延迟约3秒")
        elif time(13, 0) <= current_time <= time(15, 0):
            return ("交易中(下午)", "数据为实时行情，延迟约3秒")
        elif current_time < time(9, 30):
            return ("盘前", "数据为前一交易日收盘快照，非实时")
        elif time(11, 30) < current_time < time(13, 0):
            return ("午间休市", "数据为上午收盘快照，非实时")
        else:
            return ("已收盘", "数据为今日收盘快照")
    except Exception:
        return ("未知", "")

# ============================================================
# 股票代码工具
# ============================================================

def get_sina_symbol(code: str) -> str:
    """根据股票代码生成新浪格式代码"""
    code = code.strip().upper().replace("SH", "").replace("SZ", "").replace(".", "")
    if not _STOCK_CODE_RE.match(code):
        raise ValueError(f"无效的股票代码: {code!r}，应为6位数字")
    if code.startswith("6"):
        return "sh" + code
    elif code.startswith(("0", "3")):
        return "sz" + code
    elif code.startswith(("8", "4")):
        return "bj" + code
    else:
        return "sh" + code


def get_limit_price(pre_close: float, is_st: bool = False, is_kcb_cyb: bool = False) -> tuple[float, float]:
    """计算涨停价和跌停价
    - 普通股: ±10%
    - ST股: ±5%
    - 科创板/创业板: ±20%
    """
    if is_st:
        return (round(pre_close * 1.05, 2), round(pre_close * 0.95, 2))
    elif is_kcb_cyb:
        return (round(pre_close * 1.20, 2), round(pre_close * 0.80, 2))
    else:
        return (round(pre_close * 1.10, 2), round(pre_close * 0.90, 2))

# ============================================================
# 数据获取
# ============================================================

def fetch_realtime_sina(symbols: list[str]) -> dict[str, dict]:
    """从新浪获取实时行情（支持批量）

    字段说明(索引从0开始):
    0: 名称, 1: 今开, 2: 昨收, 3: 现价, 4: 最高, 5: 最低
    6: 买一价, 7: 卖一价, 8: 成交量(股), 9: 成交额(元)
    30: 量比(当日累计成交量/过去5日平均每分钟成交量×累计分钟数)
    """
    result = {}
    market_status, data_note = get_market_status()

    try:
        codes_str = urllib.parse.quote(",".join(symbols), safe=",")
        url = f"https://hq.sinajs.cn/list={codes_str}"
        req = urllib.request.Request(url, headers={
            "Referer": "https://finance.sina.com.cn",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
        resp = urllib.request.urlopen(req, timeout=10)
        text = resp.read(_MAX_RESPONSE_BYTES).decode("gbk", errors="replace")

        for line in text.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
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

            # 提取实时量比(索引30)
            volume_ratio = None
            try:
                if len(fields) > 30 and fields[30]:
                    volume_ratio = float(fields[30])
            except (ValueError, IndexError):
                pass

            if not price or price <= 0:
                continue
            if not pre_close or pre_close <= 0:
                continue

            change_amt = price - pre_close
            change_pct = (change_amt / pre_close) * 100

            result[symbol] = {
                "code": symbol[2:],
                "name": name,
                "price": price,
                "open": open_price,
                "pre_close": pre_close,
                "high": high,
                "low": low,
                "volume": volume // 100,  # 手
                "amount": amount,
                "change_amt": round(change_amt, 2),
                "change_pct": round(change_pct, 2),
                "turnover": None,
                "volume_ratio": volume_ratio,  # 实时量比
                "data_status": market_status,
                "data_note": data_note,
            }

    except Exception as e:
        print(f"新浪实时接口错误: {e}", file=sys.stderr)

    return result


def fetch_minute_data_sina(symbol: str, count: int = 500) -> list[dict]:
    """从新浪获取分时K线数据（默认500条覆盖2-3个交易日）"""
    encoded_symbol = urllib.parse.quote(symbol, safe="")
    url = f"https://quotes.sina.cn/cn/api/jsonp_v2.php/var%20_{encoded_symbol}=/CN_MarketDataService.getKLineData?symbol={encoded_symbol}&scale=1&ma=no&datalen={count}"

    try:
        req = urllib.request.Request(url, headers={
            "Referer": "https://finance.sina.com.cn",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
        resp = urllib.request.urlopen(req, timeout=10)
        text = resp.read(_MAX_RESPONSE_BYTES).decode("utf-8", errors="replace")

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
                "volume": int(item["volume"]),
                "amount": float(item["amount"]),
            })
        return result

    except Exception as e:
        print(f"新浪分时接口错误: {e}", file=sys.stderr)

    return []

# ============================================================
# 数据处理
# ============================================================

def split_by_day(minute_data: list[dict]) -> dict[str, list[dict]]:
    """按交易日分割分时数据"""
    days = {}
    for item in minute_data:
        date_str = item["time"][:10]
        if date_str not in days:
            days[date_str] = []
        days[date_str].append(item)
    return days


def extract_hhmm(time_str: str) -> str:
    """从时间字符串提取HH:MM部分"""
    return time_str[11:16]  # "2026-05-15 09:31:00" -> "09:31"


def calc_period_stats(data: list[dict], start: str, end: str) -> dict:
    """计算指定时段的量能统计"""
    period_data = [
        d for d in data
        if start <= extract_hhmm(d["time"]) < end and d["volume"] > 0
    ]
    volume = sum(d["volume"] for d in period_data)
    amount = sum(d["amount"] for d in period_data)
    return {
        "volume": volume,
        "volume_lots": volume // 100,
        "amount": amount,
        "count": len(period_data),
    }


def calc_vwap(trading_data: list[dict]) -> float:
    """计算VWAP(成交量加权均价)
    即分时图中的"黄线"、均价线
    VWAP = sum(close_i * volume_i) / sum(volume_i)
    """
    total_value = 0.0
    total_vol = 0
    for d in trading_data:
        vol = d["volume"]
        total_value += d["close"] * vol
        total_vol += vol
    if total_vol == 0:
        return 0.0
    return total_value / total_vol


def calc_vwap_envelope(price: float, vwap: float) -> dict:
    """计算当前价与VWAP的关系"""
    if vwap <= 0:
        return {
            "price_above_vwap": None,
            "deviation_pct": None,
            "label": "数据不足",
        }
    deviation = (price - vwap) / vwap * 100
    if deviation > 3:
        label = "价格远超均价线(>3%)，高位注意风险"
    elif deviation > 1:
        label = "价格在均价线上方，多头占优"
    elif deviation > -1:
        label = "价格围绕均价线波动，多空平衡"
    elif deviation > -3:
        label = "价格在均价线下方，空头占优"
    else:
        label = "价格远低于均价线(< -3%)，弱势"
    return {
        "price_above_vwap": deviation > 0,
        "deviation_pct": round(deviation, 2),
        "label": label,
    }

# ============================================================
# 对比与分析
# ============================================================

def extract_auction_volume(day_data: list[dict]) -> dict:
    """提取集合竞价量（09:25 那根K线）

    新浪分时数据中 09:25 的 K 线即为集合竞价成交数据。
    day_data 是 split_by_day() 返回的某一天完整数据（含 09:25）。
    """
    for item in day_data:
        hhmm = extract_hhmm(item["time"])
        if hhmm == "09:25" and item["volume"] > 0:
            return {
                "volume": item["volume"] // 100,  # 转换为手
                "amount": item["amount"],
                "price": item["close"],
                "found": True,
            }
    return {"volume": 0, "amount": 0.0, "price": 0.0, "found": False}


def compare_auction_volume(today_auction: dict, prev_auction: dict) -> dict:
    """对比今日与前日竞价量，判断开盘强弱

    阈值来自实战资料：
    - 今日竞价量 < 昨日 70% → 缩量，不好做T，冲高概率低
    - 今日竞价量 > 昨日 130% → 放量，有承接基础
    """
    if not today_auction["found"]:
        return {
            "today_volume": 0, "prev_volume": 0,
            "ratio": None, "signal": "数据不足",
            "level": "未知", "description": "今日竞价数据缺失",
        }
    if not prev_auction["found"] or prev_auction["volume"] == 0:
        return {
            "today_volume": today_auction["volume"],
            "today_amount": today_auction["amount"],
            "prev_volume": 0, "prev_amount": 0.0,
            "ratio": None, "signal": "数据不足",
            "level": "未知", "description": "前日竞价数据缺失，无法对比",
        }

    ratio = today_auction["volume"] / prev_auction["volume"]

    if ratio > 1.3:
        signal, level = "放量开盘", "强"
        description = f"竞价量是昨日的{ratio:.1f}倍，开盘承接力强，冲高概率高"
    elif ratio > 1.0:
        signal, level = "温和放量开盘", "中"
        description = f"竞价量略高于昨日({ratio:.2f}x)，开盘有一定承接"
    elif ratio > 0.7:
        signal, level = "平量开盘", "中"
        description = f"竞价量与昨日相当({ratio:.2f}x)，开盘强弱待观察"
    else:
        signal, level = "缩量开盘", "弱"
        description = f"竞价量仅为昨日的{ratio:.0%}，不好做T，冲高概率低"

    return {
        "today_volume": today_auction["volume"],
        "today_amount": today_auction["amount"],
        "prev_volume": prev_auction["volume"],
        "prev_amount": prev_auction["amount"],
        "ratio": round(ratio, 2),
        "signal": signal,
        "level": level,
        "description": description,
    }


def detect_expectation_gap(
    prev_limit_up: bool | None,
    today_open: float,
    pre_close: float,
    auction_comparison: dict,
) -> dict:
    """检测预期差（基于前日涨停情况和今日开盘表现）

    逻辑来自实战资料第一章：
    - 前日强势涨停 → 市场预期次日高开甚至顶一字
    - 若次日低开或竞价缩量 → 低于预期，存在预期差博弈机会

    gap_type:
        "below_expectation"  低于预期
        "meet_expectation"   符合预期
        "above_expectation"  高于预期
        "no_prior_signal"    前日无明显信号，无法判断预期差
    """
    if prev_limit_up is None:
        return {
            "gap_type": "no_prior_signal",
            "gap_level": "none",
            "description": "前日数据不足，无法判断预期差",
            "actionable": False,
            "action_hint": "",
        }

    if not prev_limit_up:
        open_pct = (today_open - pre_close) / pre_close * 100 if pre_close > 0 else 0
        if open_pct > 3:
            return {
                "gap_type": "above_expectation",
                "gap_level": "moderate",
                "description": f"前日未涨停但今日高开{open_pct:.1f}%，高于一般预期，追高需谨慎",
                "actionable": False,
                "action_hint": "",
            }
        return {
            "gap_type": "no_prior_signal",
            "gap_level": "none",
            "description": "前日未涨停，无强预期基础，不适用预期差分析",
            "actionable": False,
            "action_hint": "",
        }

    # 前日涨停，有强预期
    open_pct = (today_open - pre_close) / pre_close * 100 if pre_close > 0 else 0
    auction_ratio = auction_comparison.get("ratio")

    if open_pct < -2:
        return {
            "gap_type": "below_expectation",
            "gap_level": "strong",
            "description": f"前日涨停+今日低开{open_pct:.1f}%，严重低于预期",
            "actionable": True,
            "action_hint": "持仓者：开盘30分钟不翻红立即卖出；未持仓者：观望，等企稳信号",
        }
    elif open_pct < 0:
        auction_weak = auction_ratio is not None and auction_ratio < 0.7
        if auction_weak:
            return {
                "gap_type": "below_expectation",
                "gap_level": "moderate",
                "description": f"前日涨停+今日低开{open_pct:.1f}%+竞价缩量({auction_ratio:.2f}x)，低于预期",
                "actionable": True,
                "action_hint": "持仓者：密切关注30分钟内能否翻红；未持仓者：暂不介入",
            }
        else:
            return {
                "gap_type": "below_expectation",
                "gap_level": "weak",
                "description": f"前日涨停+今日小幅低开{open_pct:.1f}%，轻微低于预期，关注能否快速翻红",
                "actionable": True,
                "action_hint": "持仓者：观察30分钟内走势；未持仓者：等翻红后量能确认再介入",
            }
    elif open_pct < 3:
        return {
            "gap_type": "meet_expectation",
            "gap_level": "none",
            "description": f"前日涨停+今日小幅高开{open_pct:.1f}%，基本符合预期",
            "actionable": False,
            "action_hint": "",
        }
    else:
        return {
            "gap_type": "above_expectation",
            "gap_level": "moderate",
            "description": f"前日涨停+今日高开{open_pct:.1f}%，高于预期。注意：高开后若无量跟进易回落",
            "actionable": True,
            "action_hint": "持仓者：高开超3%可先卖部分锁利；未持仓者：高开不追，等回踩",
        }


def calc_composite_score(
    open_pct: float,
    open_amt_ratio: float | None,
    auction_ratio: float | None,
    support_signal: str,
    vwap_deviation: float | None,
    all_amt_ratio: float | None,
    gap_type: str,
    gap_level: str,
) -> dict:
    """多维度综合评分（脚本内可计算的3个维度）

    重要原则：数据不足时不填充默认分，而是标记该子项为 None 并降低满分。
    只有真实获取到的数据才参与评分，避免因数据缺失导致评分虚高影响投资决策。

    趋势评分（第4维度，25分）需要历史日K线，由 Claude 在报告生成时补充。
    脚本输出 partial_total 和 max_partial（实际满分），Claude 加上趋势分后输出总分。

    维度1：量能评分（满分动态，最高25分）
        早盘占比(8) + 早盘额比(9，需前日数据) + 竞价量比(8，需竞价数据)

    维度2：承接力评分（满分动态，最高25分）
        量价信号(15) + VWAP关系(8，需VWAP数据) + 全天额比奖励(2，需前日数据)

    维度3：预期差评分（满分25分）
        gap_type/level 映射分值
    """
    scores = {}
    details = {}
    missing_data = []  # 记录缺失的数据项

    # --- 维度1：量能评分 ---
    vol_score = 0
    vol_max = 25  # 动态满分，根据数据可用性调整

    if open_pct >= 30:
        vol_score += 8
        details["早盘占比"] = f"{open_pct:.1f}% → +8"
    elif open_pct >= 20:
        vol_score += 4
        details["早盘占比"] = f"{open_pct:.1f}% → +4"
    else:
        details["早盘占比"] = f"{open_pct:.1f}% → +0（缩量警示）"

    if open_amt_ratio is not None:
        if open_amt_ratio > 1.3:
            vol_score += 9
            details["早盘额比"] = f"{open_amt_ratio:.2f} → +9"
        elif open_amt_ratio > 1.1:
            vol_score += 6
            details["早盘额比"] = f"{open_amt_ratio:.2f} → +6"
        elif open_amt_ratio > 0.9:
            vol_score += 4
            details["早盘额比"] = f"{open_amt_ratio:.2f} → +4"
        elif open_amt_ratio > 0.7:
            vol_score += 2
            details["早盘额比"] = f"{open_amt_ratio:.2f} → +2"
        else:
            details["早盘额比"] = f"{open_amt_ratio:.2f} → +0"
    else:
        vol_max -= 9  # 无前日数据，降低满分
        details["早盘额比"] = "无前日数据，此项不计分"
        missing_data.append("早盘额比（无前日对比数据）")

    if auction_ratio is not None:
        if auction_ratio > 1.3:
            vol_score += 8
            details["竞价量比"] = f"{auction_ratio:.2f} → +8"
        elif auction_ratio >= 1.0:
            vol_score += 5
            details["竞价量比"] = f"{auction_ratio:.2f} → +5"
        elif auction_ratio >= 0.7:
            vol_score += 3
            details["竞价量比"] = f"{auction_ratio:.2f} → +3"
        else:
            details["竞价量比"] = f"{auction_ratio:.2f} → +0"
    else:
        vol_max -= 8  # 无竞价数据，降低满分
        details["竞价量比"] = "无竞价数据，此项不计分"
        missing_data.append("竞价量比（分时数据不含09:25）")

    scores["volume"] = vol_score
    scores["volume_max"] = vol_max

    # --- 维度2：承接力评分 ---
    acc_score = 0
    acc_max = 25

    if "放量上涨" in support_signal:
        acc_score += 15
        details["量价信号"] = f"{support_signal} → +15"
    elif "缩量回调" in support_signal:
        acc_score += 12
        details["量价信号"] = f"{support_signal} → +12"
    elif "平量上涨" in support_signal or "缩量上涨" in support_signal:
        acc_score += 8
        details["量价信号"] = f"{support_signal} → +8"
    elif "微涨" in support_signal:
        acc_score += 6
        details["量价信号"] = f"{support_signal} → +6"
    elif "横盘" in support_signal:
        acc_score += 4
        details["量价信号"] = f"{support_signal} → +4"
    elif "微跌" in support_signal or "平量回调" in support_signal:
        acc_score += 3
        details["量价信号"] = f"{support_signal} → +3"
    elif support_signal in ("数据不足", "无昨收数据", ""):
        acc_max -= 15
        details["量价信号"] = "数据不足，此项不计分"
        missing_data.append("量价信号（无昨收数据）")
    else:
        details["量价信号"] = f"{support_signal} → +0"

    if vwap_deviation is not None:
        if 1 <= vwap_deviation <= 3:
            acc_score += 8
            details["VWAP关系"] = f"高于均价{vwap_deviation:.1f}% → +8"
        elif -1 <= vwap_deviation < 1:
            acc_score += 5
            details["VWAP关系"] = f"围绕均价{vwap_deviation:.1f}% → +5"
        elif -3 <= vwap_deviation < -1:
            acc_score += 2
            details["VWAP关系"] = f"低于均价{vwap_deviation:.1f}% → +2"
        elif vwap_deviation > 3:
            details["VWAP关系"] = f"远超均价{vwap_deviation:.1f}% → +0（高位风险）"
        else:
            details["VWAP关系"] = f"远低均价{vwap_deviation:.1f}% → +0（弱势）"
    else:
        acc_max -= 8
        details["VWAP关系"] = "无成交数据，此项不计分"
        missing_data.append("VWAP关系（无分时数据）")

    if all_amt_ratio is not None:
        if all_amt_ratio > 1.2:
            acc_score += 2
            details["全天额比"] = f"{all_amt_ratio:.2f} → +2"
        elif all_amt_ratio >= 0.8:
            acc_score += 1
            details["全天额比"] = f"{all_amt_ratio:.2f} → +1"
    else:
        acc_max -= 2
        details["全天额比"] = "无前日数据，此项不计分"

    scores["acceptance"] = acc_score
    scores["acceptance_max"] = acc_max

    # --- 维度3：预期差评分 ---
    gap_score_map = {
        ("above_expectation", "moderate"): 18,
        ("meet_expectation", "none"): 15,
        ("no_prior_signal", "none"): 12,
        ("below_expectation", "weak"): 10,
        ("below_expectation", "moderate"): 6,
        ("below_expectation", "strong"): 2,
    }
    exp_score = gap_score_map.get((gap_type, gap_level), 12)
    scores["expectation"] = exp_score
    scores["expectation_max"] = 25
    details["预期差"] = f"{gap_type}/{gap_level} → +{exp_score}"

    # --- 汇总（动态满分制）---
    partial_total = vol_score + acc_score + exp_score
    max_partial = vol_max + acc_max + 25  # 实际满分（排除缺失数据项后）

    # 评级基于实际满分的百分比，而非固定阈值
    if max_partial > 0:
        score_pct = partial_total / max_partial
        if score_pct >= 0.80:
            partial_rating = "强势（待趋势确认）"
        elif score_pct >= 0.60:
            partial_rating = "偏多（待趋势确认）"
        elif score_pct >= 0.40:
            partial_rating = "中性"
        else:
            partial_rating = "偏空"
    else:
        partial_rating = "数据不足，无法评级"

    return {
        "scores": scores,
        "partial_total": partial_total,
        "max_partial": max_partial,
        "partial_rating": partial_rating,
        "details": details,
        "missing_data": missing_data,
        "note": f"趋势评分(0-25)由Claude基于历史K线补充，当前满分{max_partial}+25={max_partial+25}分",
    }


def compare_same_period(today: dict, prev: dict, period_name: str) -> dict:
    """对比同一时段的量能变化，以额比为主判断趋势

    额比 = 今日成交额 / 前日成交额
    额比比量比更能真实反映资金参与度(价格变动影响成交额)
    """
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

    # 以额比为主判断趋势(额比更能真实反映资金参与度)
    if amt_ratio > 1.3:
        trend = "明显增量"
    elif amt_ratio > 1.1:
        trend = "温和增量"
    elif amt_ratio < 0.7:
        trend = "明显缩量"
    elif amt_ratio < 0.9:
        trend = "温和缩量"
    else:
        trend = "基本持平"

    # 额比与量比背离时附加标记
    if amt_ratio > 1.2 and vol_ratio < 0.9:
        trend += "(高价成交放量)"

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


def calc_turnover_rate(volume_lots: int, float_shares: int) -> float:
    """计算换手率"""
    if float_shares <= 0:
        return 0
    volume_shares = volume_lots * 100
    return round(volume_shares / float_shares * 100, 2)


def get_turnover_rating(turnover: float) -> str:
    """换手率评级（对齐实战标准）
    - 大盘蓝筹: 正常3-7%, 活跃7-15%, 高热15%+
    - 热门题材股: 正常7-15%, 活跃15-25%, 高热25%+
    - 次新股: 正常15-25%, 活跃25-40%, 高热40%+
    以下为通用评级，具体需结合个股市值判断
    """
    if turnover < 1:
        return "极度低迷(无人问津)"
    elif turnover < 3:
        return "低迷(交投清淡)"
    elif turnover < 7:
        return "正常(常规交易)"
    elif turnover < 15:
        return "活跃(资金关注)"
    elif turnover < 25:
        return "高度活跃(热门标的)"
    else:
        return "异常放量(筹码剧烈交换，需警惕)"

# ============================================================
# 核心分析函数
# ============================================================

def analyze_support_power(today_data: list[dict], prev_data: list[dict],
                           pre_close: float) -> dict:
    """分析承接力（量价配合判断）v3.0

    修复: 使用pre_close(昨收)作为价格变动基准，而非当日第一根K线
    """
    if not today_data:
        return {"price_change_pct": 0, "volume_ratio": 0,
                "signal": "数据不足", "power": "无法判断"}

    # 使用昨收价作为基准计算涨跌幅(正确做法)
    current_price = today_data[-1]["close"]
    today_price_change = (current_price - pre_close) / pre_close * 100

    if not prev_data:
        return {
            "price_change_pct": round(today_price_change, 2),
            "volume_ratio": None,
            "signal": "上涨" if today_price_change > 0 else ("下跌" if today_price_change < 0 else "横盘"),
            "power": "仅基于价格变动判断，无前日量比参考",
        }

    # 计算今日总量能
    today_total_vol = sum(d["volume"] for d in today_data if d["volume"] > 0)

    # 计算前一日同时段量能
    today_end_time = extract_hhmm(today_data[-1]["time"])
    prev_same_period = [
        d for d in prev_data
        if extract_hhmm(d["time"]) <= today_end_time and d["volume"] > 0
    ]
    prev_total_vol = sum(d["volume"] for d in prev_same_period) if prev_same_period else 0
    prev_total_amt = sum(d["amount"] for d in prev_same_period) if prev_same_period else 0
    today_total_amt = sum(d["amount"] for d in today_data if d["volume"] > 0)

    # 以额比为主判断量能变化
    amt_ratio = today_total_amt / prev_total_amt if prev_total_amt > 0 else None
    vol_ratio = today_total_vol / prev_total_vol if prev_total_vol > 0 else None

    # 确定主要量比(优先用额比)
    primary_ratio = amt_ratio if amt_ratio is not None else (vol_ratio if vol_ratio is not None else 0)

    signal = ""
    power = ""

    if today_price_change < -0.5:
        if primary_ratio < 0.8:
            signal = "缩量回调"
            power = "承接力强（主力护盘，散户惜售不抛）"
        elif primary_ratio > 1.2:
            signal = "放量下跌"
            power = "承接力弱（主力出货，恐慌抛售）"
        else:
            signal = "平量回调"
            power = "承接力一般（关注支撑位）"
    elif today_price_change < 0:
        signal = "微跌"
        power = "回调幅度小，承接力尚可"
    elif today_price_change > 0.5:
        if primary_ratio > 1.2:
            signal = "放量上涨"
            power = "量价配合好（主力积极做多）"
        elif primary_ratio < 0.8 and primary_ratio > 0:
            signal = "缩量上涨"
            power = "量价背离（主力控盘锁仓或散户推动，关注持续性）"
        else:
            signal = "平量上涨"
            power = "量价正常，趋势健康"
    elif today_price_change > 0:
        signal = "微涨"
        power = "涨幅较小，量价正常"
    else:
        signal = "横盘整理"
        power = "多空平衡，等待方向选择"

    result = {
        "price_change_pct": round(today_price_change, 2),
        "volume_ratio": round(vol_ratio, 2) if vol_ratio is not None else None,
        "amount_ratio": round(amt_ratio, 2) if amt_ratio is not None else None,
        "signal": signal,
        "power": power,
    }
    return result


def build_sell_signals(trading_data: list[dict], pre_close: float,
                       vwap: float, prev_limit_up: bool = None) -> list[dict]:
    """基于卖出三部曲生成卖出/持仓信号

    资料规则:
    1. 前日涨停股: 开盘30分钟不红盘(price<昨收) → 卖出信号
    2. 前日未涨停股: 开盘1小时不红盘 → 卖出信号
    3. 冲高回落: 盘中涨幅超2%后回落到黄线(VWAP)下方 → 卖出信号
    4. 尾盘: 不涨停 → 卖出信号

    返回信号列表，每个信号含 type/level/message
    """
    signals = []
    if not trading_data:
        return signals

    current_price = trading_data[-1]["close"]
    is_red = current_price > pre_close  # 红盘(高于昨收)
    current_time_str = extract_hhmm(trading_data[-1]["time"])

    # 计算盘中最高涨幅(相对于昨收)
    day_high = max(d["close"] for d in trading_data)
    max_gain_pct = (day_high - pre_close) / pre_close * 100

    # 规则1 & 2: 基于开盘表现的卖出信号
    if current_time_str >= "10:00":
        if prev_limit_up is True:
            if not is_red:
                signals.append({
                    "type": "卖出信号",
                    "level": "强",
                    "message": "前日涨停+开盘30分钟不红盘，按三部曲应卖出"
                })
                signals.append({
                    "type": "参考",
                    "level": "中",
                    "message": "前日涨停股开盘半小时不红盘即走，是游资铁律"
                })
        elif prev_limit_up is False:
            if not is_red and current_time_str >= "10:31":
                signals.append({
                    "type": "卖出信号",
                    "level": "中",
                    "message": "前日未涨停+开盘1小时不红盘，按三部曲应卖出"
                })

    # 规则3: 冲高回落破黄线
    if vwap > 0 and max_gain_pct > 2:
        # 检查是否从高处回落到黄线下方
        price_below_vwap = current_price < vwap
        if price_below_vwap:
            signals.append({
                "type": "卖出信号",
                "level": "强",
                "message": f"盘中最高涨{max_gain_pct:.1f}%后回落破均价线，按三部曲应卖出(锁利)"
            })

    # 规则4: 尾盘判断
    if current_time_str >= "14:50":
        limit_up_price = round(pre_close * 1.10, 2)
        if current_price < limit_up_price:
            signals.append({
                "type": "持仓建议",
                "level": "中",
                "message": "尾盘未涨停，按三部曲应考虑卖出(除非红盘且趋势向好)"
            })

    # 额外保护信号: VWAP偏离过大
    if vwap > 0:
        deviation = (current_price - vwap) / vwap * 100
        if deviation > 3:
            signals.append({
                "type": "风控提醒",
                "level": "中",
                "message": f"价格高出均价线{deviation:.1f}%，建议卖出部分锁利"
            })

    return signals


def detect_limit_status(price: float, pre_close: float,
                        code: str = "") -> dict:
    """检测涨停/跌停状态（基于昨收价正确计算）"""
    if pre_close <= 0:
        return {"status": "未知", "limit_up": False, "limit_down": False}

    # 判断股票类型
    is_kcb_cyb = code.startswith(("68", "30"))  # 科创/创业板
    is_st = "ST" in code or "*ST" in code  # ST股(这里简化判断)

    limit_up, limit_down = get_limit_price(pre_close, is_st, is_kcb_cyb)
    tolerance = 0.01  # 1分钱容差

    is_limit_up = abs(price - limit_up) <= tolerance
    is_limit_down = abs(price - limit_down) <= tolerance

    if is_limit_up:
        status = "涨停"
    elif is_limit_down:
        status = "跌停"
    else:
        status = "正常交易"

    return {
        "status": status,
        "limit_up": is_limit_up,
        "limit_down": is_limit_down,
        "limit_up_price": limit_up,
        "limit_down_price": limit_down,
    }


def detect_prev_limit_up(prev_data: list[dict], pre_close: float) -> bool:
    """判断前一日是否涨停

    通过前一日数据: 如果前一日收盘价 ≈ 昨收(即今日的pre_close)
    且前一日开盘后的价格变动较小(典型涨停特征: 高开或一字板)
    简化判断: 只要前一日最后价格与前一日开盘价差别极小且全天波动小
    """
    if not prev_data or len(prev_data) < 10:
        return False

    trading_prev = [d for d in prev_data
                    if "09:30" <= extract_hhmm(d["time"]) <= "15:00"
                    and d["volume"] > 0]

    if not trading_prev:
        return False

    prev_close_price = trading_prev[-1]["close"]
    prev_high = max(d["high"] for d in trading_prev)
    prev_low = min(d["low"] for d in trading_prev)

    # 涨停特征: 全天波动极小(高低差<1%)，且收盘在最高点附近
    if prev_low > 0:
        day_range = (prev_high - prev_low) / prev_low * 100
        close_near_high = abs(prev_close_price - prev_high) <= 0.01
        if day_range < 1.5 and close_near_high:
            return True

    # 另一种: 收盘价接近涨停价(今日pre_close * 1.10)
    # 但我们不知道前天的pre_close，所以用开盘价近似
    # 如果前日开盘到收盘涨幅接近10%且收盘=最高
    prev_open = trading_prev[0]["open"]
    if prev_open > 0:
        prev_change = (prev_close_price - prev_open) / prev_open * 100
        if prev_change > 9.0 and close_near_high:
            return True

    return False

def analyze_minute_volume(minute_data: list[dict], float_shares: int = 0,
                           pre_close: float = None, code: str = "",
                           auction_today_shares: int = 0,
                           auction_prev_shares: int = 0) -> dict:
    """分析分时量能 v3.0

    P0修复: 集合竞价过滤(09:30开始)、涨停检测基于pre_close、承接力使用pre_close
    P1新增: VWAP计算、卖出三部曲信号、前两天均值对比
    """
    if not minute_data:
        return {"error": "无分时数据"}

    days = split_by_day(minute_data)
    sorted_dates = sorted(days.keys())

    if len(sorted_dates) < 1:
        return {"error": "无有效交易日数据"}

    today_date = sorted_dates[-1]
    today_data = days[today_date]

    # --- 集合竞价量提取（在过滤 09:30 之前进行）---
    # 优先使用外部传入的竞价量（来自 mx-data），否则尝试从分时数据提取
    if auction_today_shares > 0:
        today_auction = {"volume": auction_today_shares // 100, "amount": 0.0, "price": 0.0, "found": True}
    else:
        today_auction = extract_auction_volume(today_data)

    # 过滤连续竞价时段(09:30-15:00)，排除集合竞价
    trading_data = [
        d for d in today_data
        if d["volume"] > 0 and "09:30" <= extract_hhmm(d["time"]) <= "15:00"
    ]

    if not trading_data:
        return {"error": "无有效交易数据(今日尚未开盘或数据缺失)"}

    # --- 基础统计 ---
    total_vol = sum(d["volume"] for d in trading_data)
    total_amt = sum(d["amount"] for d in trading_data)

    def period_stats(start: str, end: str) -> dict:
        return calc_period_stats(trading_data, start, end)

    open_30 = period_stats("09:30", "10:00")
    mid_am = period_stats("10:00", "11:30")
    mid_pm = period_stats("13:00", "14:30")
    close_30 = period_stats("14:30", "15:01")

    # --- VWAP 计算 ---
    vwap = calc_vwap(trading_data)
    current_price = trading_data[-1]["close"] if trading_data else 0
    vwap_info = calc_vwap_envelope(current_price, vwap)

    # --- 前两日数据获取(用于均值对比) ---
    prev_data_1 = None
    prev_data_2 = None
    prev_date_1 = None
    if len(sorted_dates) >= 2:
        prev_date_1 = sorted_dates[-2]
        prev_data_1 = days[prev_date_1]
    if len(sorted_dates) >= 3:
        prev_data_2 = days[sorted_dates[-3]]

    # --- 前日竞价量提取 ---
    if auction_prev_shares > 0:
        prev_auction = {"volume": auction_prev_shares // 100, "amount": 0.0, "price": 0.0, "found": True}
    else:
        prev_auction = extract_auction_volume(prev_data_1) if prev_data_1 else {
            "found": False, "volume": 0, "amount": 0.0, "price": 0.0
        }

    # --- 判断前日是否涨停（提前到此处，detect_expectation_gap 需要）---
    prev_limit_up = None
    if prev_data_1:
        prev_limit_up = detect_prev_limit_up(prev_data_1, pre_close)

    # --- 同时段对比(对比前两天均值) ---
    prev_comparison = {}
    if prev_data_1:
        def prev_trading_for(data):
            return [d for d in data
                    if d["volume"] > 0 and "09:30" <= extract_hhmm(d["time"]) <= "15:00"]

        p1 = prev_trading_for(prev_data_1)
        p1_open = calc_period_stats(p1, "09:30", "10:00")
        p1_mid_am = calc_period_stats(p1, "10:00", "11:30")
        p1_mid_pm = calc_period_stats(p1, "13:00", "14:30")
        p1_close = calc_period_stats(p1, "14:30", "15:01")

        if prev_data_2:
            p2 = prev_trading_for(prev_data_2)
            # 只有当日-2至少有60条数据(约1小时交易)时才纳入均值
            if len(p2) >= 60:
                p2_open = calc_period_stats(p2, "09:30", "10:00")
                p2_mid_am = calc_period_stats(p2, "10:00", "11:30")
                p2_mid_pm = calc_period_stats(p2, "13:00", "14:30")
                p2_close = calc_period_stats(p2, "14:30", "15:01")

                def avg_two(a, b):
                    return {
                        "volume": (a["volume"] + b["volume"]) // 2,
                        "volume_lots": (a["volume_lots"] + b["volume_lots"]) // 2,
                        "amount": (a["amount"] + b["amount"]) / 2,
                        "count": (a["count"] + b["count"]) // 2,
                    }
                prev_open = avg_two(p1_open, p2_open)
                prev_mid_am = avg_two(p1_mid_am, p2_mid_am)
                prev_mid_pm = avg_two(p1_mid_pm, p2_mid_pm)
                prev_close = avg_two(p1_close, p2_close)
                comparison_base = "前两日均值"
            else:
                prev_open = p1_open
                prev_mid_am = p1_mid_am
                prev_mid_pm = p1_mid_pm
                prev_close = p1_close
                comparison_base = prev_date_1
        else:
            prev_open = p1_open
            prev_mid_am = p1_mid_am
            prev_mid_pm = p1_mid_pm
            prev_close = p1_close
            comparison_base = prev_date_1

        prev_comparison = {
            "open_30min": compare_same_period(open_30, prev_open, "早盘30分"),
            "mid_am": compare_same_period(mid_am, prev_mid_am, "上午中段"),
            "mid_pm": compare_same_period(mid_pm, prev_mid_pm, "下午中段"),
            "close_30min": compare_same_period(close_30, prev_close, "尾盘30分"),
            "prev_date": comparison_base,
        }

    # --- 竞价量对比 ---
    auction_comparison = compare_auction_volume(today_auction, prev_auction)

    # --- 预期差检测 ---
    today_open_price = trading_data[0]["open"] if trading_data else 0.0
    expectation_gap = detect_expectation_gap(
        prev_limit_up=prev_limit_up,
        today_open=today_open_price,
        pre_close=pre_close or 0.0,
        auction_comparison=auction_comparison,
    )

    # --- 主力动向信号(去重处理: 同时满足>30%和>40%只触发最高级) ---
    signals = []
    if total_vol > 0:
        if close_30["volume"] / total_vol > 0.25:
            signals.append("尾盘大幅放量(>25%)，可能有主力抢筹或出货")
        elif close_30["volume"] / total_vol > 0.15:
            signals.append("尾盘有一定放量(15-25%)")

        open_ratio = open_30["volume"] / total_vol if total_vol > 0 else 0
        open_amt_ratio = None
        if prev_comparison and "open_30min" in prev_comparison:
            open_amt_ratio = prev_comparison["open_30min"].get("amount_ratio")

        # 去重: 用elif链，只触发最高级别
        if open_ratio > 0.40:
            if open_amt_ratio is not None and open_amt_ratio > 1.2:
                signals.append("早盘强势放量(占比>40%+额比高)，主力强力介入")
            elif open_amt_ratio is not None and open_amt_ratio > 0.8:
                signals.append("早盘放量异常(占比>40%)，主力高度活跃")
            else:
                signals.append("早盘高度集中(占比>40%)，主力高度控盘")
        elif open_ratio > 0.30:
            if open_amt_ratio is not None and open_amt_ratio > 1.2:
                signals.append("早盘放量抢筹(占比>30%+额比高，主力积极介入)")
            elif open_amt_ratio is not None and open_amt_ratio > 0.8:
                signals.append("早盘正常交易(占比>30%+额比正常)")
            else:
                signals.append("早盘控盘缩量(占比>30%+额比低，主力高度控盘)")
        elif open_ratio < 0.20 and open_ratio > 0:
            # 资料核心阈值: 早盘占比<20%全天基本无戏
            signals.append("早盘成交占比<20%(缩量明显)，今日基本无戏，建议观望")

    # --- 涨停/跌停检测(基于pre_close正确计算) ---
    if pre_close and pre_close > 0:
        limit_info = detect_limit_status(current_price, pre_close, code)
        if limit_info["limit_up"]:
            signals.append("涨停封板中，关注封单量和开板风险")
        elif limit_info["limit_down"]:
            signals.append("跌停封板中，不宜抄底")
    else:
        limit_info = {"status": "无法判断", "limit_up": False, "limit_down": False}

    # --- 承接力分析 ---
    support_power = {}
    if pre_close and pre_close > 0:
        support_power = analyze_support_power(trading_data, prev_data_1, pre_close)
    else:
        support_power = {"price_change_pct": 0, "volume_ratio": None,
                         "signal": "无昨收数据", "power": "无法判断"}

    # --- 卖出三部曲信号 ---
    sell_signals = []
    if pre_close and pre_close > 0:
        sell_signals = build_sell_signals(trading_data, pre_close, vwap, prev_limit_up)

    # --- 综合评分 ---
    _open_pct = round(open_30["volume"] / total_vol * 100, 1) if total_vol else 0
    _open_amt_ratio = None
    if prev_comparison and "open_30min" in prev_comparison:
        _open_amt_ratio = prev_comparison["open_30min"].get("amount_ratio")
    _auction_ratio = auction_comparison.get("ratio")
    _support_signal = support_power.get("signal", "")
    _vwap_dev = vwap_info.get("deviation_pct")
    _all_amt_ratio = support_power.get("amount_ratio")
    composite_score = calc_composite_score(
        open_pct=_open_pct,
        open_amt_ratio=_open_amt_ratio,
        auction_ratio=_auction_ratio,
        support_signal=_support_signal,
        vwap_deviation=_vwap_dev,
        all_amt_ratio=_all_amt_ratio,
        gap_type=expectation_gap.get("gap_type", "no_prior_signal"),
        gap_level=expectation_gap.get("gap_level", "none"),
    )

    # --- 换手率 ---
    turnover_rate = None
    turnover_rating = None
    if float_shares > 0:
        turnover_rate = calc_turnover_rate(total_vol // 100, float_shares)
        turnover_rating = get_turnover_rating(turnover_rate)

    # --- 放量时段 TOP 10 ---
    sorted_by_vol = sorted(trading_data, key=lambda x: x["volume"], reverse=True)[:10]
    top_volumes = [
        {
            "time": d["time"][-8:],
            "price": d["close"],
            "volume": d["volume"] // 100,
            "amount": d["amount"],
        }
        for d in sorted_by_vol
    ]

    return {
        "today_date": today_date,
        "total_volume": total_vol // 100,
        "total_amount": total_amt,
        "current_price": current_price,
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
        # v3.0 新增
        "vwap": round(vwap, 2),
        "vwap_info": vwap_info,
        "limit_info": limit_info,
        "prev_limit_up": prev_limit_up,
        "sell_signals": sell_signals,
        # v5.0 新增
        "auction_comparison": auction_comparison,
        "expectation_gap": expectation_gap,
        "composite_score": composite_score,
    }


# ============================================================
# 输出模板系统 v3.1
# ============================================================

@dataclass
class TableDef:
    """表格定义"""
    headers: list[str]
    rows: list[list[str]]
    aligns: list[str] = field(default_factory=list)


@dataclass
class Section:
    """报告章节"""
    title: str
    body: list[str] = field(default_factory=list)
    table: TableDef | None = None


@dataclass
class Report:
    """分析报告"""
    title: str = ""
    subtitle: str = ""
    sections: list[Section] = field(default_factory=list)
    summary_signals: list[str] = field(default_factory=list)
    footer_note: str = ""


# ---- 表格渲染 ----

def _text_table(t: TableDef) -> str:
    """渲染为终端对齐表格"""
    if not t.rows:
        return ""
    ncols = len(t.headers)
    widths = [len(h) for h in t.headers]
    for row in t.rows:
        for i, cell in enumerate(row):
            if i < ncols:
                widths[i] = max(widths[i], len(cell))
    parts = []
    for i in range(ncols):
        w = widths[i] + 2
        a = t.aligns[i] if i < len(t.aligns) else "<"
        parts.append(f"{{:{'<' if a == '<' else '>'}{w}}}")
    fmt = "    " + "  ".join(parts)
    lines = [fmt.format(*t.headers)]
    sep_parts = ["─" * (widths[i] + 2) for i in range(ncols)]
    lines.append("    " + "  ".join(sep_parts))
    for row in t.rows:
        padded = list(row) + [""] * (ncols - len(row))
        lines.append(fmt.format(*padded))
    return "\n".join(lines)


def _md_table(t: TableDef) -> str:
    """渲染为 GitHub Markdown 表格"""
    if not t.rows:
        return ""
    lines = ["| " + " | ".join(t.headers) + " |"]
    seps = []
    for i in range(len(t.headers)):
        a = t.aligns[i] if i < len(t.aligns) else "<"
        if a == ">":
            seps.append("---:")
        elif a == "<":
            seps.append(":---")
        else:
            seps.append(":---:")
    lines.append("| " + " | ".join(seps) + " |")
    for row in t.rows:
        padded = list(row) + [""] * (len(t.headers) - len(row))
        lines.append("| " + " | ".join(padded) + " |")
    return "\n".join(lines)


# ---- 报告渲染 ----

def render_report_text(report: Report) -> str:
    """渲染为终端文本"""
    W = 62
    lines = ["=" * W, f"  {report.title}"]
    if report.subtitle:
        lines.append(f"  {report.subtitle}")
    lines.append("=" * W)
    for sec in report.sections:
        lines.append("")
        lines.append(f"  [{sec.title}]")
        for line in sec.body:
            lines.append(f"    {line}")
        if sec.table:
            lines.append(_text_table(sec.table))
    if report.summary_signals:
        lines.append("")
        lines.append(f"  {'='*50}")
        lines.append(f"  [综合信号]")
        for s in report.summary_signals:
            lines.append(f"    {s}")
        lines.append(f"  {'='*50}")
    if report.footer_note:
        lines.append(f"\n  {report.footer_note}")
    return "\n".join(lines)


def render_report_md(report: Report) -> str:
    """渲染为 Markdown"""
    lines = [f"## {report.title}", ""]
    if report.subtitle:
        lines.append(f"> {report.subtitle}")
        lines.append("")
    for sec in report.sections:
        lines.append(f"### {sec.title}")
        lines.append("")
        for line in sec.body:
            lines.append(line)
            lines.append("")
        if sec.table:
            lines.append(_md_table(sec.table))
            lines.append("")
    if report.summary_signals:
        lines.append("### 综合信号")
        lines.append("")
        for s in report.summary_signals:
            lines.append(f"- {s}")
        lines.append("")
    if report.footer_note:
        lines.append(f"> *{report.footer_note}*")
        lines.append("")
    return "\n".join(lines)


# ---- 模版构建器 ----

def _build_summary(analysis: dict) -> list[str]:
    """构建综合信号（逻辑集中，避免重复）"""
    signals = []
    sp = analysis.get("support_power", {})
    sig = sp.get("signal", "")
    if "缩量回调" in sig:
        signals.append("[看多] 承接力强: 缩量回调不破支撑，主力护盘")
    elif "放量下跌" in sig:
        signals.append("[看空] 承接力弱: 放量下跌，警惕出货")
    elif "放量上涨" in sig:
        signals.append("[看多] 量价配合: 放量上涨，主力做多")
    elif "缩量上涨" in sig:
        signals.append("[中性] 量价背离: 缩量上涨，关注后续量能")

    if analysis.get("prev_comparison") and "open_30min" in analysis["prev_comparison"]:
        open_pct = analysis["distribution"]["open_30min"]["percent"]
        ar = analysis["prev_comparison"]["open_30min"].get("amount_ratio")
        if ar is not None:
            if open_pct > 30:
                if ar > 1.2:
                    signals.append("[看多] 早盘放量: 资金加速流入")
                elif ar > 0.8:
                    signals.append("[偏多] 早盘活跃: 主力积极参与")
                else:
                    signals.append("[中性] 早盘控盘: 主力高度控盘缩量")
            elif open_pct < 20:
                signals.append("[看空] 早盘缩量: 量能严重不足，建议观望")

    for s in analysis.get("signals", []):
        if "抢筹" in s:
            signals.append(f"[看多] 主力抢筹: {s}")
        elif "出货" in s:
            signals.append(f"[看空] 主力出货: {s}")
        elif "涨停" in s:
            signals.append(f"[看多] 涨停封板: {s}")
        elif "跌停" in s:
            signals.append(f"[看空] 跌停封板: {s}")
        elif "无戏" in s:
            signals.append(f"[看空] 量能不足: {s}")

    if not signals:
        signals.append("[中性] 暂无明显信号，建议观望")
    return signals


def build_realtime_report(data: dict) -> Report:
    """构建实时行情报告（模版化）"""
    cs = "+" if data["change_pct"] >= 0 else ""
    body = [
        f"现价: {data['price']:.2f}  涨跌: {cs}{data['change_pct']:.2f}%",
        f"今开: {data['open']:.2f}  最高: {data['high']:.2f}  最低: {data['low']:.2f}",
        f"昨收: {data['pre_close']:.2f}",
        f"成交量: {data['volume']/10000:,.1f}万手  成交额: {data['amount']/100000000:,.2f}亿",
    ]
    if data.get("turnover"):
        body.append(f"换手率: {data['turnover']:.2f}%")
    if data.get("volume_ratio") is not None:
        vr = data["volume_ratio"]
        lbl = "放量" if vr > 1.2 else ("缩量" if vr < 0.8 else "正常")
        body.append(f"实时量比: {vr:.2f} ({lbl})")
    footer = ""
    if data.get("data_note"):
        footer = f"数据状态: {data['data_status']} | {data['data_note']}"
    return Report(
        title=f"{data['name']} ({data['code']})",
        sections=[Section(title="实时行情", body=body)],
        footer_note=footer,
    )


def _build_review_section(analysis: dict) -> Section:
    """构建盘后复盘数据章节（--review 模式专用）

    输出结构化复盘数据，供 Claude 生成次日操作计划。
    脚本只做数据整理，主观判断由 Claude 完成。
    """
    body = []

    # 今日量能结构
    dist = analysis.get("distribution", {})
    open_pct = dist.get("open_30min", {}).get("percent", 0)
    close_pct = dist.get("close_30min", {}).get("percent", 0)
    body.append(f"早盘占比: {open_pct:.1f}%  尾盘占比: {close_pct:.1f}%")

    # 竞价情况
    ac = analysis.get("auction_comparison", {})
    if ac.get("ratio") is not None:
        body.append(f"竞价量比: {ac['ratio']:.2f}x  [{ac['signal']}]")
    elif ac.get("today_volume", 0) > 0:
        body.append(f"竞价量: {ac['today_volume']:,}手（无前日对比）")

    # 涨停状态
    li = analysis.get("limit_info", {})
    body.append(f"今日收盘状态: {li.get('status', '正常交易')}")

    # 前日涨停情况（用于次日三部曲判断）
    prev_lu = analysis.get("prev_limit_up")
    today_lu = li.get("limit_up", False)
    body.append(f"今日是否涨停: {'是 → 次日三部曲：30分钟不翻红卖出' if today_lu else '否 → 次日三部曲：1小时不翻红卖出'}")
    body.append(f"前日是否涨停: {'是' if prev_lu else ('否' if prev_lu is False else '未知')}")

    # 预期差
    eg = analysis.get("expectation_gap", {})
    body.append("")
    body.append(f"[预期差] {eg.get('description', '无数据')}")
    if eg.get("action_hint"):
        body.append(f"操作提示: {eg['action_hint']}")

    # 综合评分
    cs = analysis.get("composite_score", {})
    if cs:
        scores = cs.get("scores", {})
        max_p = cs.get("max_partial", 75)
        missing = cs.get("missing_data", [])
        body.append("")
        body.append(
            f"[综合评分] 量能{scores.get('volume','?')}/{scores.get('volume_max',25)} + "
            f"承接{scores.get('acceptance','?')}/{scores.get('acceptance_max',25)} + "
            f"预期差{scores.get('expectation','?')}/25 = {cs.get('partial_total','?')}/{max_p}"
        )
        body.append(f"评级: {cs.get('partial_rating', '')}（加趋势分后满{max_p+25}分）")
        if missing:
            body.append(f"⚠ 缺失数据（未计分）: {', '.join(missing)}")

    # 卖出三部曲信号汇总
    sell_sigs = analysis.get("sell_signals", [])
    if sell_sigs:
        body.append("")
        body.append("[三部曲信号]")
        for s in sell_sigs:
            mk = "!!" if s["level"] == "强" else "!"
            body.append(f"  {mk} {s['message']}")

    # VWAP 关键位
    vwap = analysis.get("vwap", 0)
    if vwap > 0:
        body.append("")
        body.append(f"[关键价位] VWAP均价线: {vwap:.2f}（次日跌破此位需警惕）")

    return Section(title="盘后复盘数据（次日操作参考）", body=body)


def build_minute_report(analysis: dict, name: str, review_mode: bool = False) -> Report:
    """构建分时量能分析报告（模版化，章节固定有序）"""
    if "error" in analysis:
        return Report(
            title=f"{name} 分时分析错误",
            sections=[Section(title="错误", body=[analysis["error"]])],
        )

    sections = []

    # ---- 1. 基础数据 ----
    b1 = [
        f"分析日期: {analysis.get('today_date', 'N/A')}",
        f"全天成交: {analysis['total_volume']:,}手 ({analysis['total_amount']/10000:,.1f}万元)",
    ]
    if analysis.get("turnover_rate") is not None:
        b1.append(f"换手率: {analysis['turnover_rate']:.2f}% ({analysis['turnover_rating']})")
    if analysis.get("vwap") and analysis["vwap"] > 0:
        vi = analysis.get("vwap_info", {})
        b1.append(f"均价线(VWAP): {analysis['vwap']:.2f}")
        b1.append(f"当前价 vs 均价线: {vi.get('label', 'N/A')}")
    sections.append(Section(title="基础数据", body=b1))

    # ---- 2. 成交分布 ----
    dist = analysis["distribution"]
    d_rows = []
    for pk, pn in [
        ("open_30min", "早盘30分(9:30-10:00)"),
        ("mid_am", "上午中段(10:00-11:30)"),
        ("mid_pm", "下午中段(13:00-14:30)"),
        ("close_30min", "尾盘30分(14:30-15:00)"),
    ]:
        d = dist[pk]
        ps = f"{d['percent']:.1f}%"
        if pk == "open_30min" and d["percent"] < 20 and d["percent"] > 0:
            ps += " [缩量]"
        d_rows.append([pn, f"{d['volume']:,}", f"{d['amount']/10000:,.1f}", ps])
    sections.append(Section(
        title="成交分布", body=[],
        table=TableDef(
            headers=["时段", "量(手)", "金额(万)", "占比"],
            rows=d_rows, aligns=["<", ">", ">", ">"]),
    ))

    # ---- 3. 同时段对比 ----
    if analysis.get("prev_comparison"):
        pc = analysis["prev_comparison"]
        c_rows = []
        for pk, pn in [
            ("open_30min", "早盘30分"), ("mid_am", "上午中段"),
            ("mid_pm", "下午中段"), ("close_30min", "尾盘30分"),
        ]:
            if pk in pc:
                c = pc[pk]
                c_rows.append([
                    pn,
                    f"{c['today_volume']:,}",
                    f"{c['prev_volume']:,}",
                    f"{c['volume_ratio']:.2f}" if c["volume_ratio"] else "N/A",
                    f"{c['today_amount']/10000:,.1f}",
                    f"{c['prev_amount']/10000:,.1f}",
                    f"{c['amount_ratio']:.2f}" if c.get("amount_ratio") else "N/A",
                    c.get("trend", ""),
                ])
        sections.append(Section(
            title=f"同时段对比 (vs {pc.get('prev_date', '前一日')})", body=[],
            table=TableDef(
                headers=["时段", "今日量", "前日量", "量比", "今日额(万)", "前日额(万)", "额比", "趋势"],
                rows=c_rows, aligns=["<", ">", ">", ">", ">", ">", ">", "<"]),
        ))

    # ---- 4. 承接力判断 ----
    if analysis.get("support_power"):
        sp = analysis["support_power"]
        b4 = [
            f"涨跌幅(相对昨收): {sp['price_change_pct']:+.2f}%",
            f"额比: {sp['amount_ratio']:.2f}" if sp.get("amount_ratio") is not None
            else f"量比: {sp.get('volume_ratio', 'N/A')}",
            f"信号: **{sp['signal']}**  →  {sp['power']}",
        ]
        sections.append(Section(title="承接力判断", body=b4))

    # ---- 5. 早盘量能预期 ----
    op = analysis["distribution"]["open_30min"]["percent"]
    b5 = []
    if analysis.get("prev_comparison") and "open_30min" in analysis["prev_comparison"]:
        ar = analysis["prev_comparison"]["open_30min"].get("amount_ratio")
        if ar is not None:
            if op > 30:
                if ar > 1.2:
                    signal, icon = "放量抢筹 → 主力积极介入", "[看多]"
                elif ar > 0.8:
                    signal, icon = "正常交易 → 主力活跃", "[偏多]"
                else:
                    signal, icon = "控盘缩量 → 主力高度控盘", "[中性]"
            elif op < 20:
                if ar < 0.7:
                    signal, icon = "严重缩量 → 今日基本无戏，强烈建议观望", "[警示]"
                else:
                    signal, icon = "量能不足 → 参与度低，谨慎", "[看空]"
            else:
                if ar > 1.2:
                    signal, icon = "资金后移 → 主力在其他时段积极操作", "[偏多]"
                elif ar > 0.8:
                    signal, icon = "量能分散 → 交易节奏正常", "[中性]"
                else:
                    signal, icon = "整体观望 → 资金参与度低", "[看空]"
            b5.append(f"{icon} 早盘占比: {op:.1f}%  额比: {ar:.2f}")
            b5.append(f"判断: {signal}")
        else:
            b5.append(f"早盘占比: {op:.1f}% (无前日额比数据)")
    else:
        b5.append(f"早盘占比: {op:.1f}% (无前日对比数据)")
    sections.append(Section(title="早盘量能预期", body=b5))

    # ---- 6. 放量时段 TOP 10 ----
    t_rows = []
    for item in analysis.get("top_volumes", [])[:10]:
        t_rows.append([
            item["time"],
            f"{item['price']:.2f}",
            f"{item['volume']:,}",
            f"{item['amount']/10000:,.1f}",
        ])
    sections.append(Section(
        title="放量时段 TOP 10", body=[],
        table=TableDef(
            headers=["时间", "价格", "成交量(手)", "成交额(万)"],
            rows=t_rows, aligns=["<", ">", ">", ">"]),
    ))

    # ---- 7. 主力动向判断 ----
    b7 = list(analysis.get("signals", [])) or ["暂无明显主力异动信号"]
    sections.append(Section(title="主力动向判断", body=b7))

    # ---- 8. 卖出三部曲信号 ----
    if analysis.get("sell_signals"):
        b8 = []
        for sig in analysis["sell_signals"]:
            mk = "!!" if sig["level"] == "强" else ("!" if sig["level"] == "中" else "")
            b8.append(f"[{sig['type']}]{mk} {sig['message']}")
        sections.append(Section(title="卖出三部曲信号", body=b8))

    # ---- 9. 涨跌停状态 ----
    if analysis.get("limit_info"):
        li = analysis["limit_info"]
        if li.get("limit_up") or li.get("limit_down"):
            b9 = [f"状态: {li['status']}"]
            if li.get("limit_up_price"):
                b9.append(f"涨停价: {li['limit_up_price']:.2f}")
            if li.get("limit_down_price"):
                b9.append(f"跌停价: {li['limit_down_price']:.2f}")
            sections.append(Section(title="涨跌停状态", body=b9))

    # ---- 10. 竞价量对比 ----
    ac = analysis.get("auction_comparison", {})
    if ac.get("ratio") is not None or ac.get("today_volume", 0) > 0:
        b10 = []
        if ac.get("today_volume") is not None:
            b10.append(f"今日竞价量: {ac['today_volume']:,}手  ({ac.get('today_amount', 0)/10000:,.1f}万元)")
        if ac.get("prev_volume") is not None and ac["prev_volume"] > 0:
            b10.append(f"前日竞价量: {ac['prev_volume']:,}手  ({ac.get('prev_amount', 0)/10000:,.1f}万元)")
        if ac.get("ratio") is not None:
            b10.append(f"竞价量比: {ac['ratio']:.2f}x  [{ac['signal']}]")
        b10.append(f"研判: {ac.get('description', '')}")
        sections.append(Section(title="竞价量对比", body=b10))

    # ---- 11. 预期差信号 ----
    eg = analysis.get("expectation_gap", {})
    if eg.get("gap_type") and eg["gap_type"] != "no_prior_signal":
        b11 = [eg.get("description", "")]
        if eg.get("action_hint"):
            b11.append(f"操作提示: {eg['action_hint']}")
        sections.append(Section(title="预期差信号", body=b11))

    # ---- 12. 综合评分 ----
    cs = analysis.get("composite_score", {})
    if cs:
        scores = cs.get("scores", {})
        max_p = cs.get("max_partial", 75)
        missing = cs.get("missing_data", [])
        b12 = [
            f"量能: {scores.get('volume', 'N/A')}/{scores.get('volume_max', 25)}  "
            f"承接: {scores.get('acceptance', 'N/A')}/{scores.get('acceptance_max', 25)}  "
            f"预期差: {scores.get('expectation', 'N/A')}/25",
            f"小计: {cs.get('partial_total', 'N/A')}/{max_p}  → {cs.get('partial_rating', '')}",
        ]
        if missing:
            b12.append(f"⚠ 以下数据缺失，对应项未计分：")
            for m in missing:
                b12.append(f"  · {m}")
        b12.append(f"（趋势分25分由Claude基于历史K线补充，总满分{max_p+25}分）")
        sections.append(Section(title="综合评分（脚本部分）", body=b12))

    # ---- 13. 盘后复盘数据（--review 模式）----
    if review_mode:
        sections.append(_build_review_section(analysis))

    return Report(
        title=f"{name} 分时量能分析",
        subtitle=analysis.get("today_date", ""),
        sections=sections,
        summary_signals=_build_summary(analysis),
    )


# ---- 向后兼容接口（portfolio.py 依赖） ----

def format_realtime(data: dict) -> str:
    """格式化实时行情（终端文本）- 向后兼容"""
    return render_report_text(build_realtime_report(data))


def format_minute_analysis(analysis: dict, name: str = "") -> str:
    """格式化分时分析（终端文本）- 向后兼容"""
    report = build_minute_report(analysis, name)
    return "\n" + render_report_text(report)


def format_realtime_md(data: dict) -> str:
    """格式化实时行情（Markdown）"""
    return render_report_md(build_realtime_report(data))


def format_minute_analysis_md(analysis: dict, name: str = "") -> str:
    """格式化分时分析（Markdown）"""
    report = build_minute_report(analysis, name)
    return render_report_md(report)


# ============================================================
# 主入口
# ============================================================

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
        # 将实时量比传递到分时分析结果中
        if realtime.get("volume_ratio") is not None:
            minute_analysis["absolute_volume_ratio"] = realtime["volume_ratio"]
        result["minute_analysis"] = minute_analysis

    return result


def main():
    parser = argparse.ArgumentParser(description="A股实时行情与分时量能分析 v5.0")
    parser.add_argument("codes", nargs="+", help="股票代码，如 600789 002446")
    parser.add_argument("--minute", "-m", action="store_true", help="包含分时量能分析")
    parser.add_argument("--review", "-r", action="store_true", help="盘后复盘模式：输出今日复盘总结和次日操作参考")
    parser.add_argument("--json", "-j", action="store_true", help="JSON格式输出")
    parser.add_argument("--format", "-fmt", choices=["text", "md"], default="text",
                        help="输出格式: text(终端表格) / md(Markdown)")
    parser.add_argument("--float-shares", "-f", type=int, default=0,
                        help="流通股数(用于计算换手率，可从 cn-financial 获取)")
    parser.add_argument("--auction-today-shares", type=int, default=0,
                        help="今日集合竞价成交量(股)，来自 mx-data，如 719500")
    parser.add_argument("--auction-prev-shares", type=int, default=0,
                        help="前日集合竞价成交量(股)，来自 mx-data，如 564200")

    args = parser.parse_args()

    # --review 隐含 --minute
    if args.review:
        args.minute = True

    # 批量获取实时行情
    sina_symbols = [get_sina_symbol(code) for code in args.codes]
    realtime_cache = fetch_realtime_sina(sina_symbols)

    results = []
    for code in args.codes:
        result = analyze_stock(code, with_minute=args.minute,
                               realtime_cache=realtime_cache,
                               float_shares=args.float_shares,
                               auction_today_shares=args.auction_today_shares,
                               auction_prev_shares=args.auction_prev_shares)
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
