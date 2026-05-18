#!/usr/bin/env python3
"""数据获取模块：新浪财经实时行情 + 分时K线"""

import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, time

_MAX_RESPONSE_BYTES = 2 * 1024 * 1024  # 2 MB
_STOCK_CODE_RE = re.compile(r'^\d{6}$')


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
                "volume_ratio": volume_ratio,
                "data_status": market_status,
                "data_note": data_note,
            }

    except Exception as e:
        print(f"新浪实时接口错误: {e}", file=sys.stderr)

    return result


def fetch_minute_data_sina(symbol: str, count: int = 500) -> list[dict]:
    """从新浪获取分时K线数据（默认500条覆盖2-3个交易日）"""
    encoded_symbol = urllib.parse.quote(symbol, safe="")
    url = (
        f"https://quotes.sina.cn/cn/api/jsonp_v2.php/var%20_{encoded_symbol}="
        f"/CN_MarketDataService.getKLineData?symbol={encoded_symbol}&scale=1&ma=no&datalen={count}"
    )

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
        return [
            {
                "time": item["day"],
                "open": float(item["open"]),
                "high": float(item["high"]),
                "low": float(item["low"]),
                "close": float(item["close"]),
                "volume": int(item["volume"]),
                "amount": float(item["amount"]),
            }
            for item in data
        ]

    except Exception as e:
        print(f"新浪分时接口错误: {e}", file=sys.stderr)

    return []
