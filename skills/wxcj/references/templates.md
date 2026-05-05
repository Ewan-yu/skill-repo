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

## 占位符替换规则

| 占位符 | 替换为 |
|--------|--------|
| `[IMG_1]` | `![img01](assets/序号_拼音首字母/img01.png)` |
| `[IMG_2]` | `![img02](assets/序号_拼音首字母/img02.png)` |
| 以此类推 | 以此类推 |

**图片描述建议**：
- 根据图片上下文生成有意义的描述
- 表格截图 → "XX数据表"
- 走势图 → "XX走势对比"
