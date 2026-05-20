#!/usr/bin/env python3
"""指标计算模块：VWAP、竞价量、预期差、综合评分、换手率等"""


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
    """计算VWAP(成交量加权均价)，即分时图中的黄线"""
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
        return {"price_above_vwap": None, "deviation_pct": None, "label": "数据不足"}
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


def extract_auction_volume(day_data: list[dict]) -> dict:
    """提取集合竞价量（09:25 那根K线）。新浪分时数据通常不含此数据。"""
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

    数据不足时降低满分而非填充默认分，确保评分真实反映数据质量。
    趋势评分（第4维度，25分）由 Claude 基于历史K线补充。
    """
    scores = {}
    details = {}
    missing_data = []

    # --- 维度1：量能评分（最高25分）---
    vol_score = 0
    vol_max = 25

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
        vol_max -= 9
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
        vol_max -= 8
        details["竞价量比"] = "无竞价数据，此项不计分"
        missing_data.append("竞价量比（分时数据不含09:25）")

    scores["volume"] = vol_score
    scores["volume_max"] = vol_max

    # --- 维度2：承接力评分（最高25分）---
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

    # --- 维度3：预期差评分（25分）---
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
    max_partial = vol_max + acc_max + 25

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
    """对比同一时段的量能变化，以额比为主判断趋势"""
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
    return round(volume_lots * 100 / float_shares * 100, 2)


def get_turnover_rating(turnover: float) -> str:
    """换手率评级（对齐实战标准）"""
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


def get_limit_price(pre_close: float, is_st: bool = False, is_kcb_cyb: bool = False) -> tuple[float, float]:
    """计算涨停价和跌停价"""
    if is_st:
        return (round(pre_close * 1.05, 2), round(pre_close * 0.95, 2))
    elif is_kcb_cyb:
        return (round(pre_close * 1.20, 2), round(pre_close * 0.80, 2))
    else:
        return (round(pre_close * 1.10, 2), round(pre_close * 0.90, 2))


def calc_vwap_trend(trading_data: list[dict]) -> dict:
    """计算VWAP时间序列并分析黄线走势方向

    返回黄线全天走势：向上/向下/横盘/震荡，以及趋势强度和波动范围。
    """
    if not trading_data or len(trading_data) < 10:
        return {"trend": "数据不足", "slope": None, "description": "数据点不足，无法判断趋势"}

    # 计算累计VWAP序列（每隔几个点采样一次，避免过多数据）
    vwap_series = []
    total_value = 0.0
    total_vol = 0
    sample_interval = max(1, len(trading_data) // 20)  # 采样约20个点

    for i, d in enumerate(trading_data):
        vol = d["volume"]
        if vol > 0:
            total_value += d["close"] * vol
            total_vol += vol
            if total_vol > 0:
                vwap = total_value / total_vol
                if i % sample_interval == 0 or i == len(trading_data) - 1:
                    vwap_series.append({
                        "time": extract_hhmm(d["time"]),
                        "vwap": vwap,
                        "index": i,
                    })

    if len(vwap_series) < 3:
        return {"trend": "数据不足", "slope": None, "description": "有效数据点不足"}

    # 分析VWAP序列趋势
    start_vwap = vwap_series[0]["vwap"]
    end_vwap = vwap_series[-1]["vwap"]

    # 提取所有VWAP值用于计算波动范围
    vwap_values = [v["vwap"] for v in vwap_series]
    max_vwap = max(vwap_values)
    min_vwap = min(vwap_values)

    # 计算趋势斜率（%）
    price_change = end_vwap - start_vwap
    price_change_pct = (price_change / start_vwap * 100) if start_vwap > 0 else 0

    # VWAP波动范围（振幅）
    vwap_range_pct = ((max_vwap - min_vwap) / start_vwap * 100) if start_vwap > 0 else 0

    # 趋势强度：前半段vs后半段的方向一致性
    mid_idx = len(vwap_series) // 2
    first_half_slope = (vwap_series[mid_idx]["vwap"] - start_vwap) / start_vwap * 100 if start_vwap > 0 else 0
    second_half_slope = (end_vwap - vwap_series[mid_idx]["vwap"]) / vwap_series[mid_idx]["vwap"] * 100 if vwap_series[mid_idx]["vwap"] > 0 else 0
    consistent = (first_half_slope > 0 and second_half_slope > 0) or (first_half_slope < 0 and second_half_slope < 0)
    trend_strength = "一致" if consistent else "分歧"

    # 判断趋势方向
    if price_change_pct > 0.5:
        trend = "向上"
        strength_desc = "趋势一致" if consistent else "前强后弱" if first_half_slope > 0 else "后段加速"
        description = f"黄线全天向上({price_change_pct:+.1f}%)，均价成本持续上移，买方主动，{strength_desc}"
    elif price_change_pct < -0.5:
        trend = "向下"
        strength_desc = "趋势一致" if consistent else "前弱后强" if first_half_slope < 0 else "后段加速下行"
        description = f"黄线全天向下({price_change_pct:+.1f}%)，均价成本下移，卖方主动，{strength_desc}"
    else:
        if vwap_range_pct > 1.0:
            trend = "震荡"
            description = f"黄线震荡(振幅{vwap_range_pct:.1f}%)，多空激烈博弈"
        else:
            trend = "横盘"
            description = f"黄线横盘稳定(振幅{vwap_range_pct:.1f}%)，多空平衡"

    return {
        "trend": trend,
        "slope": round(price_change_pct, 2),
        "start_vwap": round(start_vwap, 2),
        "end_vwap": round(end_vwap, 2),
        "max_vwap": round(max_vwap, 2) if vwap_series else None,
        "min_vwap": round(min_vwap, 2) if vwap_series else None,
        "vwap_range_pct": round(vwap_range_pct, 2),
        "trend_strength": trend_strength,
        "description": description,
    }


def analyze_white_yellow_relation(trading_data: list[dict], vwap: float) -> dict:
    """分析白线（价格）相对黄线（运行VWAP）的动态关系

    使用逐点累计VWAP与当时价格对比（而非最终VWAP），
    正确反映全天每个时刻的多空状态。
    增强版：添加交叉次数、当前持续状态、最后交叉时间。
    """
    if not trading_data or vwap <= 0:
        return {
            "relation": "数据不足",
            "above_ratio": None,
            "below_ratio": None,
            "description": "无法分析",
        }

    above_count = 0
    below_count = 0
    total_points = 0
    running_value = 0.0
    running_vol = 0
    cross_count = 0
    last_cross_time = ""
    last_cross_direction = ""
    current_streak = 0
    current_position = ""  # "above" or "below"

    prev_above = None

    # 逐点计算运行VWAP，与当时价格对比（而非最终VWAP）
    for d in trading_data:
        vol = d["volume"]
        if vol > 0:
            running_value += d["close"] * vol
            running_vol += vol
            running_vwap = running_value / running_vol

            total_points += 1
            is_above = d["close"] > running_vwap

            if is_above:
                above_count += 1
            elif d["close"] < running_vwap:
                below_count += 1

            # 检测交叉
            if prev_above is not None and is_above != prev_above:
                cross_count += 1
                last_cross_time = extract_hhmm(d["time"])
                last_cross_direction = "上穿" if is_above else "下穿"

            # 追踪当前持续状态
            if is_above:
                if current_position == "above":
                    current_streak += 1
                else:
                    current_position = "above"
                    current_streak = 1
            elif d["close"] < running_vwap:
                if current_position == "below":
                    current_streak += 1
                else:
                    current_position = "below"
                    current_streak = 1

            prev_above = is_above

    if total_points == 0:
        return {
            "relation": "数据不足",
            "above_ratio": None,
            "below_ratio": None,
            "description": "无有效交易数据",
        }

    above_ratio = above_count / total_points * 100
    below_ratio = below_count / total_points * 100

    # 判断关系类型（基于运行VWAP时间占比）
    if above_ratio > 80:
        relation = "长时间在上方"
        description = f"白线{above_ratio:.0f}%时间在黄线上方，多头强势控盘"
    elif above_ratio > 60:
        relation = "主要在上方"
        description = f"白线{above_ratio:.0f}%时间在黄线上方，多头占优"
    elif above_ratio > 40:
        relation = "上下纠缠"
        description = f"白线在黄线上方{above_ratio:.0f}%时间，多空激烈博弈，方向待选"
    elif above_ratio > 20:
        relation = "主要在下方"
        description = f"白线{below_ratio:.0f}%时间在黄线下方，空头占优"
    else:
        relation = "长时间在下方"
        description = f"白线{below_ratio:.0f}%时间在黄线下方，空头强势压制"

    # 追加当前位置和持续信息
    current_price = trading_data[-1]["close"]
    current_above = current_price > vwap
    if current_above:
        description += "；当前价在均价线上方"
    else:
        description += "；当前价在均价线下方（弱势信号）"

    if cross_count > 0:
        description += f"；全天交叉{cross_count}次"
    if last_cross_time:
        description += f"；最后交叉{last_cross_time}({last_cross_direction})"

    return {
        "relation": relation,
        "above_ratio": round(above_ratio, 1),
        "below_ratio": round(below_ratio, 1),
        "above_count": above_count,
        "below_count": below_count,
        "total_points": total_points,
        "current_above": current_above,
        "cross_count": cross_count,
        "last_cross_time": last_cross_time,
        "last_cross_direction": last_cross_direction,
        "current_streak": current_streak,
        "current_position": current_position,
        "description": description,
    }


def build_shrink_decision(vwap_trend: str, vwap_deviation: float | None,
                          open_pct: float, period_comparisons: dict) -> dict:
    """缩量时的操作决策树（参考实战手册第七章）

    缩量 + 黄线向下 + 离支撑位远 → 立即卖出
    缩量 + 黄线横盘/震荡 + 靠近均价 → 观察企稳
    缩量 + 黄线向上            → 暂时观察，可能是洗盘
    """
    # 判断是否缩量及严重程度
    is_shrink = False
    shrink_severity = ""

    if open_pct > 0 and open_pct < 20:
        is_shrink = True
        shrink_severity = f"早盘严重缩量(占比{open_pct:.1f}%，按实战标准<20%今日基本无戏)"

    if not is_shrink and period_comparisons:
        open_comp = period_comparisons.get("open_30min", {})
        amt_ratio = open_comp.get("amount_ratio")
        if amt_ratio is not None:
            if amt_ratio < 0.7:
                is_shrink = True
                shrink_severity = f"早盘明显缩量(额比{amt_ratio:.2f}，不足前日70%)"
            elif amt_ratio < 0.9:
                is_shrink = True
                shrink_severity = f"早盘温和缩量(额比{amt_ratio:.2f})"

    if not is_shrink:
        return {
            "is_shrink": False,
            "decision": "量能正常",
            "action": "",
            "urgency": "无",
        }

    # 缩量决策树
    if vwap_trend == "向下":
        decision = "立即卖出"
        action = "缩量+黄线向下，按实战铁律应立即卖出，不等待支撑"
        urgency = "高"
    elif vwap_trend in ("横盘", "震荡"):
        if vwap_deviation is not None and abs(vwap_deviation) < 2:
            decision = "观察企稳"
            action = "缩量+黄线横盘+靠近均价，等待是否出现放量企稳"
            urgency = "中"
        else:
            decision = "谨慎观望"
            action = "缩量+黄线横盘，偏离均价较远，等待方向确认后再操作"
            urgency = "中"
    elif vwap_trend == "向上":
        decision = "暂时观察"
        action = "缩量+黄线向上，可能是主力控盘洗盘，等量能放大确认再介入"
        urgency = "低"
    else:
        decision = "谨慎观望"
        action = "趋势不明，保持观望"
        urgency = "中"

    return {
        "is_shrink": True,
        "shrink_severity": shrink_severity,
        "decision": decision,
        "action": action,
        "urgency": urgency,
        "reasoning": f"{shrink_severity} → 黄线{vwap_trend} → {decision}",
    }
