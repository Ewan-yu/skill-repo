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
    """构建盘后复盘数据章节（--review 模式专用）"""
    body = []

    dist = analysis.get("distribution", {})
    open_pct = dist.get("open_30min", {}).get("percent", 0)
    close_pct = dist.get("close_30min", {}).get("percent", 0)
    body.append(f"早盘占比: {open_pct:.1f}%  尾盘占比: {close_pct:.1f}%")

    ac = analysis.get("auction_comparison", {})
    if ac.get("ratio") is not None:
        body.append(f"竞价量比: {ac['ratio']:.2f}x  [{ac['signal']}]")
    elif ac.get("today_volume", 0) > 0:
        body.append(f"竞价量: {ac['today_volume']:,}手（无前日对比）")

    li = analysis.get("limit_info", {})
    body.append(f"今日收盘状态: {li.get('status', '正常交易')}")

    prev_lu = analysis.get("prev_limit_up")
    today_lu = li.get("limit_up", False)
    body.append(f"今日是否涨停: {'是 → 次日三部曲：30分钟不翻红卖出' if today_lu else '否 → 次日三部曲：1小时不翻红卖出'}")
    body.append(f"前日是否涨停: {'是' if prev_lu else ('否' if prev_lu is False else '未知')}")

    eg = analysis.get("expectation_gap", {})
    body.append("")
    body.append(f"[预期差] {eg.get('description', '无数据')}")
    if eg.get("action_hint"):
        body.append(f"操作提示: {eg['action_hint']}")

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

    sell_sigs = analysis.get("sell_signals", [])
    if sell_sigs:
        body.append("")
        body.append("[三部曲信号]")
        for s in sell_sigs:
            mk = "!!" if s["level"] == "强" else "!"
            body.append(f"  {mk} {s['message']}")

    vwap = analysis.get("vwap", 0)
    if vwap > 0:
        body.append("")
        body.append(f"[关键价位] VWAP均价线: {vwap:.2f}（次日跌破此位需警惕）")

    return Section(title="盘后复盘数据（次日操作参考）", body=body)


def build_minute_report(analysis: dict, name: str, review_mode: bool = False) -> Report:
    """构建分时量能分析报告（章节固定有序）"""
    if "error" in analysis:
        return Report(
            title=f"{name} 分时分析错误",
            sections=[Section(title="错误", body=[analysis["error"]])],
        )

    sections = []

    # 1. 基础数据
    b1 = [
        f"分析日期: {analysis.get('today_date', 'N/A')}",
        f"全天成交: {analysis['total_volume']:,}手 ({analysis['total_amount']/10000:,.1f}万元)",
    ]
    if analysis.get("turnover_rate") is not None:
        b1.append(f"换手率: {analysis['turnover_rate']:.2f}% ({analysis['turnover_rating']})")
    if analysis.get("vwap") and analysis["vwap"] > 0:
        vi = analysis.get("vwap_info", {})
        vt = analysis.get("vwap_trend", {})
        wyb = analysis.get("white_yellow_relation", {})
        b1.append(f"均价线(VWAP): {analysis['vwap']:.2f} | 走势: {vt.get('trend', 'N/A')}")
        b1.append(f"当前价 vs 均价: {vi.get('label', 'N/A')}")
        if wyb.get("description"):
            b1.append(f"白黄线关系: {wyb.get('description', 'N/A')}")
    sections.append(Section(title="基础数据", body=b1))

    # 2. 成交分布
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

    # 3. 同时段对比
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

    # 4. 承接力判断
    if analysis.get("support_power"):
        sp = analysis["support_power"]
        b4 = [
            f"涨跌幅(相对昨收): {sp['price_change_pct']:+.2f}%",
            f"额比: {sp['amount_ratio']:.2f}" if sp.get("amount_ratio") is not None
            else f"量比: {sp.get('volume_ratio', 'N/A')}",
            f"信号: **{sp['signal']}**  →  {sp['power']}",
        ]
        sections.append(Section(title="承接力判断", body=b4))

    # 5. 早盘量能预期
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

    # 6. 放量时段 TOP 10
    t_rows = [
        [item["time"], f"{item['price']:.2f}", f"{item['volume']:,}", f"{item['amount']/10000:,.1f}"]
        for item in analysis.get("top_volumes", [])[:10]
    ]
    sections.append(Section(
        title="放量时段 TOP 10", body=[],
        table=TableDef(headers=["时间", "价格", "成交量(手)", "成交额(万)"],
                       rows=t_rows, aligns=["<", ">", ">", ">"]),
    ))

    # 7. 主力动向判断
    b7 = list(analysis.get("signals", [])) or ["暂无明显主力异动信号"]
    sections.append(Section(title="主力动向判断", body=b7))

    # 8. 卖出三部曲信号
    if analysis.get("sell_signals"):
        b8 = []
        for sig in analysis["sell_signals"]:
            mk = "!!" if sig["level"] == "强" else ("!" if sig["level"] == "中" else "")
            b8.append(f"[{sig['type']}]{mk} {sig['message']}")
        sections.append(Section(title="卖出三部曲信号", body=b8))

    # 9. 涨跌停状态
    if analysis.get("limit_info"):
        li = analysis["limit_info"]
        if li.get("limit_up") or li.get("limit_down"):
            b9 = [f"状态: {li['status']}"]
            if li.get("limit_up_price"):
                b9.append(f"涨停价: {li['limit_up_price']:.2f}")
            if li.get("limit_down_price"):
                b9.append(f"跌停价: {li['limit_down_price']:.2f}")
            sections.append(Section(title="涨跌停状态", body=b9))

    # 10. 竞价量对比
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

    # 11. 预期差信号
    eg = analysis.get("expectation_gap", {})
    if eg.get("gap_type") and eg["gap_type"] != "no_prior_signal":
        b11 = [eg.get("description", "")]
        if eg.get("action_hint"):
            b11.append(f"操作提示: {eg['action_hint']}")
        sections.append(Section(title="预期差信号", body=b11))

    # 12. 综合评分
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

    # 13. 盘后复盘数据（--review 模式）
    if review_mode:
        sections.append(_build_review_section(analysis))

    return Report(
        title=f"{name} 分时量能分析",
        subtitle=analysis.get("today_date", ""),
        sections=sections,
        summary_signals=_build_summary(analysis),
    )
