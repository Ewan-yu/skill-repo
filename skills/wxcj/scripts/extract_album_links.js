(() => {
  const links = document.querySelectorAll('[role=option] a, li a');
  const results = [];
  for (const link of links) {
    const href = link.href || link.getAttribute('href');
    const text = link.innerText || link.textContent;
    if (href && text) results.push({text: text.substring(0,80), href: href});
  }
  return results.slice(0,5);
})()
