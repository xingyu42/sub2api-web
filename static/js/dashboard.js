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

(function renderTrend() {
  const ctx = document.getElementById('trendChart');
  if (!ctx || typeof Chart === 'undefined') return;

  const trendData = readJsonData('trend-data', null);
  const series = (trendData && (trendData.trend || trendData.items || trendData.data)) || [];
  const labels = series.map((p) => p.date || p.time || p.bucket || '');
  const tokens = series.map((p) => p.total_tokens ?? p.tokens ?? 0);
  const cost = series.map((p) => p.total_cost ?? p.cost ?? 0);

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

(function renderModels() {
  const ctx = document.getElementById('modelChart');
  if (!ctx || typeof Chart === 'undefined') return;

  const modelData = readJsonData('model-data', []);
  const items = Array.isArray(modelData)
    ? modelData
    : (modelData && (modelData.items || modelData.models || modelData.stats)) || [];
  const top = items.slice(0, 8);

  new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: top.map((m) => m.model || m.name || '未知'),
      datasets: [{
        data: top.map((m) => m.total_tokens ?? m.tokens ?? m.requests ?? 0),
        backgroundColor: ['#0ea5e9', '#f97316', '#10b981', '#a855f7', '#eab308', '#ef4444', '#6366f1', '#14b8a6'],
      }],
    },
    options: { plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 11 } } } } },
  });
})();
