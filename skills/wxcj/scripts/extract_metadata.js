// 提取文章元数据（标题、作者、日期）
// 用法：python3 scripts/camofox_adapter.py eval $TAB_ID scripts/extract_metadata.js

(function() {
  try {
    const title = document.querySelector("#activity-name")?.textContent?.trim()
      || document.querySelector(".rich_media_title")?.textContent?.trim()
      || document.querySelector("h1")?.textContent?.trim()
      || "";

    const author = document.querySelector("#js_name")?.textContent?.trim()
      || document.querySelector(".rich_media_meta_nickname")?.textContent?.trim()
      || "";

    const date = document.querySelector("#publish_time")?.textContent?.trim()
      || document.querySelector(".rich_media_meta_date")?.textContent?.trim()
      || "";

    if (!title) {
      return JSON.stringify({ error: "未能提取标题，页面结构可能已变化", title, author, date });
    }

    return JSON.stringify({ title, author, date });
  } catch(e) {
    return JSON.stringify({ error: e.message, title: "", author: "", date: "" });
  }
})();
