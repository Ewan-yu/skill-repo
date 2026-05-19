#!/usr/bin/env python3
"""核心分析模块：承接力、卖出三部曲、涨停检测、分时量能汇总"""

from indicators import (
    calc_period_stats, calc_vwap, calc_vwap_envelope,
    extract_auction_volume, compare_auction_volume,
    detect_expectation_gap, calc_composite_score,
    compare_same_period, calc_turnover_rate, get_turnover_rating,
    get_limit_price, split_by_day, extract_hhmm,
    calc_vwap_trend, analyze_white_yellow_relation,
    build_shrink_decision,
)


def analyze_support_power(today_data: list[dict], prev_data: list[dict],
                           pre_close: float) -> dict:
    """分析承接力（量价配合判断）

    使用 pre_close（昨收）作为价格变动基准。
    """
    if not today_data:
        return {"price_change_pct": 0, "volume_ratio": 0,
                "signal": "数据不足", "power": "无法判断"}

    current_price = today_data[-1]["close"]
    today_price_change = (current_price - pre_close) / pre_close * 100

    if not prev_data:
        return {
            "price_change_pct": round(today_price_change, 2),
            "volume_ratio": None,
            "signal": "上涨" if today_price_change > 0 else ("下跌" if today_price_change < 0 else "横盘"),
            "power": "仅基于价格变动判断，无前日量比参考",
        }

    today_total_vol = sum(d["volume"] for d in today_data if d["volume"] > 0)
    today_end_time = extract_hhmm(today_data[-1]["time"])
    prev_same_period = [
        d for d in prev_data
        if extract_hhmm(d["time"]) <= today_end_time and d["volume"] > 0
    ]
    prev_total_vol = sum(d["volume"] for d in prev_same_period) if prev_same_period else 0
    prev_total_amt = sum(d["amount"] for d in prev_same_period) if prev_same_period else 0
    today_total_amt = sum(d["amount"] for d in today_data if d["volume"] > 0)

    amt_ratio = today_total_amt / prev_total_amt if prev_total_amt > 0 else None
    vol_ratio = today_total_vol / prev_total_vol if prev_total_vol > 0 else None
    primary_ratio = amt_ratio if amt_ratio is not None else (vol_ratio if vol_ratio is not None else 0)

    if today_price_change < -0.5:
        if primary_ratio < 0.8:
            signal, power = "缩量回调", "承接力强（主力护盘，散户惜售不抛）"
        elif primary_ratio > 1.2:
            signal, power = "放量下跌", "承接力弱（主力出货，恐慌抛售）"
        else:
            signal, power = "平量回调", "承接力一般（关注支撑位）"
    elif today_price_change < 0:
        signal, power = "微跌", "回调幅度小，承接力尚可"
    elif today_price_change > 0.5:
        if primary_ratio > 1.2:
            signal, power = "放量上涨", "量价配合好（主力积极做多）"
        elif primary_ratio < 0.8 and primary_ratio > 0:
            signal, power = "缩量上涨", "量价背离（主力控盘锁仓或散户推动，关注持续性）"
        else:
            signal, power = "平量上涨", "量价正常，趋势健康"
    elif today_price_change > 0:
        signal, power = "微涨", "涨幅较小，量价正常"
    else:
        signal, power = "横盘整理", "多空平衡，等待方向选择"

    return {
        "price_change_pct": round(today_price_change, 2),
        "volume_ratio": round(vol_ratio, 2) if vol_ratio is not None else None,
        "amount_ratio": round(amt_ratio, 2) if amt_ratio is not None else None,
        "signal": signal,
        "power": power,
    }


def build_sell_signals(trading_data: list[dict], pre_close: float,
                       vwap: float, prev_limit_up: bool = None) -> list[dict]:
    """基于卖出三部曲生成卖出/持仓信号

    1. 前日涨停股: 开盘30分钟不红盘 → 卖出
    2. 前日未涨停股: 开盘1小时不红盘 → 卖出
    3. 冲高回落破VWAP → 卖出
    4. 尾盘不涨停 → 卖出
    """
    signals = []
    if not trading_data:
        return signals

    current_price = trading_data[-1]["close"]
    is_red = current_price > pre_close
    current_time_str = extract_hhmm(trading_data[-1]["time"])
    day_high = max(d["close"] for d in trading_data)
    max_gain_pct = (day_high - pre_close) / pre_close * 100

    if current_time_str >= "10:00":
        if prev_limit_up is True:
            if not is_red:
                signals.append({"type": "卖出信号", "level": "强",
                                 "message": "前日涨停+开盘30分钟不红盘，按三部曲应卖出"})
                signals.append({"type": "参考", "level": "中",
                                 "message": "前日涨停股开盘半小时不红盘即走，是游资铁律"})
        elif prev_limit_up is False:
            if not is_red and current_time_str >= "10:30":
                signals.append({"type": "卖出信号", "level": "中",
                                 "message": "前日未涨停+开盘1小时不红盘，按三部曲应卖出"})

    if vwap > 0 and max_gain_pct > 2:
        if current_price < vwap:
            signals.append({"type": "卖出信号", "level": "强",
                             "message": f"盘中最高涨{max_gain_pct:.1f}%后回落破均价线，按三部曲应卖出(锁利)"})

    if current_time_str >= "14:50":
        limit_up_price = round(pre_close * 1.10, 2)
        if current_price < limit_up_price:
            signals.append({"type": "持仓建议", "level": "中",
                             "message": "尾盘未涨停，按三部曲应考虑卖出(除非红盘且趋势向好)"})

    if vwap > 0:
        deviation = (current_price - vwap) / vwap * 100
        if deviation > 3:
            signals.append({"type": "风控提醒", "level": "中",
                             "message": f"价格高出均价线{deviation:.1f}%，建议卖出部分锁利"})

    return signals


def detect_limit_status(price: float, pre_close: float, code: str = "") -> dict:
    """检测涨停/跌停状态（基于昨收价正确计算）"""
    if pre_close <= 0:
        return {"status": "未知", "limit_up": False, "limit_down": False}

    is_kcb_cyb = code.startswith(("68", "30"))
    is_st = "ST" in code or "*ST" in code

    limit_up, limit_down = get_limit_price(pre_close, is_st, is_kcb_cyb)
    tolerance = 0.01

    is_limit_up = abs(price - limit_up) <= tolerance
    is_limit_down = abs(price - limit_down) <= tolerance

    return {
        "status": "涨停" if is_limit_up else ("跌停" if is_limit_down else "正常交易"),
        "limit_up": is_limit_up,
        "limit_down": is_limit_down,
        "limit_up_price": limit_up,
        "limit_down_price": limit_down,
    }


def detect_prev_limit_up(prev_data: list[dict], pre_close: float, code: str = "") -> bool:
    """判断前一日是否涨停"""
    if not prev_data or len(prev_data) < 10:
        return False

    # 科创板(68开头)和创业板(30开头)涨跌幅限制20%，涨停阈值18%
    change_threshold = 18.0 if (code.startswith("68") or code.startswith("30")) else 9.0

    trading_prev = [d for d in prev_data
                    if "09:30" <= extract_hhmm(d["time"]) <= "15:00"
                    and d["volume"] > 0]

    if not trading_prev:
        return False

    prev_close_price = trading_prev[-1]["close"]
    prev_high = max(d["high"] for d in trading_prev)
    prev_low = min(d["low"] for d in trading_prev)
    close_near_high = abs(prev_close_price - prev_high) <= 0.01

    if prev_low > 0:
        day_range = (prev_high - prev_low) / prev_low * 100
        if day_range < 1.5 and close_near_high:
            return True

    prev_open = trading_prev[0]["open"]
    if prev_open > 0:
        prev_change = (prev_close_price - prev_open) / prev_open * 100
        if prev_change > change_threshold and close_near_high:
            return True

    return False


def analyze_minute_volume(minute_data: list[dict], float_shares: int = 0,
                           pre_close: float = None, code: str = "",
                           auction_today_shares: int = 0,
                           auction_prev_shares: int = 0) -> dict:
    """分析分时量能，返回完整分析结果字典"""
    if not minute_data:
        return {"error": "无分时数据"}

    days = split_by_day(minute_data)
    sorted_dates = sorted(days.keys())

    if len(sorted_dates) < 1:
        return {"error": "无有效交易日数据"}

    today_date = sorted_dates[-1]
    today_data = days[today_date]

    # 集合竞价量：优先使用外部传入（来自 mx-data），否则尝试从分时数据提取
    if auction_today_shares > 0:
        today_auction = {"volume": auction_today_shares // 100, "amount": 0.0, "price": 0.0, "found": True}
    else:
        today_auction = extract_auction_volume(today_data)

    trading_data = [
        d for d in today_data
        if d["volume"] > 0 and "09:30" <= extract_hhmm(d["time"]) <= "15:00"
    ]

    if not trading_data:
        return {"error": "无有效交易数据(今日尚未开盘或数据缺失)"}

    total_vol = sum(d["volume"] for d in trading_data)
    total_amt = sum(d["amount"] for d in trading_data)

    def period_stats(start: str, end: str) -> dict:
        return calc_period_stats(trading_data, start, end)

    open_30 = period_stats("09:30", "10:00")
    mid_am = period_stats("10:00", "11:30")
    mid_pm = period_stats("13:00", "14:30")
    close_30 = period_stats("14:30", "15:01")

    vwap = calc_vwap(trading_data)
    current_price = trading_data[-1]["close"] if trading_data else 0
    vwap_info = calc_vwap_envelope(current_price, vwap)

    # VWAP趋势分析（黄线走势+白黄线关系）
    vwap_trend = calc_vwap_trend(trading_data)
    white_yellow_rel = analyze_white_yellow_relation(trading_data, vwap)

    prev_data_1 = None
    prev_data_2 = None
    prev_date_1 = None
    if len(sorted_dates) >= 2:
        prev_date_1 = sorted_dates[-2]
        prev_data_1 = days[prev_date_1]
    if len(sorted_dates) >= 3:
        prev_data_2 = days[sorted_dates[-3]]

    if auction_prev_shares > 0:
        prev_auction = {"volume": auction_prev_shares // 100, "amount": 0.0, "price": 0.0, "found": True}
    else:
        prev_auction = extract_auction_volume(prev_data_1) if prev_data_1 else {
            "found": False, "volume": 0, "amount": 0.0, "price": 0.0
        }

    prev_limit_up = None
    if prev_data_1:
        prev_limit_up = detect_prev_limit_up(prev_data_1, pre_close, code)

    # 同时段对比
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
                prev_open, prev_mid_am, prev_mid_pm, prev_close = p1_open, p1_mid_am, p1_mid_pm, p1_close
                comparison_base = prev_date_1
        else:
            prev_open, prev_mid_am, prev_mid_pm, prev_close = p1_open, p1_mid_am, p1_mid_pm, p1_close
            comparison_base = prev_date_1

        prev_comparison = {
            "open_30min": compare_same_period(open_30, prev_open, "早盘30分"),
            "mid_am": compare_same_period(mid_am, prev_mid_am, "上午中段"),
            "mid_pm": compare_same_period(mid_pm, prev_mid_pm, "下午中段"),
            "close_30min": compare_same_period(close_30, prev_close, "尾盘30分"),
            "prev_date": comparison_base,
        }

    auction_comparison = compare_auction_volume(today_auction, prev_auction)

    today_open_price = trading_data[0]["open"] if trading_data else 0.0
    expectation_gap = detect_expectation_gap(
        prev_limit_up=prev_limit_up,
        today_open=today_open_price,
        pre_close=pre_close or 0.0,
        auction_comparison=auction_comparison,
    )

    # 主力动向信号
    signals = []
    if total_vol > 0:
        if close_30["volume"] / total_vol > 0.25:
            signals.append("尾盘大幅放量(>25%)，可能有主力抢筹或出货")
        elif close_30["volume"] / total_vol > 0.15:
            signals.append("尾盘有一定放量(15-25%)")

        open_ratio = open_30["volume"] / total_vol
        open_amt_ratio = None
        if prev_comparison and "open_30min" in prev_comparison:
            open_amt_ratio = prev_comparison["open_30min"].get("amount_ratio")

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
            signals.append("早盘成交占比<20%(缩量明显)，今日基本无戏，建议观望")

    # 涨停/跌停检测
    if pre_close and pre_close > 0:
        limit_info = detect_limit_status(current_price, pre_close, code)
        if limit_info["limit_up"]:
            signals.append("涨停封板中，关注封单量和开板风险")
        elif limit_info["limit_down"]:
            signals.append("跌停封板中，不宜抄底")
    else:
        limit_info = {"status": "无法判断", "limit_up": False, "limit_down": False}

    # 承接力分析
    if pre_close and pre_close > 0:
        support_power = analyze_support_power(trading_data, prev_data_1, pre_close)
    else:
        support_power = {"price_change_pct": 0, "volume_ratio": None,
                         "signal": "无昨收数据", "power": "无法判断"}

    # 卖出三部曲信号
    sell_signals = []
    if pre_close and pre_close > 0:
        sell_signals = build_sell_signals(trading_data, pre_close, vwap, prev_limit_up)

    # 综合评分
    _open_pct = round(open_30["volume"] / total_vol * 100, 1) if total_vol else 0
    _open_amt_ratio = None
    if prev_comparison and "open_30min" in prev_comparison:
        _open_amt_ratio = prev_comparison["open_30min"].get("amount_ratio")
    composite_score = calc_composite_score(
        open_pct=_open_pct,
        open_amt_ratio=_open_amt_ratio,
        auction_ratio=auction_comparison.get("ratio"),
        support_signal=support_power.get("signal", ""),
        vwap_deviation=vwap_info.get("deviation_pct"),
        all_amt_ratio=support_power.get("amount_ratio"),
        gap_type=expectation_gap.get("gap_type", "no_prior_signal"),
        gap_level=expectation_gap.get("gap_level", "none"),
    )

    # 换手率
    turnover_rate = None
    turnover_rating = None
    if float_shares > 0:
        turnover_rate = calc_turnover_rate(total_vol // 100, float_shares)
        turnover_rating = get_turnover_rating(turnover_rate)

    # 放量时段 TOP 10
    top_volumes = [
        {
            "time": d["time"][-8:],
            "price": d["close"],
            "volume": d["volume"] // 100,
            "amount": d["amount"],
        }
        for d in sorted(trading_data, key=lambda x: x["volume"], reverse=True)[:10]
    ]

    return {
        "today_date": today_date,
        "total_volume": total_vol // 100,
        "total_amount": total_amt,
        "current_price": current_price,
        "distribution": {
            "open_30min": {"volume": open_30["volume_lots"], "amount": open_30["amount"],
                           "percent": round(open_30["volume"] / total_vol * 100, 1) if total_vol else 0},
            "mid_am": {"volume": mid_am["volume_lots"], "amount": mid_am["amount"],
                       "percent": round(mid_am["volume"] / total_vol * 100, 1) if total_vol else 0},
            "mid_pm": {"volume": mid_pm["volume_lots"], "amount": mid_pm["amount"],
                       "percent": round(mid_pm["volume"] / total_vol * 100, 1) if total_vol else 0},
            "close_30min": {"volume": close_30["volume_lots"], "amount": close_30["amount"],
                            "percent": round(close_30["volume"] / total_vol * 100, 1) if total_vol else 0},
        },
        "prev_comparison": prev_comparison,
        "top_volumes": top_volumes,
        "signals": signals,
        "support_power": support_power,
        "turnover_rate": turnover_rate,
        "turnover_rating": turnover_rating,
        "vwap": round(vwap, 2),
        "vwap_info": vwap_info,
        "vwap_trend": vwap_trend,
        "white_yellow_relation": white_yellow_rel,
        "limit_info": limit_info,
        "prev_limit_up": prev_limit_up,
        "sell_signals": sell_signals,
        "auction_comparison": auction_comparison,
        "expectation_gap": expectation_gap,
        "composite_score": composite_score,
        "open_pct": _open_pct,
        "shrink_decision": build_shrink_decision(
            vwap_trend=vwap_trend.get("trend", ""),
            vwap_deviation=vwap_info.get("deviation_pct"),
            open_pct=_open_pct,
            period_comparisons=prev_comparison,
        ),
    }
