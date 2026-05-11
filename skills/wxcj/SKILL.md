---
name: wxcj
description: 微信公众号文章采集工具。将微信公众号文章完整保存到本地 Obsidian 知识库，包括文字内容、配图本地化、样式保留（加粗、斜体、删除线、引用块等）。当用户提供微信公众号文章链接（mp.weixin.qq.com/s）、合集/专辑链接、或要求采集/保存/下载公众号文章、批量导出公众号内容时使用此 skill。支持单篇和批量采集，自动处理图片懒加载和 blob URL 问题，支持断点续采。已采集文章中的内链自动转为 Obsidian 双链 [[标题]]。使用 camofox-browser（Camoufox 反指纹浏览器）作为底层引擎，C++ 级别反检测。
---

# 微信公众号文章采集 (wxcj)

将微信公众号文章采集并保存为 Obsidian 规范的 Markdown 文件，配图下载到本地，保留原文样式。

底层使用 **camofox-browser**（基于 Camoufox 的反指纹浏览器），在 C++ 层面伪装硬件指纹、WebGL、AudioContext 等，反爬虫能力远超 Playwright + 随机延迟方案。

## 文件结构

```
wxcj/
├── SKILL.md                    # 本文件 - 工作流程说明
├── scripts/
│   ├── camofox_adapter.py      # camofox-browser 适配层（自动安装 + HTTP API 封装）
│   ├── extract_content.js      # 文章内容提取（TreeWalker + 样式保留 + Obsidian 双链）
│   ├── extract_article_list.js # 合集文章列表提取（使用 data-link 属性）
│   ├── extract_images.js       # 图片 URL 提取
│   └── extract_metadata.js     # 文章元数据提取
└── references/
    ├── templates.md            # 目录索引和文章 Markdown 模板
    ├── image-placement.md      # 图片位置处理指南
    ├── troubleshooting.md      # 常见问题排查
    └── anti-crawling.md        # 防反爬虫策略详解
```

## 核心工具

**camofox_adapter.py** — 所有浏览器操作通过此适配层完成。它封装了 camofox-browser 的 HTTP API，并包含自动安装和启动逻辑。

首次使用时，脚本会自动：
1. 检查 camofox-browser 是否已安装
2. 未安装则自动 clone 仓库并执行 `npm install`
3. 自动启动本地服务（默认端口 9377）
4. 等待服务就绪

**前置要求**：本机需已安装 `git` 和 `Node.js 18+`（含 npm）。

**Windows 编码**：如遇中文乱码，在终端中设置 `set PYTHONUTF8=1` 或在系统环境变量中添加 `PYTHONUTF8=1`。脚本内已内置 UTF-8 强制输出。

## 工作流

### 第零步：初始化（每次采集前执行）

```bash
python3 scripts/camofox_adapter.py init
```

这一步会检查 camofox-browser 的健康状态。如果服务未运行或未安装，会自动完成安装和启动。首次运行可能需要几分钟（下载 CamouFox 浏览器引擎约 300MB），后续运行秒级完成。

### 第一步：解析文章列表（合集链接时）

当用户提供合集/专辑链接时：

```bash
TAB_ID=$(python3 scripts/camofox_adapter.py open "<合集URL>")
```

**合集页面结构**：每个文章是 `<li>` 元素，包含以下关键属性：
- `data-link`: 文章完整 URL（含 `&amp;` 编码，需解码）
- `data-title`: 文章标题
- `data-msgid`: 消息 ID（可用于去重）
- `data-itemidx`: 序号

示例：
```html
<li class="album__list-item js_album_item"
    data-msgid="2650320567"
    data-link="http://mp.weixin.qq.com/s?__biz=xxx&amp;mid=xxx&amp;idx=1&amp;sn=xxx"
    data-title="文章标题"
    data-is_read="0">
```

滚动加载全部文章后，使用脚本提取：

```bash
python3 scripts/camofox_adapter.py eval "$TAB_ID" scripts/extract_article_list.js
```

**返回结果**：JSON 格式，包含 `articles` 数组和 `count`。每篇文章包含 `index`、`title`、`url`、`msgid` 字段。

**断点续采检查**：对比返回的 `count` 与目录索引中已采集数量，确认是否有新增文章。

提取完成后关闭 tab：

```bash
python3 scripts/camofox_adapter.py close "$TAB_ID"
```

### 第二步：创建或更新目录索引

在系列文件夹的**上级目录**创建 `系列名_目录索引.md`，模板详见 `references/templates.md`。

**首次创建**：直接从合集提取的文章列表创建目录索引。

**断点续采 / 更新检测**：
1. 读取现有目录索引，统计已采集数量（`✅ 已采集` 状态）
2. 对比合集提取的 `count` 与目录索引的 `total`
3. 如果 `count > total`，说明有新增文章：
   - 更新目录索引的 `total` 字段
   - 新增文章条目，状态标记为 `待采集`
   - 更新 `_urlmap.json` 添加新文章的 URL 映射
4. 如果目录索引已存在，从第一个 `待采集` 文章继续，跳过 `✅ 已采集` 的文章

### 第三步：创建文章文件夹结构

```
系列名/
├── 文章1.md
├── 文章2.md
├── assets/
│   ├── 01_拼音首字母/
│   │   ├── img01.png
│   │   └── img02.png
│   └── 02_拼音首字母/
```

**命名规范**：
- 文章文件：`序号_文章简称.md`
- 图片文件夹：`序号_拼音首字母`
- 图片文件：`img01.png`、`img02.png`...

### 第四步：采集单篇文章

#### 4.1 打开文章并滚动加载

```bash
TAB_ID=$(python3 scripts/camofox_adapter.py open "<文章URL>")
```

滚动触发所有图片懒加载（自动不规则滚动，模拟真人）：

```bash
python3 scripts/camofox_adapter.py scroll "$TAB_ID"
```

适配器内部会执行 6 次随机距离和随机间隔的滚动，模拟真人不规则阅读行为。如需手动控制滚动：

```bash
python3 scripts/camofox_adapter.py scroll "$TAB_ID" --amount 500
```

#### 4.2 构建并注入 URL 映射表

在提取内容前，读取目录索引和已采集文章的 frontmatter，构建 URL 映射表。映射表格式：

```json
{
  "http://mp.weixin.qq.com/s?__biz=xxx&mid=123": {
    "path": "系列名/01_文章名",
    "title": "文章标题"
  }
}
```

将映射表保存为 JSON 文件（如 `/tmp/urlmap.json`），然后在 eval 时通过 `--url-map` 参数注入：

```bash
python3 scripts/camofox_adapter.py eval "$TAB_ID" scripts/extract_content.js --url-map /tmp/urlmap.json
```

适配器会自动将映射表注入到 `window.__urlMap`，然后执行提取脚本。

#### 4.3 提取文章内容

使用 TreeWalker 遍历 DOM，按文档顺序提取文本和图片，保留加粗、斜体、删除线、下划线和引用块格式。

```bash
python3 scripts/camofox_adapter.py eval "$TAB_ID" scripts/extract_content.js
```

**返回结果**：JSON 格式，包含 `content`（文本内容，图片用 `[IMG_N]` 占位符标记）和 `imgCount`（图片数量）。

**Obsidian 双链**：脚本会自动将指向已采集文章的内链转为 `[[文件名|显示标题]]` 格式，未采集的文章保留原始链接。

示例：
- 已采集文章：`[[17_没有量化公募的时代要有时代的量化公募|没有量化公募的时代，要有时代的量化公募]]`
- 未采集文章：`[文章标题](https://mp.weixin.qq.com/s?...)`

#### 4.4 提取图片 URL 和元数据

```bash
python3 scripts/camofox_adapter.py eval "$TAB_ID" scripts/extract_images.js
python3 scripts/camofox_adapter.py eval "$TAB_ID" scripts/extract_metadata.js
```

两个脚本均返回 JSON 格式，包含错误信息（如适用）。

也可以通过 camofox 原生 API 获取图片（用于交叉验证）：

```bash
python3 scripts/camofox_adapter.py images "$TAB_ID"
```

#### 4.5 关闭 tab 并下载图片

```bash
python3 scripts/camofox_adapter.py close "$TAB_ID"
cd "系列名/assets/序号_拼音首字母"
curl -s -o img01.png "<图片URL>"
# 每张图片下载后随机等待 0.5-2 秒
sleep $(echo "scale=2; ($RANDOM % 1500 + 500) / 1000" | bc)
```

下载后验证文件大小（>0 字节）：`ls -la`

### 第五步：生成 Markdown 文件

**关键原则**：必须严格按照 `extract_content.js` 脚本返回的内容生成 Markdown 文件，图片位置完全由脚本决定，不要自行添加或移动任何图片。

**具体步骤：**

1. **解析脚本返回的 JSON**：提取 `content` 字段
2. **按序号替换占位符**：`[IMG_1]` → `![图片描述](assets/序号_拼音首字母/img01.png)`，以此类推
3. **图片描述生成规则**：根据图片上下文生成有意义的描述（表格截图 → "XX数据表"，走势图 → "XX走势对比"，产品图 → "产品名称"）
4. **添加 frontmatter 和相关链接**：按照模板格式添加元数据

**图片位置验证（必须执行）：**

生成文件后，立即验证图片位置是否正确：

```bash
# 1. 统计脚本返回的图片数量
echo "脚本返回的图片数量: $(grep -o '\[IMG_[0-9]*\]' /tmp/content.json | wc -l)"

# 2. 统计实际文件中的图片数量
echo "文件中的图片数量: $(grep -o '!\[' article.md | wc -l)"

# 3. 列出脚本返回的图片占位符顺序
grep -o '\[IMG_[0-9]*\]' /tmp/content.json

# 4. 列出文件中的图片顺序
grep -o '!\[.*\](assets/[^)]*)' article.md
```

如果数量或顺序不一致，必须重新生成文件！

**常见错误（必须避免）：**
- 不要在脚本输出之外的章节添加图片
- 不要因为"某个章节看起来需要图片"就添加图片
- 不要移动或调整占位符的位置
- 严格按照脚本返回的内容生成文件
- 不要根据"图片应该在哪里"来决定位置，脚本输出就是真相

模板详见 `references/templates.md`，图片位置处理详见 `references/image-placement.md`。

### 第六步：验证并更新目录索引

**验证清单**（在更新目录索引前检查）：
1. 图片数量是否与 `extract_images.js` 返回的数量一致
2. 图片顺序是否与脚本返回的顺序一致
3. 是否有脚本输出之外的图片被添加
4. 每张图片的描述是否根据上下文生成（非通用描述）

**更新目录索引**：将文章链接指向本地文件，状态标记为 `✅ 已采集`，更新 `collected` 计数。

## 重新采集

当需要重新采集已存在的文章时：

1. 重新执行 `extract_content.js` 获取最新内容和图片位置（不要复用旧文件）
2. URL 映射表仅用于**去重**（避免重复下载已存在的图片），不用于确定图片位置
3. 严格按照当前脚本输出生成新的 Markdown 文件，覆盖旧文件

## 防反爬虫策略

使用 camofox-browser 后，反爬虫能力大幅提升：

- **C++ 级指纹伪装**：Camoufox 在浏览器引擎层面伪装硬件参数、WebGL、AudioContext、屏幕信息等，无需 JS 层面的 stealth 插件
- **真实浏览器行为**：Camoufox 基于 Firefox，不是 Chromium headless，指纹特征与真实用户一致

但仍建议保持以下频率控制：

**核心原则**：
1. 控制请求频率 — 每篇文章间隔 3-8 秒
2. 限制批量大小 — 每批次最多 5 篇，批次间休息 30-60 秒
3. 复用浏览器会话 — 同批次内不要反复开关 tab

完整配置和异常处理流程见 `references/anti-crawling.md`。

## 批量采集策略

- 每批次 5 篇，控制采集频率
- 批次间等待用户确认再继续，模拟休息 30-60 秒
- **断点续采**：中断后读取目录索引，从第一个 `待采集` 文章继续
- 每完成一篇立即更新目录索引状态
- 遇到验证码或异常响应时，立即停止并等待用户处理

## 样式保留说明

| 微信样式 | Markdown 格式 | 触发条件 |
|----------|---------------|----------|
| **加粗** | `**text**` | `<strong>`/`<b>` 或 font-weight: bold |
| *斜体* | `*text*` | `<em>`/`<i>` 或 font-style: italic |
| ~~删除线~~ | `~~text~~` | `<s>`/`<strike>`/`<del>` 或 line-through |
| <u>下划线</u> | `<u>text</u>` | `<u>` 或 text-decoration: underline |
| 引用块 | `> text` | `<blockquote>` 或带左边框样式的元素 |

嵌套样式（如加粗+斜体）会按顺序应用，生成 `***text***`。

## 问题排查

遇到问题时参考 `references/troubleshooting.md`。
