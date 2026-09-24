/**
 * MediPulse OS - Vista: tablero de Business Intelligence (KPIs, tendencias y censo).
 * Solo presenta lo que devuelve MediPulse.DashboardService (GET /api/dashboard); no calcula KPIs.
 */

window.MediPulse = window.MediPulse || {};

// 2. VISTA 1: MOTOR DE BUSINESS INTELLIGENCE (BI) — datos reales de hospital.db
MediPulse.BI = {
  filters: { period: 'today', service: 'all' },
  charts: {},
  loading: false,
  pending: false,
  refreshTimer: null,
  palette: ['#1f4a2a', '#3b8070', '#9ed3a2', '#e11d48', '#f59e0b', '#3b82f6', '#8b5cf6', '#14b8a6', '#64748b', '#f97316'],

  applyFilters() {
    this.filters.period = document.getElementById('bi-filter-period').value;
    this.filters.service = document.getElementById('bi-filter-service').value;
    this.render();
  },

  startAutoRefresh() {
    clearInterval(this.refreshTimer);
    this.refreshTimer = setInterval(() => {
      if (MediPulse.Navigation.currentView === 'view-bi' && document.visibilityState === 'visible') {
        this.render({ silent: true });
      }
    }, MediPulse.Config.dashboardRefreshMs);
  },

  async render(options = {}) {
    if (this.loading) { this.pending = true; return; }
    this.loading = true;
    const section = document.getElementById('view-bi');
    if (!options.silent) section.classList.add('opacity-70');
    try {
      const data = await MediPulse.DashboardService.get(this.filters);
      this.paint(data);
    } catch (error) {
      MediPulse.UI.toast(`No se pudo cargar el dashboard: ${error.message}`, 'error');
    } finally {
      section.classList.remove('opacity-70');
      this.loading = false;
      if (this.pending) { this.pending = false; this.render({ silent: true }); }
    }
  },

  paint(d) {
    const k = d.kpis || {};
    const esc = MediPulse.UI.escape;

    // Encabezado: fecha de corte y origen de los datos
    const live = d.source !== 'mock';
    setText('bi-reference-date', `Datos al ${fmtDate(d.referenceDate)} · ${d.periodLabel || ''}${d.service && d.service !== 'all' ? ` · ${d.service}` : ''}`);
    const sourceBadge = document.getElementById('bi-source-badge');
    sourceBadge.textContent = live ? 'Datos en vivo · hospital.db' : 'Modo respaldo · datos simulados';
    sourceBadge.className = `px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${live ? 'bg-white/20' : 'bg-amber-400 text-amber-950'}`;
    this.syncServiceOptions(d.services || [], d.service || 'all');

    // 1. KPIs superiores
    setText('kpi-occupancy-rate', `${fmtNumber(k.occupancyRate, 1)}%`);
    setText('kpi-beds-ratio', `${fmtNumber(k.occupiedBeds)} de ${fmtNumber(k.totalBeds)} camas ocupadas`);
    setText('kpi-wait-time', k.avgWaitMinutes !== null && k.avgWaitMinutes !== undefined ? `${fmtNumber(k.avgWaitMinutes, 1)} min` : 'Sin datos');
    setText('kpi-wait-subtitle', `Triaje → atención · ${fmtNumber(k.waitPatients)} pacientes`);
    setText('kpi-surgery', `${fmtNumber(k.surgeriesPerformed)} / ${fmtNumber(k.surgeriesScheduled)}`);
    setText('kpi-surgery-subtitle', k.surgeryComplianceRate !== null && k.surgeryComplianceRate !== undefined
      ? `Realizadas vs programadas · ${fmtNumber(k.surgeryComplianceRate, 1)}%`
      : 'Realizadas vs programadas');
    setText('kpi-critical-count', fmtNumber(k.criticalMeds));
    setText('kpi-critical-subtitle', `${fmtNumber(k.medsUnder5Days)} con menos de 5 días de inventario`);

    // 2. Barras de capacidad (por servicio o, si hay filtro, por área del servicio)
    setText('bi-wards-subtitle', d.service && d.service !== 'all'
      ? `Detalle por área de ${d.service}`
      : 'Distribución de camas censables y operativas');
    const wardsContainer = document.getElementById('bi-wards-container');
    wardsContainer.innerHTML = (d.wards || []).map(w => {
      const pct = w.occupancyPct || 0;
      const colorBar = pct > 80 ? 'bg-rose-500' : (pct >= 50 ? 'bg-secondary' : 'bg-emerald-500');
      const alertText = pct > 80
        ? '<i data-lucide="alert-triangle" class="w-3 h-3 inline mr-0.5 text-amber-500"></i> Saturación Alta'
        : 'Nominal';
      return `
        <div>
          <div class="flex justify-between text-xs font-bold mb-1 gap-2">
            <span class="text-slate-800 truncate">${esc(w.wing)}</span>
            <span class="text-primary font-black shrink-0">${w.occupied} / ${w.total} (${pct}%)</span>
          </div>
          <div class="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden">
            <div class="h-2.5 rounded-full ${colorBar} transition-all duration-500" style="width: ${pct}%"></div>
          </div>
          <div class="flex justify-between text-[10px] text-slate-400 mt-1">
            <span>Libres: ${w.free}${w.unavailable ? ` · No disponibles: ${w.unavailable}` : ''}</span>
            <span class="flex items-center">${alertText}</span>
          </div>
        </div>
      `;
    }).join('') || '<p class="text-xs text-slate-400">Sin camas registradas para este filtro.</p>';

    setText('bi-last-sync', live
      ? `datos al ${fmtDate(d.referenceDate)}${d.lastSync ? ` · recalculado ${d.lastSync.slice(11, 16)}` : ''}`
      : 'sin conexión con hospital.db');
    document.getElementById('bi-system-status').innerHTML = live
      ? '<i data-lucide="check-circle-2" class="w-3.5 h-3.5 text-emerald-600"></i> Datos reales · hospital.db'
      : '<i data-lucide="alert-triangle" class="w-3.5 h-3.5 text-amber-500"></i> Modo respaldo (mockData.js)';

    // 3. Censo activo priorizado por triaje (anonimizado)
    const tColors = { 1: 'bg-rose-600 text-white', 2: 'bg-orange-500 text-white', 3: 'bg-amber-500 text-white', 4: 'bg-emerald-600 text-white', 5: 'bg-blue-600 text-white' };
    const urgentContainer = document.getElementById('bi-urgent-patients-list');
    urgentContainer.innerHTML = (d.urgentPatients || []).map(raw => {
      const p = MediPulse.Privacy.maskPatient(raw);
      return `
        <div class="py-2.5 flex items-center justify-between gap-2">
          <div class="flex items-center space-x-2.5 min-w-0">
            <span class="w-7 h-7 sm:w-8 sm:h-8 rounded-xl ${tColors[p.triageLevel] || 'bg-slate-500 text-white'} flex items-center justify-center font-black text-xs shrink-0 shadow-sm">
              T${p.triageLevel || '?'}
            </span>
            <div class="min-w-0">
              <p class="font-bold text-xs text-slate-800 truncate">${esc(p.name)}${String(p.name).includes(p.id) ? '' : ` <span class="text-[10px] text-slate-400 font-medium">${esc(p.id)}</span>`}</p>
              <p class="text-[10px] sm:text-[11px] text-slate-500 truncate max-w-[170px] sm:max-w-[220px]">${esc(p.diagnosis || 'Sin diagnóstico registrado')}</p>
            </div>
          </div>
          <div class="text-right shrink-0">
            <span class="text-[10px] font-bold text-secondary block">${esc(p.roomNumber || '')}</span>
            <span class="text-[9px] text-slate-400">${esc(p.department || '')}</span>
          </div>
        </div>
      `;
    }).join('') || '<p class="py-3 text-xs text-slate-400">No hay pacientes activos para este filtro.</p>';

    // 4. Gráficos
    this.renderCharts(d);
    lucide.createIcons();
  },

  syncServiceOptions(services, selected) {
    const select = document.getElementById('bi-filter-service');
    if (!services.length) return;
    const current = ['all', ...services].join('|');
    if (select.dataset.options !== current) {
      select.innerHTML = '<option value="all">Todos los Servicios</option>' +
        services.map(s => `<option value="${MediPulse.UI.escape(s)}">${MediPulse.UI.escape(s)}</option>`).join('');
      select.dataset.options = current;
    }
    select.value = services.includes(selected) ? selected : 'all';
  },

  makeChart(key, canvasId, config) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || typeof Chart === 'undefined') return;
    if (this.charts[key]) this.charts[key].destroy();
    this.charts[key] = new Chart(canvas, config);
  },

  renderCharts(d) {
    // Gráfico 1: Evolución de ocupación (línea) + ingresos por día (barras)
    const trend = d.occupancyTrend || { labels: [], occupancyPct: [], admissions: [] };
    setText('bi-trend-subtitle', `Ocupación estimada (%) e ingresos por día · últimos ${trend.windowDays || trend.labels.length} días`);
    this.makeChart('tendencia', 'chart-tendencia', {
      data: {
        labels: trend.labels,
        datasets: [
          {
            type: 'line', label: 'Ocupación (%)', data: trend.occupancyPct, yAxisID: 'y',
            borderColor: '#3b8070', backgroundColor: 'rgba(59, 128, 112, 0.12)', borderWidth: 3,
            tension: 0.35, fill: true, pointBackgroundColor: '#1f4a2a', pointRadius: trend.labels.length > 14 ? 0 : 3
          },
          {
            type: 'bar', label: 'Ingresos', data: trend.admissions, yAxisID: 'y1',
            backgroundColor: 'rgba(158, 211, 162, 0.55)', borderRadius: 4
          }
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
        plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 10 } } } },
        scales: {
          y: { beginAtZero: true, max: 100, title: { display: true, text: '% ocupación' }, grid: { borderDash: [4, 4] } },
          y1: { beginAtZero: true, position: 'right', grid: { display: false }, title: { display: true, text: 'Ingresos' } },
          x: { grid: { display: false } }
        }
      }
    });

    // Gráfico 2: Distribución por servicio (dona)
    const dist = d.serviceDistribution || { labels: [], values: [] };
    setText('bi-dist-subtitle', `Ingresos por servicio · ${d.periodLabel || 'periodo'}`);
    this.makeChart('distribucion', 'chart-distribucion', {
      type: 'doughnut',
      data: {
        labels: dist.labels,
        datasets: [{ data: dist.values, backgroundColor: dist.labels.map((_, i) => this.palette[i % this.palette.length]), borderWidth: 0 }]
      },
      options: {
        responsive: true, maintainAspectRatio: false, cutout: '65%',
        plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 10 } } } }
      }
    });

    // Gráfico 3: Stock crítico de medicamentos (barras)
    const meds = d.criticalMeds || [];
    setText('bi-meds-subtitle', d.source === 'mock'
      ? 'Stock actual frente al mínimo de seguridad (datos simulados)'
      : 'Stock actual frente al mínimo de seguridad · stock simulado a partir del consumo real');
    this.makeChart('medicamentos', 'chart-medicamentos', {
      type: 'bar',
      data: {
        labels: meds.map(m => (m.name.length > 22 ? `${m.name.substring(0, 22)}…` : m.name)),
        datasets: [
          { label: 'Stock actual', data: meds.map(m => m.stock), backgroundColor: meds.map(m => (m.status === 'Crítico' ? '#e11d48' : '#f59e0b')), borderRadius: 4 },
          { label: 'Stock mínimo', data: meds.map(m => m.minStock), backgroundColor: '#cbd5e1', borderRadius: 4 }
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 10 } } },
          tooltip: {
            callbacks: {
              title: items => meds[items[0].dataIndex].name,
              afterBody: items => {
                const m = meds[items[0].dataIndex];
                return m.daysOfInventory !== null && m.daysOfInventory !== undefined ? `Cobertura: ${fmtNumber(m.daysOfInventory, 1)} días` : '';
              }
            }
          }
        },
        scales: { y: { beginAtZero: true, grid: { borderDash: [4, 4] } }, x: { grid: { display: false } } }
      }
    });
  }
};
