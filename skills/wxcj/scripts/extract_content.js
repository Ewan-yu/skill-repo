// 微信公众号文章内容提取脚本
// 用法：python3 scripts/camofox_adapter.py eval $TAB_ID scripts/extract_content.js
// 如需 URL 映射表（Obsidian 双链）：
//   python3 scripts/camofox_adapter.py eval $TAB_ID scripts/extract_content.js --url-map urlmap.json

(async function() {
  const el = document.querySelector("#js_content");
  if (!el) return JSON.stringify({ error: "No content found", hint: "页面可能未加载完成或结构已变化" });

  // URL映射表：URL -> { path: 本地文件路径, title: 文章标题 }
  // 注入示例：window.__urlMap = {
  //   "http://mp.weixin.qq.com/s?__biz=xxx&mid=123": { path: "系列名/01_文章名", title: "文章标题" }
  // };
  const urlMap = window.__urlMap || {};

  let result = "";
  let imgIndex = 0;
  let inBlockquote = false;

  const blockTags = new Set(['P', 'DIV', 'SECTION', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'LI', 'PRE', 'TABLE', 'TR', 'TH', 'TD', 'UL', 'OL']);
  const headingTags = new Set(['H1', 'H2', 'H3', 'H4', 'H5', 'H6']);

  function getStyle(node) {
    if (node.nodeType !== 1) return null;
    try { return window.getComputedStyle(node); } catch(e) { return null; }
  }

  function hasStyle(node, prop, val) {
    const s = getStyle(node);
    return s && s[prop] && s[prop].includes(val);
  }

  function isBlockquote(node) {
    if (node.nodeType !== 1) return false;
    if (node.tagName === 'BLOCKQUOTE') return true;
    if (headingTags.has(node.tagName)) return false;
    const style = getStyle(node);
    if (style && style.borderLeftWidth && style.borderLeftWidth !== '0px' && style.borderLeftWidth !== 'medium') {
      return true;
    }
    return false;
  }

  function isCJK(ch) {
    if (!ch) return false;
    const code = ch.charCodeAt(0);
    return (code >= 0x4E00 && code <= 0x9FFF) || (code >= 0x3000 && code <= 0x303F) ||
           (code >= 0xFF00 && code <= 0xFFEF) || (code >= 0x2E80 && code <= 0x2EFF) ||
           (code >= 0x3400 && code <= 0x4DBF) || (code >= 0x20000 && code <= 0x2A6DF) ||
           (code >= 0x2A700 && code <= 0x2B73F) || (code >= 0x2B740 && code <= 0x2B81F) ||
           (code >= 0x2B820 && code <= 0x2CEAF) || (code >= 0xF900 && code <= 0xFAFF) ||
           (code >= 0x2F800 && code <= 0x2FA1F) || (code >= 0x30000 && code <= 0x3134F);
  }

  function addFmtSpaced(prefix, text, suffix) {
    let r = prefix + text + suffix;
    // 对于加粗格式（**），不添加空格
    if (prefix !== '**' && prefix !== '~~' && prefix !== '<u>') {
      if (prefix && text && isCJK(text[0]) && !prefix.endsWith(' ')) r = prefix + ' ' + text + suffix;
      if (suffix && text && isCJK(text[text.length - 1]) && !suffix.startsWith(' ')) r = prefix + text + ' ' + suffix;
    }
    return r;
  }

  // 检查文本是否主要是星号（乘法符号），不应该被处理为斜体
  function isAsteriskText(text) {
    if (!text) return false;
    const trimmed = text.trim();
    // 匹配：纯星号、星号+数字、数字+星号、星号+百分号等
    return /^[*×]\d*%?$/.test(trimmed) || /^\d*[*×]%?$/.test(trimmed);
  }

  function walk(node, fmt) {
    if (node.nodeType === 3) {
      const t = node.textContent;
      if (t.trim()) {
        let text = t;
        if (inBlockquote) {
          text = "> " + text.replace(/\n/g, "\n> ");
        }
        if (fmt.strike) text = addFmtSpaced(" ~~", text, "~~ ");
        if (fmt.underline) text = addFmtSpaced("<u>", text, "</u>");
        // 只有当文本不是星号（乘法符号）时才应用斜体格式
        if (fmt.italic && !isAsteriskText(text)) text = addFmtSpaced(" *", text, "* ");
        if (fmt.bold) text = addFmtSpaced(" **", text, "** ");
        result += text;
      }
      return;
    }

    if (node.nodeType !== 1) return;
    const tag = node.tagName;

    if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'NOSCRIPT') return;

    if (tag === 'IMG') {
      const src = node.getAttribute("data-src") || node.src;
      if (src && src.includes("mmbiz.qpic.cn")) {
        imgIndex++;
        if (inBlockquote) {
          result += "\n> \n> [IMG_" + imgIndex + "]\n> \n";
        } else {
          result += "\n\n[IMG_" + imgIndex + "]\n\n";
        }
      }
      return;
    }

    if (tag === 'A') {
      const href = node.getAttribute("href");
      if (href && href.includes("mp.weixin.qq.com")) {
        let prefix = "";
        if (result.endsWith("《")) {
          result = result.slice(0, -1);
          prefix = "《";
        }

        const prevResult = result;
        result = "";
        for (const child of node.childNodes) {
          walk(child, fmt);
        }
        const linkText = result.trim();
        result = prevResult;

        let suffix = "";
        const nextSibling = node.nextSibling;
        if (nextSibling && nextSibling.nodeType === 3 && nextSibling.textContent.startsWith("》")) {
          suffix = "》";
          nextSibling.textContent = nextSibling.textContent.substring(1);
        }

        // 查找 URL 映射，支持 Obsidian 双链
        const hrefMid = href.match(/mid=(\d+)/)?.[1];
        let isCollected = false;
        let linkOutput = "";

        if (hrefMid) {
          for (const [mapUrl, mapInfo] of Object.entries(urlMap)) {
            const mapMid = mapUrl.match(/mid=(\d+)/)?.[1];
            if (mapMid && hrefMid === mapMid) {
              // 已采集的文章 → Obsidian 双链 [[文件名|显示标题]]
              const title = typeof mapInfo === 'object' ? mapInfo.title : linkText;
              const path = typeof mapInfo === 'object' ? mapInfo.path : '';
              if (path) {
                linkOutput = "[[" + path + "|" + title + "]]";
              } else {
                linkOutput = "[[" + title + "]]";
              }
              isCollected = true;
              break;
            }
          }
        }

        if (!isCollected) {
          // 未采集的文章 → 标准 Markdown 链接
          linkOutput = "[" + linkText + "](" + href + ")";
        }

        if (inBlockquote) {
          result += "> " + prefix + linkOutput + suffix;
        } else {
          result += prefix + linkOutput + suffix;
        }
      }
      return;
    }

    if (tag === 'BR') {
      result += inBlockquote ? "\n> " : "\n";
      return;
    }
    if (tag === 'HR') {
      result += inBlockquote ? "\n> ---\n" : "\n---\n\n";
      return;
    }

    if (isBlockquote(node)) {
      if (result.length > 0 && !result.endsWith('\n')) {
        result += "\n";
      }
      inBlockquote = true;
    }

    const f = { ...fmt };
    if (tag === 'STRONG' || tag === 'B') f.bold = true;
    if (tag === 'EM' || tag === 'I') f.italic = true;
    if (tag === 'S' || tag === 'STRIKE' || tag === 'DEL') f.strike = true;
    if (tag === 'U') f.underline = true;

    if (hasStyle(node, 'fontWeight', 'bold') || hasStyle(node, 'fontWeight', '700')) f.bold = true;
    if (hasStyle(node, 'fontStyle', 'italic')) f.italic = true;
    if (hasStyle(node, 'textDecoration', 'line-through')) f.strike = true;
    if (hasStyle(node, 'textDecoration', 'underline')) f.underline = true;

    if (blockTags.has(tag)) {
      if (inBlockquote) {
        if (!result.endsWith('\n')) {
          result += "\n> ";
        }
      } else {
        if (result.length > 0 && !result.endsWith('\n')) {
          result += "\n";
        }
      }
    }

    for (const child of node.childNodes) {
      walk(child, f);
    }

    if (blockTags.has(tag)) {
      if (inBlockquote) {
        result += "\n> \n";
      } else {
        if (tag === 'P') {
          result += "\n\n";
        } else {
          if (result.length > 0 && !result.endsWith('\n')) {
            result += "\n";
          }
        }
      }
    }

    if (isBlockquote(node)) {
      inBlockquote = false;
      result += "\n";
    }
  }

  try {
    walk(el, {});
    result = result.replace(/\n{3,}/g, "\n\n").replace(/^\n+/, '').trim();
    return JSON.stringify({ content: result, imgCount: imgIndex });
  } catch(e) {
    return JSON.stringify({ error: e.message, hint: "DOM 结构可能已变化，请检查 extract_content.js 是否需要更新" });
  }
})();
