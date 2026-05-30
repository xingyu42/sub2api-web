const trendData = JSON.parse(document.getElementById('trend-data')?.innerHTML || '{}');
const modelData = JSON.parse(document.getElementById('model-data')?.innerHTML || '{}');
const CHART_JS_SRC = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.6/dist/chart.umd.min.js';

function loadChartJs() {
  if (window.Chart) return Promise.resolve();

  const existing = document.querySelector(`script[src="${CHART_JS_SRC}"]`);
  if (existing) {
    return new Promise((resolve, reject) => {
      existing.addEventListener('load', resolve, { once: true });
      existing.addEventListener('error', reject, { once: true });
    });
  }

  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = CHART_JS_SRC;
    script.async = true;
    script.onload = resolve;
    script.onerror = reject;
    document.head.appendChild(script);
  });
}

(function initDashboardCharts() {
  loadChartJs().then(() => {
    renderTrend();
    renderModels();
  }).catch(() => {
    document.querySelectorAll('canvas').forEach((canvas) => {
      canvas.parentElement.innerHTML = '<div class="text-center text-slate-500 py-8 text-sm">图表加载失败</div>';
    });
  });
})();

function renderTrend() {
  const ctx = document.getElementById('trendChart');
  const series = (trendData && (trendData.trend || trendData.items || trendData.data)) || [];
  const labels = series.map(p => p.date || p.time || p.bucket || '');
  const tokens = series.map(p => p.total_tokens ?? p.tokens ?? 0);
  const cost = series.map(p => p.total_cost ?? p.cost ?? 0);

  new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Token',
          data: tokens,
          borderColor: '#3b82f6',
          backgroundColor: 'rgba(59,130,246,0.1)',
          borderWidth: 2,
          tension: 0.4,
          fill: true,
          yAxisID: 'y'
        },
        {
          label: '费用 ($)',
          data: cost,
          borderColor: '#f59e0b',
          backgroundColor: 'rgba(245,158,11,0.1)',
          borderWidth: 2,
          tension: 0.4,
          fill: true,
          yAxisID: 'y1'
        },
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          labels: {
            font: { size: 12, weight: '500' },
            color: '#475569',
            usePointStyle: true,
            padding: 16
          }
        },
        tooltip: {
          backgroundColor: 'rgba(15, 23, 42, 0.9)',
          padding: 12,
          titleFont: { size: 13, weight: '600' },
          bodyFont: { size: 12 },
          borderColor: 'rgba(148, 163, 184, 0.2)',
          borderWidth: 1
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          position: 'left',
          grid: { color: '#f1f5f9' },
          ticks: { color: '#64748b', font: { size: 11 } }
        },
        y1: {
          beginAtZero: true,
          position: 'right',
          grid: { drawOnChartArea: false },
          ticks: { color: '#64748b', font: { size: 11 } }
        },
        x: {
          grid: { display: false },
          ticks: { color: '#64748b', font: { size: 11 }, maxRotation: 0, autoSkip: true, maxTicksLimit: 7 }
        }
      }
    }
  });
}

function renderModels() {
  const ctx = document.getElementById('modelChart');
  const items = Array.isArray(modelData)
    ? modelData
    : (modelData && (modelData.items || modelData.models || modelData.stats)) || [];
  const top = items.slice(0, 8);

  new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: top.map(m => m.model || m.name || '未知'),
      datasets: [{
        data: top.map(m => m.total_tokens ?? m.tokens ?? m.requests ?? 0),
        backgroundColor: [
          '#3b82f6', '#f59e0b', '#10b981', '#a855f7',
          '#eab308', '#ef4444', '#6366f1', '#14b8a6'
        ],
        borderWidth: 0,
        hoverOffset: 8
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            boxWidth: 12,
            boxHeight: 12,
            font: { size: 11, weight: '500' },
            color: '#475569',
            padding: 12,
            usePointStyle: true
          }
        },
        tooltip: {
          backgroundColor: 'rgba(15, 23, 42, 0.9)',
          padding: 12,
          titleFont: { size: 13, weight: '600' },
          bodyFont: { size: 12 },
          borderColor: 'rgba(148, 163, 184, 0.2)',
          borderWidth: 1
        }
      }
    }
  });
}
