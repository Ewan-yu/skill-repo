#!/usr/bin/env python3
"""报告渲染模块：Report/Section/TableDef 数据结构 + 文本/Markdown 渲染"""

from dataclasses import dataclass, field


@dataclass
class TableDef:
    headers: list[str]
    rows: list[list[str]]
    aligns: list[str] = field(default_factory=list)


@dataclass
class Section:
    title: str
    body: list[str] = field(default_factory=list)
    table: TableDef | None = None


@dataclass
class Report:
    title: str = ""
    subtitle: str = ""
    sections: list[Section] = field(default_factory=list)
    summary_signals: list[str] = field(default_factory=list)
    footer_note: str = ""


# ---- 表格渲染 ----

def _text_table(t: TableDef) -> str:
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
    if not t.rows:
        return ""
    lines = ["| " + " | ".join(t.headers) + " |"]
    seps = []
    for i in range(len(t.headers)):
        a = t.aligns[i] if i < len(t.aligns) else "<"
        seps.append("---:" if a == ">" else (":---:" if a == "^" else ":---"))
    lines.append("| " + " | ".join(seps) + " |")
    for row in t.rows:
        padded = list(row) + [""] * (len(t.headers) - len(row))
        lines.append("| " + " | ".join(padded) + " |")
    return "\n".join(lines)


# ---- 报告渲染 ----

def render_report_text(report: Report) -> str:
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

    包含：今日收盘评估 + 次日操作计划（三部曲策略 + 低吸条件 + 情景预判）
    """
    body = []
    li = analysis.get("limit_info", {})
    today_lu = li.get("limit_up", False)
    today_ld = li.get("limit_down", False)
    today_status = li.get("status", "正常交易")
    vwap_val = analysis.get("vwap", 0)
    vwap_info = analysis.get("vwap_info", {})
    cs = analysis.get("composite_score", {})
    max_p = cs.get("max_partial", 75) if cs else 75
    partial = cs.get("partial_total", 0) if cs else 0
    eg = analysis.get("expectation_gap", {})

    # ---- 今日收盘评估 ----
    body.append("【今日收盘评估】")
    body.append(f"收盘状态: {today_status}")
    if vwap_val > 0:
        lbl = vwap_info.get("label", "N/A")
        body.append(f"收盘VWAP: {vwap_val:.2f}  {lbl}")
    if cs:
        scores = cs.get("scores", {})
        body.append(
            f"综合评分: {partial}/{max_p}（+趋势25分，满{max_p+25}）  "
            f"评级: {cs.get('partial_rating', '')}"
        )
        missing = cs.get("missing_data", [])
        if missing:
            body.append(f"⚠ 缺失数据: {', '.join(missing)}")

    body.append("")

    # ---- 次日操作计划 ----
    body.append("【次日操作计划】")
    body.append("")

    # 持仓者策略
    body.append("持仓者（三部曲纪律）:")
    if today_lu:
        body.append("  今日涨停 → 明日30分钟不翻红立即卖出（游资铁律，不等）")
    else:
        body.append("  今日未涨停 → 明日1小时不翻红卖出")
    body.append("  冲高超2%后回落破VWAP → 立即锁利（三部曲第二条）")
    body.append("  尾盘未涨停 → 三部曲第三条：收盘前卖出")
    if vwap_val > 0:
        body.append(f"  关键观察: VWAP {vwap_val:.2f} 是今日重要成本线")
    body.append("")

    # 未持仓者策略（低吸条件）
    body.append("未持仓者（低吸三原则）:")
    score_ok = partial / max_p >= 0.60 if max_p > 0 else False
    if score_ok:
        body.append(f"  量能评分达标({partial}/{max_p})，具备介入基础")
    else:
        body.append(f"  量能评分偏低({partial}/{max_p})，建议谨慎")
    body.append("  必须是近期热点板块（Claude判断）+ K线在5日线上方")
    body.append("  介入价位: 不超过昨收+3%，最好绿盘介入，白线在黄线上方")
    body.append("  止损位: 日内跌破VWAP立即止损，隔日跌破5日线走人")
    body.append("")

    # 次日情景预判
    body.append("次日情景预判（开盘前参考）:")
    lup = li.get("limit_up_price", 0)
    day_high = max(
        analysis.get("distribution", {}).get("open_30min", {}).get("amount", 0), 0
    )
    target_price_hint = f"涨停价 {lup:.2f}" if lup > 0 else "前期高点"
    body.append(f"  A) 竞价放量(>1.3x)+快速翻红 → 积极，目标{target_price_hint}")
    body.append("  B) 竞价平量+翻红 → 正常，关注量能是否持续放大")
    body.append("  C) 竞价缩量(<0.7x)+不翻红 → 三部曲卖出，不等待")
    body.append("")

    # 预期差提示
    if eg.get("gap_type") and eg["gap_type"] != "no_prior_signal":
        body.append(f"预期差: {eg.get('description', '')}")
        if eg.get("action_hint"):
            body.append(f"操作提示: {eg['action_hint']}")
    else:
        if today_lu:
            body.append("预期差: 今日涨停，明日有强预期，关注竞价量和开盘位置")

    return Section(title="盘后复盘 · 次日操作计划", body=body)


def _build_action_conclusion(analysis: dict) -> Section:
    """基于全部信号生成操作结论（多因素综合判断）"""
    body = []
    sell_sigs = analysis.get("sell_signals", [])
    has_strong_sell = any(s["level"] == "强" for s in sell_sigs)
    eg = analysis.get("expectation_gap", {})
    gap_type = eg.get("gap_type", "no_prior_signal")
    gap_level = eg.get("gap_level", "none")
    sp = analysis.get("support_power", {})
    support_signal = sp.get("signal", "")
    cs = analysis.get("composite_score", {})
    partial_total = cs.get("partial_total", 0) if cs else 0
    max_partial = cs.get("max_partial", 75) if cs else 75
    score_pct = partial_total / max_partial if max_partial > 0 else 0
    vwap_info = analysis.get("vwap_info", {})
    price_above_vwap = vwap_info.get("price_above_vwap", None)
    deviation = vwap_info.get("deviation_pct", 0) or 0
    shrink = analysis.get("shrink_decision", {})
    ac = analysis.get("auction_comparison", {})
    open_pct = analysis.get("open_pct", 0) or analysis.get("distribution", {}).get("open_30min", {}).get("percent", 0)
    auction_ratio = ac.get("ratio")

    # 操作倾向判断（优先级从高到低）
    if has_strong_sell:
        decision = "⚠ 立即卖出"
        decision_reason = "三部曲强卖出信号已触发"
    elif shrink.get("decision") == "立即卖出":
        decision = "⚠ 立即卖出"
        decision_reason = shrink.get("action", "缩量+黄线向下决策")
    elif score_pct >= 0.70 and price_above_vwap:
        decision = "✓ 可介入/持仓"
        decision_reason = f"综合评分{partial_total}/{max_partial}，价格在均价线上方 +{deviation:.1f}%"
    elif score_pct >= 0.55:
        decision = "◎ 观察（偏多）"
        decision_reason = "量能偏强，等白线站稳黄线后介入"
    elif score_pct >= 0.40:
        decision = "△ 观望"
        decision_reason = "量能一般，信号不明确，等待明确方向"
    else:
        decision = "✗ 不参与"
        decision_reason = f"综合评分偏低({partial_total}/{max_partial})，量能不足"

    body.append(f"操作倾向: {decision}")
    body.append(f"依据: {decision_reason}")
    body.append("")
    body.append("多方因素:")
    bullish = []
    if auction_ratio is not None and auction_ratio > 1.0:
        bullish.append(f"竞价放量({auction_ratio:.1f}x)")
    if "放量" in support_signal or "缩量回调" in support_signal:
        bullish.append(f"量价: {support_signal}")
    if open_pct >= 30:
        bullish.append(f"早盘放量({open_pct:.1f}%占比≥30%)")
    if price_above_vwap:
        bullish.append(f"价格在均价线上方(+{deviation:.1f}%)")
    if gap_type == "above_expectation":
        bullish.append("预期差: 高于预期")
    if bullish:
        for b in bullish:
            body.append(f"  + {b}")
    else:
        body.append("  （暂无明显多方因素）")

    body.append("空方因素:")
    bearish = []
    if auction_ratio is not None and auction_ratio < 0.7:
        bearish.append(f"竞价缩量({auction_ratio:.1f}x)")
    if "放量下跌" in support_signal:
        bearish.append(f"量价: {support_signal}")
    if open_pct > 0 and open_pct < 20:
        bearish.append(f"早盘严重缩量({open_pct:.1f}%)")
    if price_above_vwap is False:
        bearish.append(f"价格在均价线下方({deviation:.1f}%)")
    if gap_type == "below_expectation" and gap_level in ("moderate", "strong"):
        bearish.append(f"预期差: 低于预期({gap_level})")
    if shrink.get("is_shrink") and shrink.get("decision") != "立即卖出":
        bearish.append(f"缩量警示: {shrink.get('shrink_severity', '')}")
    if sell_sigs:
        bearish.append(f"三部曲信号({len(sell_sigs)}条)")
    if bearish:
        for b in bearish:
            body.append(f"  - {b}")
    else:
        body.append("  （暂无明显空方因素）")

    vwap_val = analysis.get("vwap", 0)
    if vwap_val > 0:
        body.append("")
        body.append(f"关键价位: VWAP均价线 {vwap_val:.2f}")
        if price_above_vwap is False:
            body.append("  → 白线须收复均价线才考虑介入")
        elif price_above_vwap:
            body.append("  → 白线在均价线上方，为持仓有利条件")

    return Section(title="操作结论", body=body)


def build_minute_report(analysis: dict, name: str, review_mode: bool = False) -> Report:
    """构建分时量能分析报告（章节按决策优先级排列）"""
    if "error" in analysis:
        return Report(
            title=f"{name} 分时分析错误",
            sections=[Section(title="错误", body=[analysis["error"]])],
        )

    sections = []

    # ——— 1. 基础数据 ———
    b1 = [
        f"分析日期: {analysis.get('today_date', 'N/A')}",
        f"全天成交: {analysis['total_volume']:,}手 ({analysis['total_amount']/10000:,.1f}万元)",
    ]
    if analysis.get("turnover_rate") is not None:
        b1.append(f"换手率: {analysis['turnover_rate']:.2f}% ({analysis['turnover_rating']})")
    # 量比（来自新浪实时行情）
    abs_vr = analysis.get("absolute_volume_ratio")
    if abs_vr is not None:
        vr_label = "放量" if abs_vr > 1.5 else ("活跃" if abs_vr > 1.0 else ("缩量" if abs_vr < 0.7 else "正常"))
        b1.append(f"量比(实时): {abs_vr:.2f}（{vr_label}）")
    if analysis.get("vwap") and analysis["vwap"] > 0:
        vi = analysis.get("vwap_info", {})
        vt = analysis.get("vwap_trend", {})
        wyb = analysis.get("white_yellow_relation", {})
        b1.append(f"均价线(VWAP): {analysis['vwap']:.2f}  走势: {vt.get('trend', 'N/A')}")
        # VWAP走势详情
        if vt.get("slope") is not None:
            range_info = f"振幅{vt.get('vwap_range_pct', 0):.1f}%" if vt.get("vwap_range_pct") else ""
            strength = vt.get("trend_strength", "")
            parts = [f"斜率{vt['slope']:+.1f}%"]
            if range_info:
                parts.append(range_info)
            if strength:
                parts.append(f"趋势{strength}")
            b1.append(f"  VWAP: {' | '.join(parts)}")
        b1.append(f"当前价 vs 均价: {vi.get('label', 'N/A')}")
        # 白黄线关系详情
        if wyb.get("description"):
            b1.append(f"白黄线关系: {wyb.get('description', 'N/A')}")
            # 补充交叉和持续信息
            cross_info = []
            if wyb.get("cross_count", 0) > 0:
                cross_info.append(f"交叉{wyb['cross_count']}次")
            if wyb.get("last_cross_time"):
                cross_info.append(f"最后交叉{wyb['last_cross_time']}({wyb['last_cross_direction']})")
            if wyb.get("current_streak", 0) > 0:
                pos_label = "上方" if wyb.get("current_position") == "above" else "下方"
                cross_info.append(f"当前连续在{pos_label}{wyb['current_streak']}个采样点")
            if cross_info:
                b1.append(f"  {' | '.join(cross_info)}")
    sections.append(Section(title="基础数据", body=b1))

    # ——— 2. 竞价量对比（决策前置） ———
    ac = analysis.get("auction_comparison", {})
    if ac.get("ratio") is not None or ac.get("today_volume", 0) > 0:
        b2 = []
        if ac.get("today_volume") is not None:
            b2.append(f"今日竞价量: {ac['today_volume']:,}手  ({ac.get('today_amount', 0)/10000:,.1f}万元)")
        if ac.get("prev_volume") is not None and ac["prev_volume"] > 0:
            b2.append(f"前日竞价量: {ac['prev_volume']:,}手  ({ac.get('prev_amount', 0)/10000:,.1f}万元)")
        if ac.get("ratio") is not None:
            b2.append(f"竞价量比: {ac['ratio']:.2f}x  [{ac['signal']}]")
        b2.append(f"研判: {ac.get('description', '')}")
        sections.append(Section(title="竞价量对比", body=b2))

    # ——— 3. 预期差信号（决策前置） ———
    eg = analysis.get("expectation_gap", {})
    if eg.get("gap_type") and eg["gap_type"] != "no_prior_signal":
        b3 = [eg.get("description", "")]
        if eg.get("action_hint"):
            b3.append(f"操作提示: {eg['action_hint']}")
        sections.append(Section(title="预期差信号", body=b3))

    # ——— 4. 承接力判断 ———
    if analysis.get("support_power"):
        sp = analysis["support_power"]
        b4 = [
            f"涨跌幅(相对昨收): {sp['price_change_pct']:+.2f}%",
            f"额比: {sp['amount_ratio']:.2f}" if sp.get("amount_ratio") is not None
            else f"量比: {sp.get('volume_ratio', 'N/A')}",
            f"信号: {sp['signal']}  →  {sp['power']}",
        ]
        sections.append(Section(title="承接力判断", body=b4))

    # ——— 5. 早盘量能预期 ———
    op = analysis["distribution"]["open_30min"]["percent"]
    b5 = []
    if analysis.get("prev_comparison") and "open_30min" in analysis["prev_comparison"]:
        ar = analysis["prev_comparison"]["open_30min"].get("amount_ratio")
        if ar is not None:
            if op > 30:
                signal, icon = ("放量抢筹 → 主力积极介入", "[看多]") if ar > 1.2 else \
                               (("正常交易 → 主力活跃", "[偏多]") if ar > 0.8 else ("控盘缩量 → 主力高度控盘", "[中性]"))
            elif op < 20:
                signal, icon = ("严重缩量 → 今日基本无戏，强烈建议观望", "[警示]") if ar < 0.7 else \
                               ("量能不足 → 参与度低，谨慎", "[看空]")
            else:
                signal, icon = ("资金后移 → 主力在其他时段积极操作", "[偏多]") if ar > 1.2 else \
                               (("量能分散 → 交易节奏正常", "[中性]") if ar > 0.8 else ("整体观望 → 资金参与度低", "[看空]"))
            b5.append(f"{icon} 早盘占比: {op:.1f}%  额比: {ar:.2f}")
            b5.append(f"判断: {signal}")
        else:
            b5.append(f"早盘占比: {op:.1f}% (无前日额比数据)")
    else:
        b5.append(f"早盘占比: {op:.1f}% (无前日对比数据)")
    sections.append(Section(title="早盘量能预期", body=b5))

    # ——— 6. 缩量决策（仅在缩量时显示） ———
    shrink = analysis.get("shrink_decision", {})
    if shrink.get("is_shrink"):
        b6 = [
            f"缩量状态: {shrink.get('shrink_severity', '')}",
            f"决策: {shrink.get('decision', '')}  [紧迫度: {shrink.get('urgency', '')}]",
            f"操作: {shrink.get('action', '')}",
        ]
        if shrink.get("reasoning"):
            b6.append(f"推导: {shrink['reasoning']}")
        sections.append(Section(title="缩量决策提示 ⚠", body=b6))

    # ——— 7. 成交分布 ———
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
        table=TableDef(headers=["时段", "量(手)", "金额(万)", "占比"],
                       rows=d_rows, aligns=["<", ">", ">", ">"]),
    ))

    # ——— 8. 同时段对比 ———
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

    # ——— 9. 卖出三部曲信号（有信号才显示） ———
    if analysis.get("sell_signals"):
        b9 = []
        for sig in analysis["sell_signals"]:
            mk = "!!" if sig["level"] == "强" else ("!" if sig["level"] == "中" else "")
            b9.append(f"[{sig['type']}]{mk} {sig['message']}")
        sections.append(Section(title="卖出三部曲信号", body=b9))

    # ——— 10. 主力动向判断 ———
    b10 = list(analysis.get("signals", [])) or ["暂无明显主力异动信号"]
    sections.append(Section(title="主力动向判断", body=b10))

    # ——— 11. 涨跌停状态（触发时显示） ———
    if analysis.get("limit_info"):
        li = analysis["limit_info"]
        if li.get("limit_up") or li.get("limit_down"):
            b11 = [f"状态: {li['status']}"]
            if li.get("limit_up_price"):
                b11.append(f"涨停价: {li['limit_up_price']:.2f}")
            if li.get("limit_down_price"):
                b11.append(f"跌停价: {li['limit_down_price']:.2f}")
            prev_lu = analysis.get("prev_limit_up")
            b11.append(f"前日是否涨停: {'是' if prev_lu else ('否' if prev_lu is False else '未知')}")
            sections.append(Section(title="涨跌停状态", body=b11))

    # ——— 12. 综合评分 ———
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
            b12.append("⚠ 以下数据缺失，对应项未计分：")
            for m in missing:
                b12.append(f"  · {m}")
        b12.append(f"（趋势分25分由Claude基于历史K线补充，总满分{max_p+25}分）")
        sections.append(Section(title="综合评分（脚本部分）", body=b12))

    # ——— 13. 操作结论（汇总判断） ———
    sections.append(_build_action_conclusion(analysis))

    # ——— 14. 放量时段 TOP 10（信息层，附录） ———
    t_rows = [
        [item["time"], f"{item['price']:.2f}", f"{item['volume']:,}", f"{item['amount']/10000:,.1f}"]
        for item in analysis.get("top_volumes", [])[:10]
    ]
    if t_rows:
        sections.append(Section(
            title="放量时段 TOP 10", body=[],
            table=TableDef(headers=["时间", "价格", "成交量(手)", "成交额(万)"],
                           rows=t_rows, aligns=["<", ">", ">", ">"]),
        ))

    # ——— 15. 盘后复盘（--review 模式） ———
    if review_mode:
        sections.append(_build_review_section(analysis))

    return Report(
        title=f"{name} 分时量能分析",
        subtitle=analysis.get("today_date", ""),
        sections=sections,
        summary_signals=_build_summary(analysis),
    )
