# 防反爬虫策略详解

微信公众号对异常访问行为有检测机制，包括频率检测、行为模式分析和 IP 限制。本文档提供完整的防反爬虫配置。

## 一、延迟参数配置

### 文章间延迟

| 场景 | 延迟范围 | 说明 |
|------|----------|------|
| 文章间等待 | 3-8 秒 | 两篇文章采集之间的间隔 |
| 批次间休息 | 30-60 秒 | 每 5 篇后的较长休息 |
| 模拟阅读 | 10-30 秒 | 打开文章后模拟阅读时间 |

### 单篇文章内延迟

| 操作 | 延迟范围 | 说明 |
|------|----------|------|
| 滚动间隔 | 0.5-2 秒 | 每次滚动后的等待 |
| 提取前等待 | 1-3 秒 | 页面完全加载后等待 |
| 图片下载间 | 0.5-2 秒 | 每张图片下载后等待 |

### 随机延迟实现

```bash
# 通用随机延迟函数（毫秒）
random_delay() {
  local min=$1
  local max=$2
  local delay=$((RANDOM % (max - min + 1) + min))
  agent-browser wait $delay
}

# 使用示例
random_delay 3000 8000   # 3-8秒随机等待
random_delay 500 2000    # 0.5-2秒随机等待
```

## 二、行为模拟策略

### 模拟真人阅读

打开文章后不要立即提取内容，模拟真人阅读行为：

```bash
# 1. 打开文章
agent-browser open "<URL>" && agent-browser wait --load networkidle

# 2. 模拟阅读顶部内容（随机等待 2-5 秒）
agent-browser wait $((RANDOM % 3000 + 2000))

# 3. 缓慢滚动，模拟阅读
agent-browser scroll down 500 && agent-browser wait $((RANDOM % 1500 + 800))
agent-browser scroll down 500 && agent-browser wait $((RANDOM % 1500 + 800))
agent-browser scroll down 800 && agent-browser wait $((RANDOM % 2000 + 1000))
# ... 继续滚动到底部

# 4. 滚动到底部后等待（模拟阅读完毕）
agent-browser wait $((RANDOM % 3000 + 2000))

# 5. 提取内容
```

### 滚动模式

不要使用固定距离的匀速滚动，应该模拟真人不规则的滚动模式：

```bash
# 不规则滚动模式
agent-browser scroll down $((RANDOM % 300 + 400)) && agent-browser wait $((RANDOM % 800 + 400))
agent-browser scroll down $((RANDOM % 400 + 600)) && agent-browser wait $((RANDOM % 1000 + 500))
agent-browser scroll down $((RANDOM % 300 + 500)) && agent-browser wait $((RANDOM % 1200 + 600))
agent-browser scroll down $((RANDOM % 500 + 800)) && agent-browser wait $((RANDOM % 1500 + 800))
agent-browser scroll down $((RANDOM % 200 + 300)) && agent-browser wait $((RANDOM % 1000 + 500))
# 最后一次滚动较大距离到底部
agent-browser scroll down $((RANDOM % 500 + 1500)) && agent-browser wait $((RANDOM % 2000 + 1000))
```

## 三、批量采集控制

### 批次管理

```bash
# 配置参数
BATCH_SIZE=5          # 每批次文章数
BATCH_PAUSE_MIN=30    # 批次间最小休息秒数
BATCH_PAUSE_MAX=60    # 批次间最大休息秒数
ARTICLE_PAUSE_MIN=3   # 文章间最小等待秒数
ARTICLE_PAUSE_MAX=8   # 文章间最大等待秒数
```

### 批次间休息

每完成一个批次（5 篇），执行较长的休息：

```bash
# 批次间休息 30-60 秒
batch_pause() {
  local pause=$((RANDOM % 31 + 30))
  echo "批次完成，休息 ${pause} 秒..."
  sleep $pause
}
```

### 全局频率限制

每小时最多采集 20-30 篇文章，避免短时间内大量请求：

```bash
# 如果 1 小时内采集超过 25 篇，强制休息 5 分钟
```

## 四、异常处理

### 验证码检测

如果页面出现验证码或异常提示，立即停止采集：

```bash
# 检测是否出现验证码
agent-browser eval --stdin <<'EOF'
JSON.stringify({
  hasVerify: !!document.querySelector('.verify_wrap, .captcha, #verify'),
  url: window.location.href,
  title: document.title
})
EOF
```

**触发验证码后的处理**：
1. 立即停止所有采集操作
2. 关闭浏览器
3. 提示用户手动处理验证码
4. 等待用户确认后继续

### 频率限制响应

如果收到 429 错误或页面加载异常：
1. 停止当前操作
2. 休息 60-120 秒
3. 降低后续采集频率（文章间延迟增加到 8-15 秒）

### 连接失败重试

```bash
# 重试策略：最多重试 3 次，每次间隔翻倍
max_retries=3
retry_delay=5

for i in $(seq 1 $max_retries); do
  agent-browser open "<URL>" && break
  echo "第 $i 次重试，等待 $retry_delay 秒..."
  sleep $retry_delay
  retry_delay=$((retry_delay * 2))
done
```

## 五、会话管理

### 复用浏览器会话

同批次内不要反复开关浏览器，保持一个会话完成多篇文章：

```
正确做法：
1. open 浏览器
2. 采集文章 1
3. 直接导航到文章 2（不关闭浏览器）
4. 采集文章 2
5. ... 直到批次完成
6. close 浏览器

错误做法：
1. open → 采集文章 1 → close
2. open → 采集文章 2 → close  ← 每次都开关，容易被检测
```

### 导航方式

使用页面导航而非关闭重开：

```bash
# 方式 1：直接导航
agent-browser navigate "<下一篇文章URL>"
agent-browser wait --load networkidle

# 方式 2：通过地址栏
agent-browser open "<下一篇文章URL>"
```

## 六、图片下载策略

图片下载也会被检测，需要控制频率：

```bash
# 图片下载脚本示例
download_images() {
  local urls=("$@")
  for url in "${urls[@]}"; do
    curl -s -o "img$(printf '%02d' $index).png" "$url"
    # 随机等待 0.5-2 秒
    sleep $(echo "scale=2; ($RANDOM % 1500 + 500) / 1000" | bc)
  done
}
```

### 图片 CDN 特殊处理

微信图片使用 `mmbiz.qpic.cn` CDN，注意：
- 图片 URL 可能有时效性（带 `Expires` 参数）
- 尽量在文章页面关闭前下载完所有图片
- 如果图片下载失败，不要立即重试，等待 5-10 秒

## 七、监控指标

采集过程中关注以下指标，及时发现异常：

| 指标 | 正常范围 | 异常处理 |
|------|----------|----------|
| 文章加载时间 | <5 秒 | >10 秒则暂停 |
| 图片下载成功率 | >95% | <80% 则检查频率 |
| 验证码出现 | 0 次 | 出现则立即停止 |
| 连续失败次数 | <3 次 | >=3 次则休息 2 分钟 |

## 八、最佳实践总结

1. **宁慢勿快** — 速度不是目标，稳定采集才是
2. **随机化一切** — 延迟、滚动距离、操作间隔都要随机
3. **模拟真人** — 像人一样阅读、滚动、停留
4. **及时止损** — 遇到异常立即停止，不要硬闯
5. **分时段采集** — 避免在凌晨等异常时段大量采集
6. **保持会话** — 批次内复用浏览器，减少开关频率
