function setRefreshButtonText(button, text) {
  const textNode = Array.from(button.childNodes).find(
    (node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim().startsWith('刷新'),
  );
  if (textNode) textNode.textContent = text;
}

function refreshTable() {
  const btn = document.getElementById('refresh-btn');
  const icon = document.getElementById('refresh-icon');
  if (!btn || !icon) return;

  btn.classList.add('pointer-events-none', 'opacity-50');
  icon.classList.add('animate-spin');
  setRefreshButtonText(btn, '刷新中...');

  fetch('/api-keys?fragment=1')
    .then((response) => {
      if (!response.ok) throw new Error(String(response.status));
      return response.text();
    })
    .then((html) => {
      const oldTable = document.getElementById('api-keys-table');
      const doc = new DOMParser().parseFromString(html, 'text/html');
      const newTable = doc.querySelector('#api-keys-table');
      if (newTable && oldTable) {
        newTable.classList.add('opacity-0', 'transition-opacity', 'duration-200');
        oldTable.parentNode.replaceChild(newTable, oldTable);
        requestAnimationFrame(() => {
          newTable.classList.remove('opacity-0');
          newTable.classList.add('opacity-100');
        });
      } else {
        location.reload();
      }
    })
    .catch(() => location.reload())
    .finally(() => {
      btn.classList.remove('pointer-events-none', 'opacity-50');
      icon.classList.remove('animate-spin');
      setRefreshButtonText(btn, '刷新');
    });
}

document.getElementById('refresh-btn')?.addEventListener('click', refreshTable);
