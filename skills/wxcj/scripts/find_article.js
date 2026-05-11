(() => {
  const listItems = document.querySelectorAll('li');
  const results = [];
  for (const li of listItems) {
    const link = li.querySelector('a');
    if (link) {
      const href = link.getAttribute('href');
      const text = link.textContent.trim();
      if (href && text) {
        results.push({title: text.substring(0, 100), url: href});
      }
    }
  }
  return results.slice(0, 10);
})()
