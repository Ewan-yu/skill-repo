#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""走势图绘制算法 v7 - 盒绘字符平滑曲线

参考样式:
  78 ┤                  ╭─╮
  77 ┤               ╭──╯  ╰╮
  76 ┤            ╭──╯       ╰╮
  75 ┤         ╭──╯            ╰╮
  74 ┤        ╭╯                 ╰╮
  73 ┤       ╭╯                   ╰──●  ← 现价 73.90
     └──────────────────────────────────
      04/20  04/27  05/06  05/12  05/18

绘制策略:
1. 连接线: 只画中间段 (─水平, │垂直)
2. 数据点: 根据incoming方向选择 ╮(峰) ╰(谷) o(平)
3. 点字符覆盖连接线，确保转折点清晰
"""

from typing import List, Dict


def _simplify(klines: List[Dict], max_points: int = 12) -> List[Dict]:
    """简化数据：保留关键转折点，控制总点数"""
    if len(klines) <= max_points:
        return klines[:]

    prices = [k['close'] for k in klines]
    price_range = max(prices) - min(prices)
    threshold = price_range * 0.10

    key_indices = [0]
    for i in range(1, len(klines) - 1):
        if abs(prices[i] - prices[key_indices[-1]]) >= threshold:
            key_indices.append(i)

    if key_indices[-1] != len(klines) - 1:
        key_indices.append(len(klines) - 1)

    if len(key_indices) > max_points:
        step = (len(key_indices) - 1) / (max_points - 1)
        sampled = [key_indices[0]]
        for j in range(1, max_points - 1):
            idx = min(int(j * step), len(key_indices) - 1)
            sampled.append(key_indices[idx])
        sampled.append(key_indices[-1])
        key_indices = sampled

    return [klines[i] for i in key_indices]


def _render_smooth(data: List[Dict], current_price: float) -> str:
    if not data:
        return "无数据"

    if len(data) == 1:
        return f"  {data[0]['close']:6.2f} ┤●  ← 现价 {current_price:.2f}"

    prices = [k['close'] for k in data]
    min_p = min(prices)
    max_p = max(prices)
    price_range = max_p - min_p

    if price_range < 2:
        num_rows = 10
    elif price_range < 5:
        num_rows = 12
    elif price_range < 10:
        num_rows = 16
    else:
        num_rows = min(20, int(price_range * 1.2) + 6)

    price_step = price_range / (num_rows - 1) if num_rows > 1 else 1
    y_ticks = [round(max_p - i * price_step, 2) for i in range(num_rows)]

    point_rows = []
    for p in prices:
        best = min(range(num_rows), key=lambda r: abs(y_ticks[r] - p))
        point_rows.append(best)

    N = len(data)
    spacing = 2
    x_pos = [i * spacing for i in range(N)]
    total_cols = x_pos[-1] + 1

    grid = [[' ' for _ in range(total_cols)] for _ in range(num_rows)]

    # ═══ 第一层：连接线（只画中间段）═══
    for i in range(N - 1):
        c1, c2 = x_pos[i], x_pos[i + 1]
        r1, r2 = point_rows[i], point_rows[i + 1]

        if c2 - c1 <= 1:
            continue

        if r1 == r2:
            for col in range(c1 + 1, c2):
                grid[r1][col] = '─'
        elif r1 > r2:
            # 上涨: 水平段在 r1, 垂直段在 c2-1
            for col in range(c1 + 1, c2):
                grid[r1][col] = '─'
            for row in range(r2 + 1, r1):
                grid[row][c2 - 1] = '│'
        else:
            # 下跌: 水平段在 r1, 垂直段在 c2-1
            for col in range(c1 + 1, c2):
                grid[r1][col] = '─'
            for row in range(r1 + 1, r2):
                grid[row][c2 - 1] = '│'

    # ═══ 第二层：数据点字符（覆盖连接线）═══
    # 根据incoming方向:
    #   前一段价格↑(prev_row > cur_row) → 这是峰 → ╮
    #   前一段价格↓(prev_row < cur_row) → 这是谷 → ╰
    #   前一段持平 → o
    for i in range(N):
        x, y = x_pos[i], point_rows[i]

        if i == N - 1:
            grid[y][x] = '●'
        elif i == 0:
            grid[y][x] = 'o'
        else:
            prev_row = point_rows[i - 1]
            if prev_row == y:
                grid[y][x] = 'o'
            elif prev_row > y:
                # prev_row更高(行号大=价格低) → 前一段下跌 → 谷 → ╰
                grid[y][x] = '╰'
            else:
                # prev_row更低(行号小=价格高) → 前一段上涨 → 峰 → ╮
                grid[y][x] = '╮'

    # ═══ 输出 ═══
    output = []
    last_row = point_rows[-1]
    for row_idx in range(num_rows):
        line = f"{y_ticks[row_idx]:6.2f} ┤"
        line += ''.join(grid[row_idx])
        if row_idx == last_row:
            line += f"  ← 现价 {current_price:.2f}"
        output.append(line)

    output.append("       " + "─" * (total_cols + 1))

    num_dates = min(5, N)
    date_positions = []
    for i in range(num_dates):
        idx = int(i * (N - 1) / (num_dates - 1)) if num_dates > 1 else 0
        date_str = data[idx]['date'][5:10].replace('-', '/')
        date_x = x_pos[idx]
        date_positions.append((date_x, date_str))

    date_line = "       "
    col = 0
    for dx, ds in date_positions:
        while col < dx:
            date_line += " "
            col += 1
        date_line += ds
        col += len(ds)

    output.append(date_line)
    return "\n".join(output)


def render_chart(klines: List[Dict], current_price: float) -> str:
    """渲染走势图（入口函数）"""
    if not klines:
        return "无数据"

    data = _simplify(klines, max_points=12)
    return _render_smooth(data, current_price)


if __name__ == "__main__":
    klines = [
        {'date': '2026-04-01', 'close': 50.06},
        {'date': '2026-04-07', 'close': 45.38},
        {'date': '2026-04-14', 'close': 50.00},
        {'date': '2026-04-20', 'close': 60.28},
        {'date': '2026-04-23', 'close': 64.33},
        {'date': '2026-04-24', 'close': 57.90},
        {'date': '2026-04-30', 'close': 63.51},
        {'date': '2026-05-07', 'close': 73.47},
        {'date': '2026-05-11', 'close': 75.44},
        {'date': '2026-05-14', 'close': 69.00},
        {'date': '2026-05-19', 'close': 68.24},
    ]
    print(render_chart(klines, 68.24))
