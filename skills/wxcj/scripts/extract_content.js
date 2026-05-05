// 微信公众号文章内容提取脚本
// 用法：agent-browser eval --stdin < scripts/extract_content.js
// 需要先设置 urlMap 变量（从目录索引文件构建）

(async function() {
  const el = document.querySelector("#js_content");
  if (!el) return "No content found";

  // URL映射表（在实际使用时应从目录索引文件动态构建）
  // 格式：URL -> 本地文件路径（不含.md后缀）
  // 示例：
  // const urlMap = {
  //   "http://mp.weixin.qq.com/s?__biz=xxx&mid=xxx": "系列名/01_文章名",
  //   "http://mp.weixin.qq.com/s?__biz=xxx&mid=xxx": "系列名/02_文章名"
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
    if (prefix && text && isCJK(text[0]) && !prefix.endsWith(' ')) r = prefix + ' ' + text + suffix;
    if (suffix && text && isCJK(text[text.length - 1]) && !suffix.startsWith(' ')) r = prefix + text + ' ' + suffix;
    return r;
  }

  function walk(node, fmt) {
    if (node.nodeType === 3) {
      const t = node.textContent;
      if (t.trim()) {
        let text = t;
        if (inBlockquote) {
          text = "> " + text.replace(/\n/g, "\n> ");
        }
        if (fmt.strike) text = addFmtSpaced("~~", text, "~~");
        if (fmt.underline) text = addFmtSpaced("<u>", text, "</u>");
        if (fmt.italic) text = addFmtSpaced("*", text, "*");
        if (fmt.bold) text = addFmtSpaced("**", text, "**");
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

        let finalHref = href;
        const hrefMid = href.match(/mid=(\d+)/)?.[1];

        if (hrefMid) {
          for (const [mapUrl, localPath] of Object.entries(urlMap)) {
            const mapMid = mapUrl.match(/mid=(\d+)/)?.[1];
            if (mapMid && hrefMid === mapMid) {
              finalHref = localPath;
              break;
            }
          }
        }

        if (inBlockquote) {
          result += "> " + prefix + "[" + linkText + "](" + finalHref + ")" + suffix;
        } else {
          result += prefix + "[" + linkText + "](" + finalHref + ")" + suffix;
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

  walk(el, {});

  result = result.replace(/\n{3,}/g, "\n\n").replace(/^\n+/, '').trim();

  return result;
})();
