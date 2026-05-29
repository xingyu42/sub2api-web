function readJsonData(id, fallback = null) {
  const element = document.getElementById(id);
  if (!element) return fallback;
  try {
    const text = element.content ? element.content.textContent : element.textContent;
    return JSON.parse(text || 'null');
  } catch {
    return fallback;
  }
}

function replaceChartWithMessage(ctx, message) {
  const wrapper = ctx?.parentElement;
  if (!wrapper) return;
  wrapper.replaceChildren();
  const empty = document.createElement('div');
  empty.className = 'text-sm text-zinc-500';
  empty.textContent = message;
  wrapper.appendChild(empty);
}

(function renderStats() {
  const ctx = document.getElementById('statsChart');
  if (!ctx || typeof Chart === 'undefined') return;

  const statsData = readJsonData('stats-data', null);
  if (!statsData) {
    replaceChartWithMessage(ctx, '暂无统计数据');
    return;
  }

  const points = statsData.history || statsData.daily || statsData.points || statsData.items || statsData.trend || [];
  if (!points.length) {
    replaceChartWithMessage(ctx, '最近 30 天暂无用量');
    return;
  }

  const labels = points.map((p) => p.date || p.label || p.day || p.time || '');
  const tokens = points.map((p) => p.tokens ?? p.total_tokens ?? 0);
  const cost = points.map((p) => p.cost ?? p.total_cost ?? p.actual_cost ?? 0);

  new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        { label: 'Token', data: tokens, borderColor: '#0ea5e9', backgroundColor: 'rgba(14,165,233,.1)', yAxisID: 'y' },
        { label: '费用 ($)', data: cost, borderColor: '#f97316', backgroundColor: 'rgba(249,115,22,.1)', yAxisID: 'y1' },
      ],
    },
    options: {
      interaction: { mode: 'index', intersect: false },
      scales: {
        y: { beginAtZero: true, position: 'left' },
        y1: { beginAtZero: true, position: 'right', grid: { drawOnChartArea: false } },
      },
    },
  });
})();
