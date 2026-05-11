(() => {
  const links = document.querySelectorAll('a[href]');
  const results = [];
  for (const link of links) {
    const href = link.getAttribute('href');
    const text = link.textContent.trim();
    if (href && href.includes('mp.weixin.qq.com') && text) {
      results.push({title: text.substring(0, 100), url: href});
    }
  }
  return results.slice(0, 10);
})()
