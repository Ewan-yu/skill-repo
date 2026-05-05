# 数据获取指南

本文档详细说明如何使用**妙想 Skills**（基于东方财富实时数据）和 cn-financial MCP 工具获取 A 股公司财务数据。

## 核心原则

**🔥 妙想Skills是首选数据源**

所有数据获取**优先使用妙想Skills**，原因：
- ✅ 基于东方财富权威数据源
- ✅ 数据实时更新，覆盖全面
- ✅ 自然语言查询，快速便捷
- ✅ 包含最新资讯、行业景气度、研报等综合信息

---

## Windows 用户注意事项

### 解决控制台乱码问题

在 Windows 系统下使用妙想 Skills 时，可能会遇到控制台编码问题（GBK 无法显示 UTF-8 字符）。

#### 解决方案：使用环境变量

**使用 mx-data 时**：
```bash
cd "C:\Users\kense\.claude\skills\mx-data" && PYTHONIOENCODING=utf-8 python mx_data.py "查询内容"
```

**使用 mx-search 时**：
```bash
cd "C:\Users\kense\.claude\skills\mx-search" && PYTHONIOENCODING=utf-8 python mx_search.py "查询内容"
```

#### 或者使用便捷脚本（如果已创建）

```bash
# 直接调用批处理文件
mx-data.cmd "查询内容"
mx-search.cmd "查询内容"
```

#### 方法3：使用包装脚本（最推荐，避免编码问题）

**在 Claude Code 技能中使用时**，推荐使用 Python 包装脚本：

```bash
# 查询财务数据
python "C:\Users\kense\.claude\skills\cn-stock-analysis\scripts\mx_wrapper.py" data "牧原股份 营业收入 净利润"

# 搜索资讯  
python "C:\Users\kense\.claude\skills\cn-stock-analysis\scripts\mx_wrapper.py" search "白酒行业景气度"
```

**包装脚本的优势**：
- ✅ 自动处理编码问题
- ✅ 直接读取生成的 JSON 文件
- ✅ 返回结构化数据
- ✅ 避免控制台输出乱码
- ✅ 适合在技能中自动调用

---

## 目录

- [妙想 Skills 使用指南](#妙想-skills-使用指南)
- [cn-financial MCP 工具使用指南](#cn-financial-mcp-工具使用指南)
- [8个核心指标数据获取](#8个核心指标数据获取)
- [必须获取的数据](#必须获取的数据)

---

## 妙想 Skills 使用指南

### mx-search：综合信息查询

**用途**：获取最新资讯、行业信息、景气度、研报等综合信息

#### 常用查询场景

| 场景 | mx-search 查询示例 |
|------|-------------------|
| **公司最新资讯** | `/mx-search "贵州茅台最新公告和新闻"` |
| **行业景气度** | `/mx-search "白酒行业景气度分析"` |
| **行业动态** | `/mx-search "白酒行业最新动态"` |
| **研报分析** | `/mx-search "贵州茅台研报 分析师评级"` |
| **政策影响** | `/mx-search "消费政策对白酒行业影响"` |
| **竞争格局** | `/mx-search "白酒行业竞争格局 市场份额"` |
| **风险事件** | `/mx-search "贵州茅台风险提示 负面新闻"` |

#### mx-search 在分析流程中的应用

**第二阶段：行业识别与景气度分析**
```bash
# 获取行业信息
/mx-search "贵州茅台所属行业 行业定位"

# 获取行业景气度
/mx-search "白酒行业景气度 供需关系 价格趋势"

# 获取政策环境
/mx-search "白酒行业政策环境 监管变化"
```

**第七阶段：股价趋势分析**
```bash
# 获取最新资讯影响
/mx-search "贵州茅台最新新闻 股价影响"

# 获取资金流向
/mx-search "贵州茅台资金流向 北向资金"
```

---

### mx-data：结构化数据查询

**用途**：获取股价、财务数据、估值指标等结构化数据

#### 常用查询场景

| 场景 | mx-data 查询示例 |
|------|-----------------|
| **实时行情** | `/mx-data "贵州茅台最新收盘价、涨跌幅、成交量"` |
| **估值指标** | `/mx-data "贵州茅台市盈率、市净率、市销率"` |
| **财务数据** | `/mx-data "贵州茅台近三年营业收入、净利润"` |
| **盈利能力** | `/mx-data "贵州茅台ROE、毛利率、净利率"` |
| **现金流** | `/mx-data "贵州茅台经营现金流、自由现金流"` |
| **资产负债** | `/mx-data "贵州茅台资产负债率、流动比率"` |
| **季度数据** | `/mx-data "贵州茅台最近8个季度营业收入"` |
| **分红数据** | `/mx-data "贵州茅台近五年分红情况"` |
| **股东信息** | `/mx-data "贵州茅台十大股东 股东人数"` |
| **行业对比** | `/mx-data "白酒行业上市公司 估值对比"` |

#### mx-data 在8个核心指标分析中的应用

**指标1：现金收入比**
```bash
/mx-data "贵州茅台销售商品收到的现金 营业收入"
/mx-data "贵州茅台近五年经营现金流 净利润"
```

**指标2：净资产收益率(ROE)**
```bash
/mx-data "贵州茅台近五年ROE 加权平均净资产收益率"
/mx-data "贵州茅台净资产 净利润"
```

**指标3：人均创收和人均创利**
```bash
/mx-data "贵州茅台员工总数 营业收入 净利润"
```

**指标4：总资产周转率**
```bash
/mx-data "贵州茅台总资产 营业收入"
```

**指标5：季度收入增长率**
```bash
/mx-data "贵州茅台最近8个季度营业收入 同比增长"
```

**指标6：商誉净资产比**
```bash
/mx-data "贵州茅台商誉 净资产"
```

**指标7：毛利率**
```bash
/mx-data "贵州茅台营业收入 营业成本 毛利率"
/mx-data "贵州茅台近五年毛利率变化"
```

**指标8：研发支出占比**
```bash
/mx-data "贵州茅台研发费用 营业收入"
```

---

### 妙想 Skills 查询技巧

#### 技巧1：一次性获取多项数据

```bash
# 推荐：一次查询获取相关数据
/mx-data "贵州茅台：PE、PB、ROE、毛利率、净利率、营收、净利润"
```

#### 技巧2：指定时间范围

```bash
# 获取历史数据
/mx-data "贵州茅台近五年营业收入、净利润、ROE"
/mx-data "贵州茅台最近8个季度营收 环比增长"
```

#### 技巧3：组合查询

```bash
# 结合 mx-search 和 mx-data
/mx-search "白酒行业景气度"
/mx-data "贵州茅台 五粮液 泸州老窖 PE ROE 对比"
```

#### 技巧4：行业数据查询

```bash
# 行业整体情况
/mx-data "白酒行业上市公司 总市值 营收排名"
/mx-search "白酒行业资金流向 板块表现"
```

---

## cn-financial MCP 工具使用指南

**用途**：当妙想Skills无法满足时，作为备用数据源

### 主要使用场景

| 场景 | 工具 | 原因 |
|------|------|------|
| **获取多期历史数据** | `get_valuation_metrics` | 需要长期历史计算分位 |
| **详细财务报表** | `get_income_statement` 等 | 获取完整的季度报表数据 |
| **行业成分股列表** | `get_industry_stocks` | 获取行业内所有公司 |
| **竞争对手对比** | `get_competitors` | 自动识别同行业公司 |

### 工具列表

| 工具 | 用途 | 参数 |
|------|------|------|
| `get_company_info` | 公司基本信息 | symbol |
| `get_realtime_quote` | 实时行情 | symbol |
| `get_historical_price` | 历史K线 | symbol, period, adjust |
| `get_income_statement` | 利润表 | symbol, num_quarters |
| `get_balance_sheet` | 资产负债表 | symbol, num_quarters |
| `get_cash_flow_statement` | 现金流量表 | symbol, num_quarters |
| `get_financial_indicators` | 财务指标 | symbol, num_periods |
| `get_valuation_metrics` | 估值指标历史 | symbol, num_periods |
| `get_industry_stocks` | 行业成分股 | industry |

---

## 8个核心指标数据获取

### 使用妙想Skills获取

| 指标 | mx-data 查询示例 |
|------|-----------------|
| **现金收入比** | `/mx-data "[公司名]销售商品收到的现金 营业收入"` |
| **ROE** | `/mx-data "[公司名]近五年ROE 净资产收益率"` |
| **人均创收/创利** | `/mx-data "[公司名]员工总数 营业收入 净利润"` |
| **总资产周转率** | `/mx-data "[公司名]总资产 营业收入"` |
| **季度收入增长率** | `/mx-data "[公司名]最近8个季度营收 同比增长"` |
| **商誉净资产比** | `/mx-data "[公司名]商誉 净资产"` |
| **毛利率** | `/mx-data "[公司名]营业收入 营业成本 毛利率"` |
| **研发支出占比** | `/mx-data "[公司名]研发费用 营业收入"` |

### 使用cn-financial MCP获取（备用）

| 指标 | MCP 工具 |
|------|---------|
| **现金收入比** | `get_cash_flow_statement` + `get_income_statement` |
| **ROE** | `get_financial_indicators` |
| **人均创收/创利** | 需从年报获取员工数 |
| **总资产周转率** | `get_balance_sheet` + `get_income_statement` |
| **季度收入增长率** | `get_income_statement` num_quarters=8 |
| **商誉净资产比** | `get_balance_sheet` |
| **毛利率** | `get_income_statement` |
| **研发支出占比** | `get_income_statement` |

---

## 必须获取的数据

### 多期数据要求

无论使用哪种数据源，必须获取**多期对比数据**：
- **年报数据**：至少过去5年
- **季报数据**：最近8个季度

### 数据完整性检查清单

- [ ] 基本信息（公司名称、代码、行业）
- [ ] 实时行情（股价、涨跌幅、成交量）
- [ ] 估值指标（PE、PB、PS）
- [ ] 盈利能力（ROE、毛利率、净利率）
- [ ] 成长性（营收增长率、净利润增长率）
- [ ] 财务健康（资产负债率、流动比率）
- [ ] 现金流（经营现金流、自由现金流）
- [ ] 行业信息（行业定位、竞争对手）
- [ ] 最新资讯（公告、新闻、研报）

---

## 数据验证方法

### 方法1：官方渠道验证

- 上海证券交易所：https://www.sse.com.cn/
- 深圳证券交易所：https://www.szse.cn/
- 巨潮资讯网：https://www.cninfo.com.cn/

### 方法2：东方财富网验证

妙想Skills数据来源即为东方财富，可直接在东方财富网验证：
- 东方财富网：https://www.eastmoney.com/

### 方法3：多源交叉验证

使用妙想Skills查询后，可用 cn-financial MCP 工具交叉验证关键数据。
