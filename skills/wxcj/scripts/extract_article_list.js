// 提取合集/专辑页面的文章列表
// 用法：agent-browser eval --stdin < scripts/extract_article_list.js

JSON.stringify(
  Array.from(document.querySelectorAll(".album__item, .weui_media_box"))
    .map((item, i) => ({
      index: i + 1,
      title: item.querySelector(".weui_media_title, .album__item_title")?.textContent?.trim(),
      url: item.querySelector("a")?.href,
      date: item.querySelector(".weui_media_extra, .album__item_date")?.textContent?.trim()
    }))
)
