(() => {
  const allElements = document.querySelectorAll('*');
  const results = [];
  for (const el of allElements) {
    if (el.tagName === 'A' && el.href && el.href.includes('mp.weixin.qq.com')) {
      results.push({tag: el.tagName, href: el.href, text: el.textContent.substring(0, 50)});
    }
  }
  return results.slice(0, 10);
})()
