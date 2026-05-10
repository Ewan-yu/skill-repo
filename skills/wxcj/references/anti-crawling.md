# 防反爬虫策略详解

使用 camofox-browser（Camoufox 反指纹浏览器）后，反爬虫能力已大幅提升。Camoufox 在 C++ 层面伪装硬件指纹、WebGL、AudioContext、屏幕参数等，无需 JS 层面的 stealth 插件，指纹特征与真实用户一致。

但频率控制仍然是必要的——这与指纹伪装无关，而是避免短时间大量请求触发服务端限流。

## 一、camofox-browser 的反检测优势

| 检测维度 | 旧方案 (Playwright) | 新方案 (Camoufox) |
|----------|---------------------|-------------------|
| 浏览器引擎 | Chromium headless | Firefox C++ 级修改 |
| navigator 属性 | JS 层 shim，可被检测 | C++ 层面修改，无法检测 |
| WebGL 指纹 | 默认值，容易被标记 | 随机化渲染器信息 |
| AudioContext | 默认值 | C++ 层面随机化 |
| 屏幕参数 | headless 固定值 | 与代理 IP 地理位置匹配 |
| WebRTC | 默认泄露真实 IP | 自动屏蔽或伪装 |
| Headless 检测 | 容易被识别 | Firefox 原生模式，无 headless 标记 |

## 二、延迟参数配置

### 文章间延迟

| 场景 | 延迟范围 | 说明 |
|------|----------|------|
| 文章间等待 | 3-8 秒 | 两篇文章采集之间的间隔 |
| 批次间休息 | 30-60 秒 | 每 5 篇后的较长休息 |
| 模拟阅读 | 10-30 秒 | 打开文章后模拟阅读时间 |

### 单篇文章内延迟

| 操作 | 延迟范围 | 说明 |
|------|----------|------|
| 滚动间隔 | 0.4-3 秒 | 每次滚动后的等待（adapter 自动处理） |
| 提取前等待 | 1-3 秒 | 页面完全加载后等待 |
| 图片下载间 | 0.5-2 秒 | 每张图片下载后等待 |

### adapter 自动处理

`camofox_adapter.py scroll` 命令已内置不规则滚动，无需手动配置延迟：

```bash
python3 scripts/camofox_adapter.py scroll "$TAB_ID"
# 内部执行 6 次随机距离(200-1500px)和随机间隔(0.4-3s)的滚动
```

## 三、批量采集控制

### 批次管理

```bash
BATCH_SIZE=5          # 每批次文章数
BATCH_PAUSE_MIN=30    # 批次间最小休息秒数
BATCH_PAUSE_MAX=60    # 批次间最大休息秒数
ARTICLE_PAUSE_MIN=3   # 文章间最小等待秒数
ARTICLE_PAUSE_MAX=8   # 文章间最大等待秒数
```

### 批次间休息

每完成一个批次（5 篇），执行较长的休息：

```bash
batch_pause() {
  local pause=$((RANDOM % 31 + 30))
  echo "批次完成，休息 ${pause} 秒..."
  sleep $pause
}
```

### 全局频率限制

每小时最多采集 20-30 篇文章，避免短时间内大量请求。

## 四、异常处理

### 验证码检测

如果页面出现验证码或异常提示，立即停止采集：

```bash
# 通过 snapshot 检查是否出现验证码
python3 scripts/camofox_adapter.py snapshot "$TAB_ID" | grep -i "verify\|captcha\|验证"
```

**触发验证码后的处理**：
1. 立即停止所有采集操作
2. 关闭 tab
3. 提示用户手动处理验证码
4. 等待用户确认后继续

### 频率限制响应

如果收到异常响应或页面加载异常：
1. 停止当前操作
2. 休息 60-120 秒
3. 降低后续采集频率（文章间延迟增加到 8-15 秒）

### 连接失败重试

```bash
# 重试策略：最多重试 3 次，每次间隔翻倍
max_retries=3
retry_delay=5

for i in $(seq 1 $max_retries); do
  TAB_ID=$(python3 scripts/camofox_adapter.py open "<URL>" 2>/dev/null) && break
  echo "第 $i 次重试，等待 $retry_delay 秒..."
  sleep $retry_delay
  retry_delay=$((retry_delay * 2))
done
```

## 五、会话管理

### 复用 tab

同批次内不要反复开关 tab，保持一个会话完成多篇文章：

```
正确做法：
1. TAB_ID=$(python3 scripts/camofox_adapter.py open 文章1URL)
2. 采集文章 1
3. python3 scripts/camofox_adapter.py close "$TAB_ID"
4. TAB_ID=$(python3 scripts/camofox_adapter.py open 文章2URL)
5. 采集文章 2
6. ... 直到批次完成

每篇文章用独立 tab，但共享同一 userId（复用 camofox 会话状态）
```

### 关闭会话

批次完成后，关闭整个会话：

```bash
python3 scripts/camofox_adapter.py close-all
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
- 尽量在 tab 关闭前下载完所有图片
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
2. **随机化一切** — 延迟、滚动距离、操作间隔都要随机（adapter 自动处理滚动）
3. **camofox 负责反指纹，你负责频率控制** — 两层防护各司其职
4. **及时止损** — 遇到异常立即停止，不要硬闯
5. **分时段采集** — 避免在凌晨等异常时段大量采集
