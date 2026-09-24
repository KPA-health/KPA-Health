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
  insightsEnd: null,          // fecha de análisis de alertas y causa raíz (null = fecha de referencia)
  insightsLoaded: false,
  lastData: null,             // último GET /api/dashboard pintado (lo usa "Exportar reporte")
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
    if (!this.insightsLoaded) this.renderInsights();   // una sola vez: el autorrefresco no recalcula alertas
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
    this.lastData = d;

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
    this.paintManagement(d);
    lucide.createIcons();
  },

  // 7. Indicadores de gestión del reto: espera por triage, especialidades, rotación y ocupación mensual
  paintManagement(d) {
    const esc = MediPulse.UI.escape;
    const k = d.kpis || {};
    const period = d.periodLabel || 'periodo';
    setText('kpi-avg-stay', k.avgLengthOfStayDays !== null && k.avgLengthOfStayDays !== undefined ? `${fmtNumber(k.avgLengthOfStayDays, 1)} días` : '—');
    setText('kpi-bed-turnover', k.bedTurnover !== null && k.bedTurnover !== undefined ? `${fmtNumber(k.bedTurnover, 2)} ingresos/cama` : '—');

    // Espera por nivel de triage (colores del triage: 1 rojo ... 5 azul)
    const triage = d.waitByTriage || [];
    const triageColors = { 1: '#e11d48', 2: '#f97316', 3: '#f59e0b', 4: '#059669', 5: '#2563eb' };
    setText('bi-triage-subtitle', `Minutos promedio de triage a primera atención · ${period}`);
    this.makeChart('esperaTriage', 'chart-espera-triage', {
      type: 'bar',
      data: {
        labels: triage.map(t => `Triage ${t.level}`),
        datasets: [{ label: 'Espera promedio (min)', data: triage.map(t => t.avgMinutes), backgroundColor: triage.map(t => triageColors[t.level] || '#64748b'), borderRadius: 4 }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { callbacks: { afterLabel: ctx => `${fmtNumber(triage[ctx.dataIndex].patients)} pacientes` } } },
        scales: { y: { beginAtZero: true, title: { display: true, text: 'minutos' } }, x: { grid: { display: false } } }
      }
    });

    // Especialidades más solicitadas (barras horizontales)
    const specialties = d.topSpecialties || [];
    setText('bi-specialties-subtitle', `Ingresos por especialidad principal · ${period}`);
    const shortName = name => (name.length > 26 ? `${name.substring(0, 26)}…` : name);
    this.makeChart('especialidades', 'chart-especialidades', {
      type: 'bar',
      data: {
        labels: specialties.map(s => shortName(s.specialty)),
        datasets: [{ label: 'Ingresos', data: specialties.map(s => s.admissions), backgroundColor: '#3b8070', borderRadius: 4 }]
      },
      options: {
        indexAxis: 'y', responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { callbacks: { title: items => specialties[items[0].dataIndex].specialty } } },
        scales: { x: { beginAtZero: true }, y: { ticks: { font: { size: 10 } } } }
      }
    });

    // Rotación de farmacia: mayor y menor consumo de 30 días
    const rotation = d.medicationRotation || { highest: [], lowest: [] };
    setText('bi-rotation-subtitle', rotation.totalItems
      ? `Unidades dispensadas en los últimos 30 días · ${fmtNumber(rotation.withoutMovement30d)} de ${fmtNumber(rotation.totalItems)} ítems sin movimiento`
      : 'Unidades dispensadas en los últimos 30 días');
    const rotationList = items => (items || []).map(m => `
      <div class="py-1.5 flex items-center justify-between gap-2 text-xs">
        <span class="text-slate-700 truncate" title="${esc(m.name)}">${esc(m.name)}</span>
        <span class="shrink-0 text-right">
          <span class="font-bold text-primary">${fmtNumber(m.units30d)}</span>
          ${m.rotationIndex !== null && m.rotationIndex !== undefined ? `<span class="block text-[10px] text-slate-400">${fmtNumber(m.rotationIndex, 1)}× stock/mes</span>` : ''}
        </span>
      </div>`).join('') || '<p class="text-xs text-slate-400">Sin datos</p>';
    document.getElementById('bi-rotation-high').innerHTML = rotationList(rotation.highest);
    document.getElementById('bi-rotation-low').innerHTML = rotationList(rotation.lowest);

    // Ocupación promedio mensual por servicio (tabla con color por nivel de ocupación)
    const monthly = d.monthlyOccupancy || { months: [], rows: [] };
    const monthNames = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
    const monthLabel = m => `${monthNames[Number(m.slice(5, 7)) - 1]} ${m.slice(2, 4)}`;
    const cellClass = v => (v === null || v === undefined ? 'text-slate-300'
      : v >= 85 ? 'bg-rose-100 text-rose-700 font-bold' : v >= 60 ? 'bg-amber-50 text-amber-700' : 'bg-emerald-50 text-emerald-700');
    document.getElementById('bi-monthly-occupancy').innerHTML = monthly.rows.length ? `
      <table class="w-full text-xs">
        <thead class="text-[10px] uppercase text-slate-500">
          <tr><th class="text-left p-1.5">Servicio</th>${monthly.months.map(m => `<th class="p-1.5 text-center">${monthLabel(m)}</th>`).join('')}</tr>
        </thead>
        <tbody>
          ${monthly.rows.map(r => `
          <tr class="border-t border-slate-100">
            <td class="p-1.5 font-semibold text-slate-700 whitespace-nowrap">${esc(r.service)}</td>
            ${r.values.map(v => `<td class="p-1.5 text-center rounded ${cellClass(v)}">${v === null || v === undefined ? '—' : `${fmtNumber(v, 0)}%`}</td>`).join('')}
          </tr>`).join('')}
        </tbody>
      </table>
      <p class="text-[10px] text-slate-400 mt-2">Rojo ≥ 85 % (saturación) · ámbar 60-85 % · verde &lt; 60 %</p>`
      : '<p class="text-xs text-slate-400">Sin histórico de ocupación.</p>';
  },

  // 5. Alertas e insights con fecha de análisis (GET /api/insights/briefing)
  async setAnalysisDate(end) {
    this.insightsEnd = end || null;
    const panelOpen = !document.getElementById('bi-rootcause-panel').classList.contains('hidden');
    await Promise.all([this.renderInsights(), panelOpen ? this.diagnoseWait(this.insightsEnd, { scroll: false }) : null]);
  },

  async renderInsights() {
    this.insightsLoaded = true;
    const list = document.getElementById('bi-insights-list');
    setText('bi-insights-headline', 'Revisando las alertas del hospital…');
    try {
      const data = await MediPulse.InsightsService.briefing(this.insightsEnd);
      document.getElementById('bi-insights-end').value = data.periodEnd || '';
      setText('bi-insights-headline', `${data.headline} Semana analizada: ${fmtDate(data.periodStart)} al ${fmtDate(data.periodEnd)}.`);
      list.innerHTML = (data.items || []).map(item => MediPulse.UI.alertCard(item, { detail: true })).join('')
        || '<p class="text-xs text-slate-400">No hay alertas activas para esta fecha.</p>';
    } catch (error) {
      setText('bi-insights-headline', `No se pudieron calcular las alertas: ${error.message}`);
      list.innerHTML = '';
    }
    lucide.createIcons();
  },

  // 6. Diagnóstico de causa raíz de la espera (GET /api/insights/wait-drivers)
  openDiagnosis(end = null) {
    if (MediPulse.Navigation.currentView !== 'view-bi') MediPulse.Navigation.switchView('view-bi');
    // Desde el chat llega la fecha del resumen: el dashboard se alinea a esa misma fecha
    if (end && end !== this.insightsEnd) {
      this.insightsEnd = end;
      this.renderInsights();
    }
    this.diagnoseWait(this.insightsEnd);
  },

  closeDiagnosis() {
    document.getElementById('bi-rootcause-panel').classList.add('hidden');
  },

  async diagnoseWait(end = null, { scroll = true } = {}) {
    const panel = document.getElementById('bi-rootcause-panel');
    panel.classList.remove('hidden');     // visible antes de dibujar: Chart.js necesita el tamaño real
    setText('bi-rootcause-period', 'Analizando…');
    try {
      this.paintDiagnosis(await MediPulse.InsightsService.waitDrivers(end || null));
    } catch (error) {
      setText('bi-rootcause-period', '');
      document.getElementById('bi-rootcause-summary').innerHTML =
        `<p class="text-rose-700">No se pudo calcular el diagnóstico: ${MediPulse.UI.escape(error.message)}</p>`;
    }
    if (scroll) panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    lucide.createIcons();
  },

  paintDiagnosis(d) {
    const esc = MediPulse.UI.escape;
    document.getElementById('bi-rootcause-end').value = d.periodEnd || '';
    setText('bi-rootcause-period', `Semana del ${fmtDate(d.periodStart)} al ${fmtDate(d.periodEnd)} frente a las 4 semanas anteriores · ${fmtNumber((d.patients || {}).current)} pacientes`);

    const [box, badge] = !d.significant
      ? ['bg-slate-50 border-slate-200', 'Sin cambio significativo']
      : (d.deltaMinutes > 0
        ? ['bg-rose-50 border-rose-200', `Subió ${fmtNumber(d.deltaMinutes, 1)} min`]
        : ['bg-emerald-50 border-emerald-200', `Bajó ${fmtNumber(Math.abs(d.deltaMinutes), 1)} min`]);
    document.getElementById('bi-rootcause-summary').innerHTML = `
      <div class="rounded-xl border ${box} p-3 sm:p-4 space-y-2">
        <div class="flex flex-wrap items-center gap-2 text-xs font-bold">
          <span class="text-slate-500">Espera promedio:</span>
          <span class="text-slate-800">${fmtNumber(d.baselineAvgMinutes, 1)} → ${fmtNumber(d.currentAvgMinutes, 1)} min</span>
          <span class="px-2 py-0.5 rounded-full bg-white border border-slate-200 text-[10px]">${badge}</span>
        </div>
        <p>${esc(d.summary)}</p>
        ${d.recommendation ? `
        <p class="font-semibold text-primary flex items-start gap-1.5">
          <i data-lucide="lightbulb" class="w-4 h-4 mt-0.5 shrink-0 text-amber-500"></i><span>${esc(d.recommendation)}</span>
        </p>` : ''}
      </div>`;

    document.getElementById('bi-rootcause-load').innerHTML = (d.shiftLoad || []).map(s => {
      const up = (s.changePct || 0) > 0;
      const change = s.changePct === null || s.changePct === undefined
        ? '—' : `${up ? '+' : ''}${fmtNumber(s.changePct, 1)}% vs ${fmtNumber(s.baselinePerDay, 1)}/día`;
      return `
        <div class="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-xs">
          <div><p class="font-bold text-slate-800">${esc(s.shift)}</p><p class="text-[10px] text-slate-400">${esc(s.hours)}</p></div>
          <div class="text-right">
            <p class="font-black text-primary">${fmtNumber(s.currentPerDay, 1)}/día</p>
            <p class="text-[10px] ${up ? 'text-rose-600' : 'text-emerald-600'}">${change}</p>
          </div>
        </div>`;
    }).join('');

    // Barras horizontales: aporte de cada segmento al cambio; el factor principal en rojo
    const drivers = (d.drivers || []).slice(0, 8);
    const direction = d.deltaMinutes >= 0 ? 1 : -1;
    const colors = drivers.map((x, i) => (d.significant && i === 0)
      ? '#e11d48'
      : (direction * x.contribution > 0 ? '#3b8070' : '#9ed3a2'));
    this.makeChart('rootcause', 'chart-rootcause', {
      type: 'bar',
      data: {
        labels: drivers.map(x => x.label),
        datasets: [{ label: 'Aporte (min)', data: drivers.map(x => x.contribution), backgroundColor: colors, borderRadius: 4 }]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: ctx => {
                const x = drivers[ctx.dataIndex];
                return [
                  `Aporte: ${fmtNumber(x.contribution, 2)} min (${x.type === 'mezcla' ? 'más pacientes' : 'esperaron más'})`,
                  `Espera: ${fmtNumber(x.baselineAvg, 0)} → ${fmtNumber(x.currentAvg, 0)} min`,
                  `Pacientes: ${fmtNumber(100 * x.baselineShare, 1)}% → ${fmtNumber(100 * x.currentShare, 1)}%`
                ];
              }
            }
          }
        },
        scales: { x: { title: { display: true, text: 'minutos de cambio en la espera promedio' } } }
      }
    });
  },

  // 8. Exportar reporte: CSV con los KPIs y los datos de cada gráfico, o PDF visual del tablero
  exportReport(format) {
    const menu = document.getElementById('bi-export-menu');
    if (menu) menu.open = false;
    if (!this.lastData) {
      MediPulse.UI.toast('Espere a que carguen los datos del dashboard', 'warning');
      return;
    }
    return format === 'pdf' ? this.exportPDF() : this.exportCSV();
  },

  exportCSV() {
    const d = this.lastData;
    const k = d.kpis || {};
    const trend = d.occupancyTrend || { labels: [], occupancyPct: [], admissions: [] };
    const dist = d.serviceDistribution || { labels: [], values: [] };
    const rotation = d.medicationRotation || { highest: [], lowest: [] };
    const monthly = d.monthlyOccupancy || { months: [], rows: [] };
    const sections = [
      {
        title: `Reporte KPA-Health · datos al ${fmtDate(d.referenceDate)} · ${d.periodLabel || ''} · ${d.service && d.service !== 'all' ? d.service : 'Todos los servicios'}`,
        headers: ['Indicador', 'Valor'],
        rows: [
          ['Ocupación de camas (%)', k.occupancyRate],
          ['Camas ocupadas', k.occupiedBeds],
          ['Camas totales', k.totalBeds],
          ['Espera promedio triaje a atención (min)', k.avgWaitMinutes],
          ['Pacientes con espera medida', k.waitPatients],
          ['Cirugías realizadas', k.surgeriesPerformed],
          ['Cirugías programadas', k.surgeriesScheduled],
          ['Cumplimiento quirúrgico (%)', k.surgeryComplianceRate],
          ['Medicamentos en stock crítico', k.criticalMeds],
          ['Medicamentos con menos de 5 días de inventario', k.medsUnder5Days],
          ['Estancia promedio (días)', k.avgLengthOfStayDays],
          ['Rotación de camas (ingresos/cama)', k.bedTurnover],
          ['Origen de los datos', d.source === 'mock' ? 'Datos simulados' : 'hospital.db']
        ]
      },
      { title: 'Capacidad por servicio', headers: ['Servicio', 'Ocupadas', 'Totales', 'Libres', 'No disponibles', 'Ocupación (%)'],
        rows: (d.wards || []).map(w => [w.wing, w.occupied, w.total, w.free, w.unavailable || 0, w.occupancyPct]) },
      { title: 'Tendencia de ocupación e ingresos', headers: ['Fecha', 'Ocupación (%)', 'Ingresos'],
        rows: trend.labels.map((label, i) => [label, trend.occupancyPct[i], trend.admissions[i]]) },
      { title: 'Ingresos por servicio', headers: ['Servicio', 'Ingresos'],
        rows: dist.labels.map((label, i) => [label, dist.values[i]]) },
      { title: 'Stock crítico de medicamentos', headers: ['Medicamento', 'Stock actual', 'Stock mínimo', 'Días de inventario', 'Estado'],
        rows: (d.criticalMeds || []).map(m => [m.name, m.stock, m.minStock, m.daysOfInventory, m.status]) },
      { title: 'Espera por nivel de triage', headers: ['Nivel de triage', 'Espera promedio (min)', 'Pacientes'],
        rows: (d.waitByTriage || []).map(t => [t.level, t.avgMinutes, t.patients]) },
      { title: 'Especialidades más solicitadas', headers: ['Especialidad', 'Ingresos'],
        rows: (d.topSpecialties || []).map(s => [s.specialty, s.admissions]) },
      { title: 'Rotación de farmacia (30 días)', headers: ['Grupo', 'Medicamento', 'Unidades dispensadas', 'Rotación (stock/mes)'],
        rows: [
          ...(rotation.highest || []).map(m => ['Mayor consumo', m.name, m.units30d, m.rotationIndex]),
          ...(rotation.lowest || []).map(m => ['Menor consumo', m.name, m.units30d, m.rotationIndex])
        ] },
      { title: 'Ocupación promedio mensual por servicio (%)', headers: ['Servicio', ...monthly.months],
        rows: monthly.rows.map(r => [r.service, ...r.values]) }
    ].filter(section => section.rows.length);
    MediPulse.ExportService.downloadCSV(MediPulse.ExportService.filename('dashboard', 'csv'), sections);
    MediPulse.UI.toast('Reporte CSV descargado', 'success');
  },

  async exportPDF() {
    const button = document.getElementById('bi-export-btn');
    if (button) button.classList.add('opacity-60', 'pointer-events-none');
    MediPulse.UI.toast('Generando el PDF del dashboard…', 'info');
    try {
      const d = this.lastData;
      await MediPulse.ExportService.downloadElementPDF(
        document.getElementById('view-bi'),
        MediPulse.ExportService.filename('dashboard', 'pdf'),
        { title: 'KPA-Health · Monitor Ejecutivo Institucional', subtitle: `Datos al ${fmtDate(d.referenceDate)} · ${d.periodLabel || ''}` }
      );
      MediPulse.UI.toast('Reporte PDF descargado', 'success');
    } catch (error) {
      MediPulse.UI.toast(`No se pudo generar el PDF: ${error.message}`, 'error');
    } finally {
      if (button) button.classList.remove('opacity-60', 'pointer-events-none');
    }
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
