(() => {
  const items = document.querySelectorAll('.album__item');
  const results = [];
  for (const item of items) {
    const link = item.querySelector('a');
    if (link) {
      const title = item.querySelector('.album__item-title');
      const href = link.getAttribute('href');
      if (title && href) {
        results.push({title: title.textContent.trim(), url: href});
      }
    }
  }
  return results.slice(0, 5);
})()
