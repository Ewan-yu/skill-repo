// 提取文章中所有图片的真实 URL
// 用法：agent-browser eval --stdin < scripts/extract_images.js

JSON.stringify(
  Array.from(document.querySelectorAll("#js_content img"))
    .filter(img => {
      const src = img.getAttribute("data-src") || img.src;
      return src && src.includes("mmbiz.qpic.cn");
    })
    .map((img, i) => ({
      index: i + 1,
      src: img.getAttribute("data-src") || img.src
    }))
)
