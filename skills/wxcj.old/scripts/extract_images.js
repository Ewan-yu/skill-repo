// 提取文章中所有图片的真实 URL
// 用法：agent-browser eval --stdin < scripts/extract_images.js

(function() {
  try {
    const content = document.querySelector("#js_content");
    if (!content) return JSON.stringify({ error: "No #js_content found", images: [] });

    const images = Array.from(content.querySelectorAll("img"))
      .filter(img => {
        const src = img.getAttribute("data-src") || img.src;
        return src && src.includes("mmbiz.qpic.cn");
      })
      .map((img, i) => ({
        index: i + 1,
        src: img.getAttribute("data-src") || img.src,
        alt: img.alt || ""
      }));

    return JSON.stringify({ images: images, count: images.length });
  } catch(e) {
    return JSON.stringify({ error: e.message, images: [] });
  }
})();
