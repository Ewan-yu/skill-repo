// 提取文章元数据（标题、作者、日期）
// 用法：agent-browser eval --stdin < scripts/extract_metadata.js

JSON.stringify({
  title: document.querySelector("#activity-name")?.textContent?.trim(),
  author: document.querySelector("#js_name")?.textContent?.trim(),
  date: document.querySelector("#publish_time")?.textContent?.trim()
})
