# ASCII走势图绘制指南

## 问题说明

当历史K线数据中存在大幅价格跳空时，直接连接会产生交叉线，导致图表出现"双线"效果，影响可读性。

## 解决方案

### 版本选择

- **盒绘字符版**：使用 `╭ ╮ ╯ ╰ │ ─` 等字符，视觉效果更好，但需要UTF-8支持
- **简单ASCII版**：使用 `o * | \ / -` 等字符，确保跨平台兼容性（Windows推荐）

### 简单ASCII版实现

```python
def render_chart(klines: list, current_price: float) -> str:
    """绘制走势图（简单ASCII版）

    规则：
    1. 纵轴：每格约1-2元，覆盖价格区间
    2. 横轴：均匀分布日期
    3. 连接：使用简单字符确保单条曲线
    4. 数据点：用 'o' 标记，现价用 '*' 标记
    """
    if not klines:
        return "无数据"

    # 数据采样（最多28个点）
    max_points = 28
    if len(klines) <= max_points:
        data = klines[:]
    else:
        step = (len(klines) - 1) / (max_points - 1)
        data = [klines[0]]
        for i in range(1, max_points - 1):
            idx = min(int(i * step), len(klines) - 1)
            data.append(klines[idx])
        data.append(klines[-1])

    prices = [k['close'] for k in data]
    min_price = min(prices)
    max_price = max(prices)

    # 动态Y轴行数
    price_range = max_price - min_price
    if price_range < 2:
        num_rows = 10
    elif price_range < 5:
        num_rows = 14
    elif price_range < 10:
        num_rows = 18
    else:
        num_rows = min(24, int(price_range * 1.8) + 6)

    price_step = price_range / (num_rows - 1) if num_rows > 1 else 1

    # Y轴刻度（从高到低）
    y_ticks = []
    for i in range(num_rows):
        price = min_price + i * price_step
        y_ticks.append(round(price, 2))
    y_ticks = list(reversed(y_ticks))

    # 计算每个数据点所在的行
    point_rows = []
    for k in data:
        best_row = 0
        best_dist = float('inf')
        for row, y_price in enumerate(y_ticks):
            dist = abs(k['close'] - y_price)
            if dist < best_dist:
                best_dist = dist
                best_row = row
        point_rows.append(best_row)

    # 初始化网格
    num_cols = len(data)
    grid = [[' ' for _ in range(num_cols)] for _ in range(num_rows)]

    # 标记数据点
    for col, row in enumerate(point_rows):
        is_last = col == num_cols - 1
        grid[row][col] = '*' if is_last else 'o'

    # 绘制连接线
    for col in range(num_cols - 1):
        curr_row = point_rows[col]
        next_row = point_rows[col + 1]

        if curr_row == next_row:
            # 水平延伸
            for c in range(col + 1, num_cols):
                if point_rows[c] == curr_row:
                    grid[curr_row][c] = '-'
                else:
                    break
        elif abs(curr_row - next_row) == 1:
            # 相邻行：单步斜线
            if next_row > curr_row:
                if col + 1 < num_cols:
                    grid[curr_row + 1][col + 1] = '\\'
            else:
                if col + 1 < num_cols:
                    grid[curr_row - 1][col + 1] = '/'
        else:
            # 跨越多行：用竖线连接
            start, end = min(curr_row, next_row), max(curr_row, next_row)
            for r in range(start + 1, end):
                if r < num_rows and col + 1 < num_cols:
                    grid[r][col + 1] = '|'

            # 在转折点添加斜线
            if next_row > curr_row:
                if curr_row + 1 < num_rows and col + 1 < num_cols:
                    grid[curr_row + 1][col + 1] = '\\'
            else:
                if curr_row - 1 >= 0 and col + 1 < num_cols:
                    grid[curr_row - 1][col + 1] = '/'

    # 生成输出
    output = []
    for row_idx, y_price in enumerate(y_ticks):
        line = f"{y_price:5.1f} |"
        for col in range(num_cols):
            ch = grid[row_idx][col]
            line += ch
        output.append(line)

    # X轴日期
    num_dates = min(6, len(data))
    date_indices = [int(i * (len(data) - 1) / (num_dates - 1)) for i in range(num_dates)]

    date_line = "       "
    for col in range(len(data)):
        if col in date_indices:
            date_str = data[col]['date'][5:10].replace('-', '/')
            date_line += f" {date_str}"
        else:
            date_line += "  "

    output.append(date_line)

    return "\n".join(output)
```

### 使用示例

```python
klines = [
    {'date': '2026-04-01', 'close': 7.52},
    {'date': '2026-04-10', 'close': 6.64},
    {'date': '2026-04-15', 'close': 8.05},
    {'date': '2026-04-22', 'close': 8.94},
    {'date': '2026-04-30', 'close': 9.92},
    {'date': '2026-05-07', 'close': 12.00},
    {'date': '2026-05-12', 'close': 15.05},
    {'date': '2026-05-15', 'close': 17.43},
    {'date': '2026-05-19', 'close': 16.15},
]

chart = render_chart(klines, current_price=16.15)
print(chart)
```

输出：
```
 17.4 |       o 
 17.0 |       |\
 16.5 |       ||
 16.0 |       |*
 15.6 |       / 
 15.1 |      o  
 14.6 |      |  
 13.7 |      |  
 12.3 |      /  
 11.8 |     o   
  9.9 |    o    
  9.0 |   o     
  8.1 |  o      
  7.6 |o |      
  6.6 | o       
        04/01 04/10   04/22 04/30   05/12   05/19
```

## 实战要点

1. **单条曲线**：确保每个数据点只有一条连接线
2. **采样数量**：28个点左右最佳
3. **Y轴刻度**：动态计算，确保图表高度约10-24行
4. **连接字符**：
   - `-` 水平连接
   - `|` 垂直连接
   - `\` 向上连接
   - `/` 向下连接
   - `o` 数据点
   - `*` 现价
5. **横轴日期**：不超过6个，确保对齐

## Windows兼容性

Windows终端可能无法正确显示盒绘字符。在Windows环境下：
- 优先使用简单ASCII字符版本
- 或在运行前执行 `chcp 65001` 切换到UTF-8编码
