document.addEventListener('click', (event) => {
  const row = event.target.closest('.js-clickable-row');
  if (row?.dataset.href) window.location.href = row.dataset.href;
});
