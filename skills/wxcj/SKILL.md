---
name: wxcj
description: 微信公众号文章采集工具。将微信公众号文章完整保存到本地 Obsidian 知识库，包括文字内容、配图本地化、样式保留（加粗、斜体、删除线、引用块等）。当用户提供微信公众号文章链接（mp.weixin.qq.com/s）、合集/专辑链接、或要求采集/保存/下载公众号文章、批量导出公众号内容时使用此 skill。支持单篇和批量采集，自动处理图片懒加载和 blob URL 问题，支持断点续采。
---

# 微信公众号文章采集 (wxcj)

将微信公众号文章采集并保存为 Obsidian 规范的 Markdown 文件，配图下载到本地，保留原文样式。

## 概览

```
wxcj/
├── SKILL.md                    # 本文件 - 工作流程说明
├── scripts/
│   ├── extract_content.js      # 文章内容提取（TreeWalker + 样式保留）
│   ├── extract_article_list.js # 合集文章列表提取
│   ├── extract_images.js       # 图片 URL 提取
│   └── extract_metadata.js     # 文章元数据提取
└── references/
    ├── templates.md            # 目录索引和文章 Markdown 模板
    └── troubleshooting.md      # 常见问题排查
```

## 核心工具

**agent-browser** — 所有浏览器操作优先使用 agent-browser。

## 工作流程

### 第一步：解析文章列表（如果是合集链接）

当用户提供合集/专辑链接时，使用提取脚本获取文章列表：

```bash
agent-browser open "<合集URL>" && agent-browser wait --load networkidle
```

滚动加载全部文章后，使用脚本提取：

```bash
agent-browser eval --stdin < scripts/extract_article_list.js
```

提取完成后关闭浏览器：`agent-browser close`

### 第二步：创建目录索引

在系列文件夹的**上级目录**创建 `系列名_目录索引.md`，模板详见 `references/templates.md`。

**断点续采逻辑**：如果目录索引已存在，读取它检查哪些文章状态为 `待采集`，从第一个待采集文章继续，跳过 `✅ 已采集` 的文章。

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
agent-browser open "<文章URL>" && agent-browser wait --load networkidle
```

滚动触发所有图片懒加载（每次滚动后随机等待 500-2000ms）：

```bash
agent-browser scroll down 1000 && agent-browser wait $((RANDOM % 1500 + 500))
agent-browser scroll down 1000 && agent-browser wait $((RANDOM % 1500 + 500))
agent-browser scroll down 1000 && agent-browser wait $((RANDOM % 1500 + 500))
agent-browser scroll down 1000 && agent-browser wait $((RANDOM % 1500 + 500))
agent-browser scroll down 2000 && agent-browser wait $((RANDOM % 2000 + 1000))
```

#### 4.2 构建 URL 映射表

在提取内容前，读取目录索引和已采集文章的 frontmatter，构建 `URL -> 本地文件路径` 映射表。将 `window.__urlMap` 注入到页面后，再执行提取脚本。

#### 4.3 提取文章内容

使用 TreeWalker 遍历 DOM，按文档顺序提取文本和图片，保留加粗、斜体、删除线、下划线和引用块格式。

```bash
agent-browser eval --stdin < scripts/extract_content.js
```

**返回结果**：文本内容直接返回，图片位置用 `[IMG_N]` 占位符标记。

#### 4.4 提取图片 URL 和元数据

```bash
agent-browser eval --stdin < scripts/extract_images.js
agent-browser eval --stdin < scripts/extract_metadata.js
```

#### 4.5 关闭浏览器并下载图片

```bash
agent-browser close
cd "系列名/assets/序号_拼音首字母"
curl -s -o img01.png "<图片URL>"
# 每张图片下载后随机等待 0.5-2 秒
sleep $(echo "scale=2; ($RANDOM % 1500 + 500) / 1000" | bc)
curl -s -o img02.png "<图片URL2>"
```

下载后验证文件大小（>0 字节）：`ls -la`

### 第五步：生成 Markdown 文件

将 `[IMG_N]` 占位符替换为实际图片路径，添加 frontmatter。模板和替换规则详见 `references/templates.md`。

### 第六步：更新目录索引

将文章链接指向本地文件，状态标记为 `✅ 已采集`，更新 `collected` 计数。

## 防反爬虫策略

微信公众号有反爬虫机制，频繁或规律性的请求会触发验证码或封禁。采集时必须遵循以下策略：

### 核心原则

1. **模拟真人行为** — 所有操作加入随机延迟，避免固定节奏
2. **控制请求频率** — 每篇文章间隔 3-8 秒，图片下载间隔 0.5-2 秒
3. **限制批量大小** — 每批次最多 5 篇，批次间休息 30-60 秒
4. **复用浏览器会话** — 同批次内不要反复开关浏览器

### 随机延迟实现

在 agent-browser 操作之间使用随机等待时间，不要用固定值：

```bash
# 示例：随机等待 3-8 秒（毫秒）
agent-browser wait $((RANDOM % 5000 + 3000))
```

### 详细策略和配置

完整的反爬虫配置、延迟参数、异常处理流程见 `references/anti-crawling.md`。

## 批量采集策略

- 每批次 5 篇，控制采集频率
- 批次间等待用户确认再继续，并模拟休息 30-60 秒
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
