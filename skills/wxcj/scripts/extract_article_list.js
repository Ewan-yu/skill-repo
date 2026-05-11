// 提取合集/专辑页面的文章列表
// 用法：python3 scripts/camofox_adapter.py eval $TAB_ID scripts/extract_article_list.js
//
// 合集页面结构：每个文章是 <li> 元素，包含 data-link、data-title、data-msgid 属性
// 示例：
// <li class="album__list-item js_album_item"
//     data-msgid="2650320567"
//     data-link="http://mp.weixin.qq.com/s?__biz=xxx&mid=xxx&idx=1&sn=xxx"
//     data-title="文章标题"
//     data-is_read="0">

(function() {
  try {
    // 方式1：使用 data-link 属性选择器（最可靠）
    let items = Array.from(document.querySelectorAll('li[data-link]'));

    // 方式2：备选选择器
    if (items.length === 0) {
      items = Array.from(document.querySelectorAll('.album__list-item[data-link]'));
    }

    // 方式3：更宽泛的备选
    if (items.length === 0) {
      items = Array.from(document.querySelectorAll('[data-link][data-title]'));
    }

    if (items.length === 0) {
      return JSON.stringify({
        error: "未找到文章列表，页面结构可能已变化",
        hint: "请确认链接是合集/专辑页面，或检查选择器是否需要更新",
        articles: [],
        html_sample: document.querySelector('ul, ol, .album')?.innerHTML?.substring(0, 500) || ""
      });
    }

    const articles = items.map((item, i) => {
      // 从 data-link 属性提取 URL（注意 HTML 实体编码 &amp; -> &）
      let url = item.getAttribute('data-link') || '';
      url = url.replace(/&amp;/g, '&');

      // 从 data-title 属性提取标题
      const title = item.getAttribute('data-title') || '';

      // 从 data-msgid 属性提取消息 ID（可用于去重）
      const msgid = item.getAttribute('data-msgid') || '';

      // 从 data-itemidx 属性提取序号（如果有）
      const itemIdx = item.getAttribute('data-itemidx') || (i + 1).toString();

      return {
        index: parseInt(itemIdx),
        title: title,
        url: url,
        msgid: msgid
      };
    }).filter(a => a.title && a.url);

    return JSON.stringify({
      articles: articles,
      count: articles.length,
      method: "data-link-attribute"
    });
  } catch(e) {
    return JSON.stringify({ error: e.message, articles: [] });
  }
})();
