/**
 * MediPulse OS - Componente: gráfico determinista dentro del chat del asistente.
 * Recibe `datos_grafico` y `tipo_grafico` del backend y los dibuja con Chart.js (ya cargado por index.html).
 * Sin IA: el backend (chart_builder.py) elige el tipo con reglas sobre las filas reales de la consulta.
 * El usuario puede cambiar entre barras, líneas y dona cuando los datos lo permiten.
 */

window.MediPulse = window.MediPulse || {};

MediPulse.ChatChart = {
  LABEL_KEY: 'etiqueta',
  TYPES: ['bar', 'pie', 'line', 'gauge'],
  MAX_PIE_SLICES: 8,
  TYPE_NAMES: { bar: 'Barras', line: 'Líneas', pie: 'Dona' },
  TYPE_ICONS: { bar: 'bar-chart-3', line: 'trending-up', pie: 'pie-chart' },
  // Paleta categórica validada (separación para daltonismo); orden fijo, nunca cíclico
  palette: ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7', '#e34948'],
  gaugeTrack: '#e2e8f0',

  /** True si la respuesta trae un gráfico dibujable. */
  isRenderable(type, points) {
    return this.TYPES.includes(type) && Array.isArray(points) && points.length > 0 && typeof Chart !== 'undefined';
  },

  /** Series = claves de los puntos distintas de "etiqueta", en el orden en que aparecen. */
  seriesOf(points) {
    const keys = [];
    points.forEach(point => Object.keys(point).forEach(key => {
      if (key !== this.LABEL_KEY && !keys.includes(key)) keys.push(key);
    }));
    return keys.slice(0, this.palette.length);
  },

  /** Tipos a los que el usuario puede cambiar sin engañar: dona solo con una serie, pocas porciones y sin negativos. */
  alternatives(type, points) {
    if (type === 'gauge' || points.length < 2) return [];
    const series = this.seriesOf(points);
    const pieOk = series.length === 1 && points.length <= this.MAX_PIE_SLICES
      && points.every(p => typeof p[series[0]] === 'number' && p[series[0]] >= 0);
    const options = ['bar', 'line', ...(pieOk ? ['pie'] : [])];
    return options.includes(type) ? options : [];
  },

  /** Marcado del contenedor; el canvas se llena con mount() cuando ya está en el DOM (Chart.js necesita su tamaño). */
  shell(type, points = []) {
    const height = type === 'gauge' ? 'h-44' : (type === 'pie' ? 'h-64' : 'h-60');
    const options = this.alternatives(type, points);
    const switcher = options.length > 1 ? `
        <div class="flex justify-end gap-1 mb-2" role="group" aria-label="Tipo de gráfico">
          ${options.map(t => `
          <button type="button" data-chart-type="${t}" aria-pressed="${t === type}" title="${this.TYPE_NAMES[t]}"
            class="ai-chart-type px-2 py-1 rounded-md text-[10px] font-bold flex items-center gap-1 border transition-colors">
            <i data-lucide="${this.TYPE_ICONS[t]}" class="w-3 h-3"></i>${this.TYPE_NAMES[t]}
          </button>`).join('')}
        </div>` : '';
    return `
      <div class="ai-chart rounded-xl border border-slate-200 bg-white p-3">
        ${switcher}
        <div class="ai-chart-canvas relative ${height}"><canvas aria-label="Gráfico de los resultados" role="img"></canvas></div>
        <p class="text-[10px] text-slate-400 mt-1.5">Gráfico generado con los datos de la tabla, sin IA.</p>
      </div>`;
  },

  /** Marca el botón activo del selector. */
  paintSwitcher(container, type) {
    container.querySelectorAll('[data-chart-type]').forEach(button => {
      const active = button.dataset.chartType === type;
      button.setAttribute('aria-pressed', String(active));
      button.classList.toggle('bg-secondary', active);
      button.classList.toggle('text-white', active);
      button.classList.toggle('border-secondary', active);
      button.classList.toggle('bg-white', !active);
      button.classList.toggle('text-slate-500', !active);
      button.classList.toggle('border-slate-200', !active);
    });
  },

  /**
   * Dibuja el gráfico y conecta el selector de tipo. onChange(chartAnterior, chartNuevo) permite
   * a la vista llevar la cuenta de las instancias para destruirlas al limpiar el chat.
   */
  mountInto(container, type, points, onChange = () => {}) {
    const canvasBox = container.querySelector('.ai-chart-canvas');
    let chart = this.mount(container.querySelector('canvas'), type, points);
    this.paintSwitcher(container, type);
    container.querySelectorAll('[data-chart-type]').forEach(button => {
      button.onclick = () => {
        const next = button.dataset.chartType;
        if (chart.config.type === next || (next === 'pie' && chart.config.type === 'doughnut')) return;
        const previous = chart;
        previous.destroy();
        canvasBox.classList.toggle('h-64', next === 'pie');
        canvasBox.classList.toggle('h-60', next !== 'pie');
        canvasBox.innerHTML = '<canvas aria-label="Gráfico de los resultados" role="img"></canvas>';
        chart = this.mount(canvasBox.querySelector('canvas'), next, points);
        this.paintSwitcher(container, next);
        onChange(previous, chart);
      };
    });
    return chart;
  },

  mount(canvas, type, points) {
    if (type === 'gauge') return this.mountGauge(canvas, points[0]);

    const series = this.seriesOf(points);
    const labels = points.map(p => String(p[this.LABEL_KEY] ?? '—'));
    const shortLabel = label => (label.length > 24 ? `${label.slice(0, 24)}…` : label);
    const multi = series.length > 1;
    const pie = type === 'pie';

    const datasets = pie
      ? [{
        label: series[0],
        data: points.map(p => p[series[0]]),
        backgroundColor: points.map((_, i) => this.palette[i % this.palette.length]),
        borderColor: '#ffffff',
        borderWidth: 2,
        hoverOffset: 6
      }]
      : series.map((name, i) => ({
        label: name,
        data: points.map(p => p[name]),
        backgroundColor: this.palette[i],
        borderColor: this.palette[i],
        borderWidth: type === 'line' ? 2 : 0,
        borderRadius: type === 'bar' ? 4 : 0,
        pointRadius: type === 'line' ? (points.length > 14 ? 0 : 4) : undefined,
        pointHoverRadius: 5,
        tension: 0.25,
        spanGaps: true
      }));

    // Barras horizontales si hay muchas categorías con nombres largos (se leen mejor)
    const horizontal = type === 'bar' && labels.length > 6 && labels.some(l => l.length > 12);
    const total = pie ? datasets[0].data.reduce((sum, v) => sum + (v || 0), 0) : 0;

    return new Chart(canvas, {
      type: pie ? 'doughnut' : type,
      data: { labels: labels.map(shortLabel), datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: horizontal ? 'y' : 'x',
        cutout: pie ? '55%' : undefined,
        interaction: type === 'line' ? { mode: 'index', intersect: false } : { mode: 'nearest', intersect: true },
        plugins: {
          legend: { display: pie || multi, position: 'bottom', labels: { boxWidth: 10, font: { size: 10 }, color: '#475569' } },
          tooltip: {
            callbacks: {
              title: items => labels[items[0].dataIndex],
              label: ctx => {
                const value = `${pie ? series[0] : ctx.dataset.label}: ${fmtNumber(ctx.raw, Number.isInteger(ctx.raw) ? 0 : 1)}`;
                return pie && total ? `${value} (${fmtNumber((ctx.raw / total) * 100, 1)}%)` : value;
              }
            }
          }
        },
        scales: pie ? {} : {
          [horizontal ? 'x' : 'y']: { beginAtZero: true, grid: { color: '#f1f5f9' }, ticks: { color: '#64748b', font: { size: 10 } },
            title: { display: !multi, text: series[0], color: '#64748b', font: { size: 10 } } },
          [horizontal ? 'y' : 'x']: { grid: { display: false }, ticks: { color: '#64748b', font: { size: 10 }, autoSkip: true, maxRotation: 45 } }
        }
      }
    });
  },

  /** Indicador semicircular 0-100 % para un KPI de una sola fila (ej. ocupación, cumplimiento). */
  mountGauge(canvas, point) {
    const value = Math.max(0, Math.min(100, Number(point.Valor) || 0));
    const label = String(point[this.LABEL_KEY] ?? '');
    const centerText = {
      id: 'gaugeCenter',
      afterDraw: chart => {
        const { ctx, chartArea } = chart;
        const x = (chartArea.left + chartArea.right) / 2;
        const y = chartArea.bottom - 6;
        ctx.save();
        ctx.textAlign = 'center';
        ctx.fillStyle = '#0f172a';
        ctx.font = '700 22px system-ui, sans-serif';
        ctx.fillText(`${fmtNumber(value, Number.isInteger(value) ? 0 : 1)}%`, x, y - 16);
        ctx.fillStyle = '#64748b';
        ctx.font = '500 11px system-ui, sans-serif';
        ctx.fillText(label.length > 32 ? `${label.slice(0, 32)}…` : label, x, y);
        ctx.restore();
      }
    };
    return new Chart(canvas, {
      type: 'doughnut',
      data: {
        labels: [label, 'Restante'],
        datasets: [{ data: [value, 100 - value], backgroundColor: [this.palette[0], this.gaugeTrack], borderWidth: 0 }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        rotation: -90,
        circumference: 180,
        cutout: '75%',
        plugins: {
          legend: { display: false },
          tooltip: { filter: item => item.dataIndex === 0, callbacks: { label: () => `${label}: ${fmtNumber(value, 1)}%` } }
        }
      },
      plugins: [centerText]
    });
  }
};
