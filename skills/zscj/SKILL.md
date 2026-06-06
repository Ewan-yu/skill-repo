---
name: zscj
description: 知识星球专栏采集工具。当用户需要采集知识星球专栏文章、创建专栏目录索引、批量下载知识星球内容时使用此 skill。支持自动登录、文章提取、Obsidian 格式保存、图片下载、外链处理。触发词：知识星球采集、zsxq采集、专栏采集、知识星球文章下载。
---

# 知识星球专栏采集 (zscj)

基于 [Camoufox](https://camoufox.com/) 反指纹浏览器的知识星球专栏内容采集工具，支持自动登录、文章提取、Obsidian 格式保存。

## 前置条件

- Git、Node.js 18+
- Windows 用 `python`，Linux/Mac 用 `python3`
- 首次运行时 adapter 会自动从 GitHub 克隆并安装
- camofox-browser skill 已安装

## 工作流程概览

```
1. 初始化浏览器 → 2. 登录知识星球 → 3. 导航到专栏
→ 4. 排序（最早发布）→ 5. 提取文章列表 → 6. 创建目录索引
→ 7. 采集文章全文 → 8. 保存为 Obsidian 格式 → 9. 更新索引
```

---

## Step 1: 初始化浏览器

```bash
cd "C:/Users/kense/.claude/skills/camofox-browser"
python scripts/camofox_adapter.py init
```

如果服务器已运行，会自动复用。

---

## Step 2: 登录知识星球

**重要：登录过程中不要主动截图弹出，除非用户明确要求查看。唯一的例外是二维码截图——这是用户扫码所必需的，必须弹出。其他任何截图（如首页、登录成功页面）一律不弹出。**

### 2.1 打开登录页并处理弹窗

```bash
TAB_ID=$(python scripts/camofox_adapter.py open "https://wx.zsxq.com")
python scripts/camofox_adapter.py wait $TAB_ID -s "body" --timeout 15

# 处理用户协议弹窗（必须在截图前完成，否则二维码被遮挡）
python scripts/camofox_adapter.py click $TAB_ID --text "同意" 2>/dev/null
sleep 2
```

### 2.2 获取二维码并截图（仅此一次截图弹出）

```bash
# 点击"获取登录二维码"（如果需要）
python scripts/camofox_adapter.py click $TAB_ID --text "获取登录二维码" 2>/dev/null
sleep 2

# 截图展示给用户扫码（这是登录流程中唯一需要弹出的截图）
python scripts/camofox_adapter.py screenshot $TAB_ID --output /tmp/zsxq_qr.png --view
# 告知用户："请用微信/App 扫描截图中的二维码，扫码完成后告诉我"
# ← 等待用户确认
```

### 2.3 检测登录成功并保存状态

```bash
# 等待页面跳转到主页（不要截图，静默等待即可）
python scripts/camofox_adapter.py wait $TAB_ID --url-pattern "/group/|/home|/columns" --timeout 120

# 保存登录状态
mkdir -p auth_states
python scripts/auth_state.py save $TAB_ID --output auth_states/zsxq.json
```

---

## 登录状态管理（重要）

auth_state.json 保存了 cookies 和 localStorage，但有以下限制：

- **Camoufox 重启后内存状态丢失**：每次浏览器服务重启，cookie 需重新注入
- **Session cookie 有生命周期**：zsxq.com 的登录 token 可能几小时后过期，过期后需重新扫码登录
- **正确流程**：直接打开目标 URL → 如果跳转登录页则 restore cookie → 重新导航

---

## Step 3: 导航到专栏页面

```bash
# 直接打开目标页面（和真人一样直接输入 URL）
TAB_ID=$(python scripts/camofox_adapter.py open "https://wx.zsxq.com/columns/专栏ID")
python scripts/camofox_adapter.py wait $TAB_ID -s "body" --timeout 15

# 检查是否跳转到了登录页
NEED_LOGIN=$(python scripts/camofox_adapter.py eval $TAB_ID "
  location.href.includes('/login') ? 'true' : 'false'
")

if [ "$NEED_LOGIN" = "true" ]; then
  # 登录态已失效，恢复 cookie 后重新导航
  python scripts/auth_state.py restore $TAB_ID --input auth_states/zsxq.json
  python scripts/camofox_adapter.py navigate $TAB_ID "https://wx.zsxq.com/columns/专栏ID"
  python scripts/camofox_adapter.py wait $TAB_ID -s "body" --timeout 15

  # 再次检查，如果仍然跳转登录则需要重新扫码
  STILL_LOGIN=$(python scripts/camofox_adapter.py eval $TAB_ID "
    location.href.includes('/login') ? 'true' : 'false'
  ")
  if [ "$STILL_LOGIN" = "true" ]; then
    echo "NEED_RELOGIN"
    # 返回 Step 2 重新登录
  fi
fi
```

---

## Step 4: 按"最早发布"排序

知识星球的排序按钮在 `.sort-container` 中，需要通过 JS 点击：

```bash
# 先随机滚动一下，模拟浏览行为
python scripts/camofox_adapter.py scroll $TAB_ID --amount 300
sleep $(python -c "import random; print(round(random.uniform(0.8, 1.5), 1))")

# 点击排序按钮展开下拉菜单
python scripts/camofox_adapter.py eval $TAB_ID "document.querySelector('.sort').click(); 'clicked'"

# 等待下拉菜单出现
sleep $(python -c "import random; print(round(random.uniform(0.8, 1.5), 1))")

# 点击"最早发布"
python scripts/camofox_adapter.py eval $TAB_ID "
Array.from(document.querySelectorAll('.sort-container *'))
  .find(el => el.textContent.trim() === '最早发布')
  ?.click(); 'clicked'
"

# 等待页面刷新
python scripts/camofox_adapter.py wait $TAB_ID -s "body" --timeout 10
```

---

## Step 5: 提取文章列表

使用 JS 脚本循环点击每篇文章，提取标题和正文链接。**每篇间隔随机 1-2 秒，模拟真人浏览节奏。**

```bash
python scripts/camofox_adapter.py eval $TAB_ID "
// 初始化收集器
window._collector = { results: [], index: 0, done: false, total: 0 };

function randomDelay() {
  // 随机 1000-2000ms，模拟真人点击间隔
  return 1000 + Math.floor(Math.random() * 1000);
}

(function collectNext() {
  const items = document.querySelectorAll('.topic-item');
  const total = items.length;
  window._collector.total = total;
  
  if (window._collector.index >= total) {
    window._collector.done = true;
    return;
  }
  
  // 先滚动到当前文章位置，模拟浏览
  const currentItem = items[window._collector.index];
  currentItem.scrollIntoView({ behavior: 'smooth', block: 'center' });
  
  // 随机延迟后点击
  setTimeout(function() {
    currentItem.click();
    
    // 等待内容加载后提取链接
    setTimeout(function() {
      const links = document.querySelectorAll('a.link-of-topic[href*=\"articles.zsxq.com\"]');
      const title = currentItem.querySelector('.content')?.textContent?.trim() || '';
      const url = links.length > 0 ? links[links.length - 1].href : '';
      
      window._collector.results.push({ title, url });
      window._collector.index++;
      collectNext();
    }, 500 + Math.floor(Math.random() * 500));  // 内容加载等待 500-1000ms
  }, randomDelay());
})();

'collection started, total items: ' + items.length;
"
```

等待收集完成（每篇约 1.5-3 秒，100 篇约 3-5 分钟）：

```bash
# 估算等待时间：每篇平均 2 秒
sleep $((total * 2 + 10))
python scripts/camofox_adapter.py eval $TAB_ID "
JSON.stringify({ done: window._collector.done, collected: window._collector.results.length })
"
```

提取结果：

```bash
python scripts/camofox_adapter.py eval $TAB_ID "JSON.stringify(window._collector.results)"
```

---

## Step 6: 创建 Obsidian 目录索引

### 6.1 文件格式

```markdown
# 专栏名称 - 目录索引

> 来源：知识星球「专栏名称」专栏
> 排序：最早发布
> 总计：X 篇文章
> 采集时间：YYYY-MM-DD

---

| # | 标题 | 链接 | 已采集 |
|---|------|------|--------|
| 1 | [[001_文章标题]] | [阅读原文](url) | ✅ |
| 2 | 文章标题 | [阅读原文](url) | ⬜ |
```

### 6.2 标题和双链格式

**重要：文章标题必须使用从文章页面提取的"原文标题"，而非目录索引中的标题。**

- 文件名格式：`序号_标题.md`
  - 序号：3位数字，如 001、002
  - 标题：按规则从 heading 中提取（见下方）
- 双链格式：`[[序号_标题]]`

#### 标题提取规则

从 heading 中提取标题，按以下优先级处理：

1. **有《》书名格式**：去掉 `Book XX |` 前缀，保留 `书名：文章标题`
   - `Book 04 |《遥远的救世主》：这本书讲了个什么故事？` → `遥远的救世主：这本书讲了个什么故事？`

2. **有冒号分隔**：去掉序号前缀，保留 `主题：文章标题`
   - `04 这本书讲了个什么故事？` → `这本书讲了个什么故事？`

3. **其他情况**：直接使用 heading 内容，去掉序号前缀
   - `这本书讲了个什么故事？` → `这本书讲了个什么故事？`

4. **如果 heading 为空**：使用目录索引中的标题

---

## Step 7: 采集文章全文

**重要：标题提取规则**

从文章快照的 `heading` 中提取标题，格式为 `序号_提取的标题.md`

#### 提取逻辑（按优先级）

1. **有《》书名格式**：
   - `Book 04 |《遥远的救世主》：这本书讲了个什么故事？`
   - → `遥远的救世主：这本书讲了个什么故事？`
   - 文件名：`007_遥远的救世主：这本书讲了个什么故事？.md`

2. **有冒号分隔**：
   - `04 这本书讲了个什么故事？`
   - → `这本书讲了个什么故事？`
   - 文件名：`007_这本书讲了个什么故事？.md`

3. **其他情况**：
   - `这本书讲了个什么故事？`
   - → `这本书讲了个什么故事？`
   - 文件名：`007_这本书讲了个什么故事？.md`

4. **heading 为空**：使用目录索引中的标题

### 7.1 打开文章页面

```bash
# 直接打开文章 URL（和真人一样）
TAB_ID=$(python scripts/camofox_adapter.py open "文章URL")
python scripts/camofox_adapter.py wait $TAB_ID -s "body" --timeout 15

# 检查是否需要恢复登录态
NEED_LOGIN=$(python scripts/camofox_adapter.py eval $TAB_ID "
  location.href.includes('/login') ? 'true' : 'false'
")
if [ "$NEED_LOGIN" = "true" ]; then
  python scripts/auth_state.py restore $TAB_ID --input auth_states/zsxq.json
  python scripts/camofox_adapter.py navigate $TAB_ID "文章URL"
  python scripts/camofox_adapter.py wait $TAB_ID -s "body" --timeout 15
fi
```

### 7.2 模拟阅读 + 提取文章内容

**重要：不要打开页面立即提取！** 先模拟真人阅读行为（随机滚动 + 停留），再提取内容。

```bash
# 模拟阅读：随机滚动 2-4 次，每次间隔 1-2 秒
python scripts/camofox_adapter.py scroll $TAB_ID --amount 400
sleep $(python -c "import random; print(round(random.uniform(1.0, 2.0), 1))")
python scripts/camofox_adapter.py scroll $TAB_ID --amount 600
sleep $(python -c "import random; print(round(random.uniform(1.0, 2.0), 1))")
python scripts/camofox_adapter.py scroll $TAB_ID --amount 300
sleep $(python -c "import random; print(round(random.uniform(0.8, 1.5), 1))")

# 滚回顶部后提取
python scripts/camofox_adapter.py eval $TAB_ID "window.scrollTo(0, 0); 'ok'"
sleep 1

# 使用 snapshot 获取文章结构化内容
python scripts/camofox_adapter.py snapshot $TAB_ID
```

### 7.3 下载文章中的图片

```bash
# 提取所有图片 URL
python scripts/camofox_adapter.py eval $TAB_ID "
const imgs = document.querySelectorAll('article img, .topic-content img, .content img');
const urls = Array.from(imgs).map(img => img.src).filter(src => src);
JSON.stringify(urls);
"

# 图片保存在专栏根目录的 images/ 目录下，文件名前加序号前缀
# 例如：images/007_img1.jpg, images/007_img2.png
mkdir -p "images"

# 下载每张图片（需要逐个处理）
# 图片通常需要登录态，使用浏览器下载
```

### 7.4 保存为 Obsidian 格式

**重要：不要为每篇文章创建单独的目录！** 所有文件直接保存在专栏根目录下。

文件结构：
```
专栏根目录/
├── 专栏名称_目录索引.md
├── 001_张艺谋的作业：命运就是机会和抓住机会的能力.md
├── 002_张艺谋的作业：与张艺谋有关的一些句子.md
├── ...
├── images/                    # 所有文章的图片共用一个目录
│   ├── 001_img1.jpg
│   ├── 001_img2.png
│   ├── 002_img1.jpg
│   └── ...
```

Markdown 格式：
```markdown
---
title: "原文标题"
author: 作者
date: 发布日期
source: 知识星球「专栏名称」专栏
url: 原文链接
tags:
  - 标签1
  - 标签2
---

# 文章标题

> 来自：[来源链接](url)

正文内容...

![图片描述](images/img1.jpg)

---

*本文来自知识星球「专栏名称」专栏。*
```

---

## Step 8: 外链处理规则

### 8.1 内部链接（知识星球内）

- 文章中引用的其他已采集文章 → 替换为本地双链 `[[序号_文章标题]]`
- 未采集的文章 → 保留原始链接

### 8.2 外部链接

- 保留所有外部链接不修改
- 电子书搜索链接（如微信读书）→ 保留原样

### 8.3 图片链接

- 知识星球图片 → 下载到本地 `images/` 目录
- 外部图片 → 保留原始 URL

---

## Step 9: 更新目录索引

采集完一篇文章后，更新索引文件：

1. 将对应行的标题改为双链格式：`[[序号_文章标题]]`
2. 将"已采集"列从 ⬜ 改为 ✅

---

## 完整采集流程示例

```bash
# 1. 初始化
cd "C:/Users/kense/.claude/skills/camofox-browser"
python scripts/camofox_adapter.py init

# 2. 直接打开知识星球（和真人一样输入 URL）
TAB_ID=$(python scripts/camofox_adapter.py open "https://wx.zsxq.com")
python scripts/camofox_adapter.py wait $TAB_ID -s "body" --timeout 15

# 检查是否需要登录
NEED_LOGIN=$(python scripts/camofox_adapter.py eval $TAB_ID "
  location.href.includes('/login') ? 'true' : 'false'
")

if [ "$NEED_LOGIN" = "true" ]; then
  # 尝试恢复 cookie 后刷新
  python scripts/auth_state.py restore $TAB_ID --input auth_states/zsxq.json
  python scripts/camofox_adapter.py navigate $TAB_ID "https://wx.zsxq.com"
  python scripts/camofox_adapter.py wait $TAB_ID -s "body" --timeout 15

  # 仍然需要登录，走扫码流程
  STILL_LOGIN=$(python scripts/camofox_adapter.py eval $TAB_ID "
    location.href.includes('/login') ? 'true' : 'false'
  ")
  if [ "$STILL_LOGIN" = "true" ]; then
    # 处理弹窗 + 截图二维码（唯一弹出的截图）
    python scripts/camofox_adapter.py click $TAB_ID --text "同意" 2>/dev/null
    sleep $(python -c "import random; print(round(random.uniform(1.5, 2.5), 1))")
    python scripts/camofox_adapter.py click $TAB_ID --text "获取登录二维码" 2>/dev/null
    sleep $(python -c "import random; print(round(random.uniform(1.5, 2.5), 1))")
    python scripts/camofox_adapter.py screenshot $TAB_ID --output /tmp/zsxq_qr.png --view
    # ← 等待用户扫码

    # 静默等待登录成功 + 保存状态
    python scripts/camofox_adapter.py wait $TAB_ID --url-pattern "/group/|/home|/columns" --timeout 120
    python scripts/auth_state.py save $TAB_ID --output auth_states/zsxq.json
  fi
fi

# 3. 导航到专栏（登录态已在当前 tab 中）
python scripts/camofox_adapter.py navigate $TAB_ID "专栏URL"
python scripts/camofox_adapter.py wait $TAB_ID -s "body" --timeout 15

# 6. 排序（带随机滚动）
python scripts/camofox_adapter.py scroll $TAB_ID --amount 300
sleep $(python -c "import random; print(round(random.uniform(0.8, 1.5), 1))")
python scripts/camofox_adapter.py eval $TAB_ID "document.querySelector('.sort').click()"
sleep $(python -c "import random; print(round(random.uniform(0.8, 1.5), 1))")
python scripts/camofox_adapter.py eval $TAB_ID "Array.from(document.querySelectorAll('.sort-container *')).find(el => el.textContent.trim() === '最早发布')?.click()"
python scripts/camofox_adapter.py wait $TAB_ID -s "body" --timeout 10

# 7. 提取文章列表（每篇 1-2 秒随机间隔，100 篇约 3-5 分钟）
python scripts/camofox_adapter.py eval $TAB_ID "// 收集器代码（含随机延迟）..."
# 等待收集完成：sleep $((total * 2 + 10))

# 8. 采集每篇文章（每篇先模拟阅读再提取）
# for article in articles; do
#   navigate → scroll 2-4次 → snapshot → 保存
#   sleep $(python -c "import random; print(round(random.uniform(1.0, 3.0), 1))")
# done
```

---

## 反爬注意事项

本技能已内置以下反爬策略，**请勿修改关键参数**：

| 策略 | 参数 | 说明 |
|------|------|------|
| 文章列表采集间隔 | 随机 1-2 秒/篇 | 模拟真人点击节奏 |
| 文章阅读模拟 | 随机滚动 2-4 次 + 停留 | 避免"秒读"特征 |
| 操作间等待 | 随机范围（非固定值） | 消除机械性定时特征 |
| 页面滚动 | 每次操作前随机滚动 | 模拟浏览行为 |

**使用建议：**

1. **单次采集控制在 100 篇以内**，超过 50 篇建议分批次，中间间隔 5-10 分钟
2. **避免在高峰期（工作日白天）批量采集**，深夜或凌晨触发风控概率更低
3. **如果被要求验证/封号**，立即停止采集，等待 24 小时后再试
4. **不要并发打开多个 tab 采集**，单 tab 顺序操作最安全

---

## 故障排除

### 登录二维码被遮挡

**原因**：用户协议弹窗未处理
**解决**：2.1 步骤中已包含点击"同意"，确保在截图前执行

### 登录状态失效 / 频繁要求重新登录

**原因**：Camoufox 重启后内存 cookie 丢失，或 token 自然过期
**解决**：每次访问 zsxq.com 前先 restore；如果 restore 后仍跳转登录页，说明 token 过期，需重新扫码

### 文章内容不完整

**原因**：页面未完全加载
**解决**：使用 `wait -s "body"` 等待加载完成

### 图片下载失败

**原因**：图片需要登录态
**解决**：确保已 restore 登录状态，使用浏览器直接下载

### 排序不生效

**原因**：点击了错误的元素
**解决**：使用 JS 直接操作 `.sort-container`

---

## 文件结构

```
zscj/
├── SKILL.md           # 本文件
├── auth_states/       # 登录状态存储
│   └── zsxq.json
└── articles/          # 采集的文章存储
    └── 从书中学/
        ├── 从书中学_目录索引.md
        ├── 001_张艺谋的作业：命运就是机会和抓住机会的能力.md
        ├── 002_张艺谋的作业：与张艺谋有关的一些句子.md
        ├── 004_黑客与画家：创作者的价值.md
        ├── ...
        └── images/            # 所有文章图片共用
            ├── 001_img1.jpg
            ├── 002_img1.png
            └── ...
```
