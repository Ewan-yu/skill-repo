# 模板参考

## 目录索引模板

在系列文件夹的**上级目录**创建 `系列名_目录索引.md`：

```markdown
---
title: 系列名 - 来源系列文章目录
source: 微信公众号
author: 作者名
created: YYYY-MM-DD
updated: YYYY-MM-DD
collected: 0/总数
total: 总数
tags:
  - 标签1
  - 标签2
---

# 系列名 - 来源系列文章目录

> **来源**: [公众号名称 - 系列名称](合集URL)
> **简介**: 系列简介
> **总篇数**: N 篇
> **采集时间**: YYYY-MM-DD

---

## 年份分组

| 序号 | 文章标题 | 发布日期 | 采集状态 |
|------|----------|----------|----------|
| 1 | [文章标题](系列文件夹/文章文件名.md) | YYYY-MM-DD | ✅ 已采集 |
```

## 文章 Markdown 模板

```markdown
---
title: 文章标题
source: 微信公众号
author: 作者名
created: YYYY-MM-DD
collected: YYYY-MM-DD
series: 系列名
series_index: 序号
original_url: 原文链接
tags:
  - 标签1
  - 标签2
---

# 文章标题

正文内容...

![图片描述](assets/序号_拼音首字母/img01.png)

更多正文...

---

## 相关链接

- [原文链接](URL)
- [[系列名_目录索引|返回目录]]
```

## 脚本返回格式

所有脚本均返回 JSON 格式：

### extract_content.js

```json
{
  "content": "正文内容...\n\n[IMG_1]\n\n更多内容...\n\n[IMG_2]\n\n结尾...",
  "imgCount": 2
}
```

- `content`：包含 `[IMG_N]` 占位符的文本内容
- `imgCount`：图片总数，用于验证

### extract_images.js

```json
{
  "images": [
    { "index": 1, "src": "https://mmbiz.qpic.cn/...", "alt": "" },
    { "index": 2, "src": "https://mmbiz.qpic.cn/...", "alt": "" }
  ],
  "count": 2
}
```

### extract_metadata.js

```json
{
  "title": "文章标题",
  "author": "作者名",
  "date": "2024-01-01"
}
```

### extract_article_list.js

```json
{
  "articles": [
    { "index": 1, "title": "文章标题", "url": "https://mp.weixin.qq.com/s/...", "date": "2024-01-01" }
  ],
  "count": 5
}
```

## URL 映射表格式

构建 `window.__urlMap` 注入到页面，用于跨文章链接识别和 Obsidian 双链生成：

```bash
# 将映射表保存为 JSON 文件后，通过 adapter 的 --url-map 参数注入
python3 scripts/camofox_adapter.py eval $TAB_ID scripts/extract_content.js --url-map urlmap.json
```

**映射规则**：
- 已采集的文章 → `[[文章标题]]`（Obsidian 双链）
- 未采集的文章 → `[链接文字](原始URL)`（标准 Markdown 链接）

## 占位符替换规则

**核心原则**：脚本返回的 `[IMG_N]` 占位符位置就是图片在原文中的正确位置，必须严格按照这个顺序和位置替换，不要自行添加或移动任何图片。

| 占位符 | 替换为 |
|--------|--------|
| `[IMG_1]` | `![img01](assets/序号_拼音首字母/img01.png)` |
| `[IMG_2]` | `![img02](assets/序号_拼音首字母/img02.png)` |
| 以此类推 | 以此类推 |

**图片描述生成规则**：
根据图片上下文生成有意义的描述：
- 表格截图 → "XX数据表"
- 走势图 → "XX走势对比"
- 产品图 → "产品名称"
- 架构图 → "XX架构示意图"
- 人物图 → "人物姓名"

**替换示例**：

原始脚本输出（JSON content 字段）：
```
正文内容...

[IMG_1]

更多正文内容...

[IMG_2]

结尾内容...
```

替换后：
```
正文内容...

![数据表格](assets/01_wenzhangming/img01.png)

更多正文内容...

![走势图](assets/01_wenzhangming/img02.png)

结尾内容...
```

**常见错误（必须避免）**：
- 不要在脚本输出之外的章节添加图片
- 不要移动或调整占位符的位置
- 不要合并或拆分占位符
- 严格按照脚本返回的内容生成文件
