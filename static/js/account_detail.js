(function () {
  const CHART_JS_SRC = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.6/dist/chart.umd.min.js';
  const statsTemplate = document.getElementById('stats-data');
  const canvas = document.getElementById('statsChart');
  const rawStatsText = statsTemplate?.innerHTML || '';
  const statsData = JSON.parse(rawStatsText);

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

  function normalizeStatsSeries(data) {
    if (Array.isArray(data)) return data;
    if (!data || typeof data !== 'object') return [];
    return data.history || data.data || data.items || data.stats || data.trend || [];
  }

  const series = normalizeStatsSeries(statsData);

  function renderChart() {
    const ctx = canvas;
    const labels = series.map(d => d.label || d.date || d.time || d.bucket || '');
    const requests = series.map(d => d.requests || 0);
    const tokens = series.map(d => d.total_tokens ?? d.tokens ?? 0);
    const cost = series.map(d => d.total_cost ?? d.cost ?? d.actual_cost ?? 0);

    new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [
          {
            label: '请求数',
            data: requests,
            borderColor: '#3b82f6',
            backgroundColor: 'rgba(59,130,246,0.1)',
            borderWidth: 2,
            tension: 0.4,
            fill: true,
            yAxisID: 'y'
          },
          {
            label: 'Token',
            data: tokens,
            borderColor: '#10b981',
            backgroundColor: 'rgba(16,185,129,0.1)',
            borderWidth: 2,
            tension: 0.4,
            fill: true,
            yAxisID: 'y1'
          },
          {
            label: '费用 ($)',
            data: cost,
            borderColor: '#f59e0b',
            backgroundColor: 'rgba(245,158,11,0.1)',
            borderWidth: 2,
            tension: 0.4,
            fill: true,
            yAxisID: 'y2'
          }
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
          y2: {
            beginAtZero: true,
            position: 'right',
            grid: { drawOnChartArea: false },
            ticks: { color: '#64748b', font: { size: 11 } }
          },
          x: {
            grid: { display: false },
            ticks: { color: '#64748b', font: { size: 11 } }
          }
        }
      }
    });
  }

  if (series.length > 0) {
    loadChartJs().then(renderChart).catch(() => {
      canvas.parentElement.innerHTML = '<div class="text-center text-slate-500 py-8 text-sm">图表加载失败</div>';
    });
  } else {
    const parent = canvas.parentElement;
    parent.innerHTML = '<div class="text-center text-slate-500 py-8 text-sm">暂无数据</div>';
  }
})();
