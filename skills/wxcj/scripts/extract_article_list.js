// 提取合集/专辑页面的文章列表
// 用法：python3 scripts/camofox_adapter.py eval $TAB_ID scripts/extract_article_list.js

(function() {
  try {
    // 尝试多种选择器以适配不同版本的合集页面
    const selectors = [
      ".album__item",
      ".weui_media_box",
      ".collection-list .weui_media_box",
      "[class*='album'] [class*='item']"
    ];

    let items = [];
    for (const sel of selectors) {
      items = Array.from(document.querySelectorAll(sel));
      if (items.length > 0) break;
    }

    if (items.length === 0) {
      return JSON.stringify({
        error: "未找到文章列表，页面结构可能已变化",
        hint: "请确认链接是合集/专辑页面，或检查选择器是否需要更新",
        articles: []
      });
    }

    const articles = items.map((item, i) => ({
      index: i + 1,
      title: item.querySelector(".weui_media_title, .album__item_title, [class*='title']")?.textContent?.trim() || "",
      url: item.querySelector("a")?.href || "",
      date: item.querySelector(".weui_media_extra, .album__item_date, [class*='date']")?.textContent?.trim() || ""
    })).filter(a => a.title && a.url);

    return JSON.stringify({ articles: articles, count: articles.length });
  } catch(e) {
    return JSON.stringify({ error: e.message, articles: [] });
  }
})();
