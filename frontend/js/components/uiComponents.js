/**
 * MediPulse OS - Componentes de interfaz reutilizables: toasts, indicador de estado de la API y widget de accesibilidad.
 * No dependen de ninguna vista; las vistas los usan a través de MediPulse.UI.
 */

window.MediPulse = window.MediPulse || {};

// 6. COMPONENTES UI: TOASTS, ESTADO DE LA API & ACCESIBILIDAD
MediPulse.UI = {
  escape(value) {
    return String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  },

  /** Escribe datos externos como texto, nunca como HTML ejecutable. */
  setSafeText(element, value) {
    element.textContent = String(value ?? '');
    return element;
  },

  /**
   * Tarjeta de una alerta de /api/insights/briefing (la usan el chat y el dashboard).
   * @param {object} item {type, severity, title, message, action, items}
   * @param {{detail?: boolean}} options detail = agrega la tabla de detalle (medicamentos, camas, turnos o días).
   */
  alertCard(item, { detail = false } = {}) {
    const e = v => this.escape(v);
    const styles = {
      alta: ['bg-rose-50 border-rose-200', 'bg-rose-600 text-white', 'Prioridad alta'],
      media: ['bg-amber-50 border-amber-200', 'bg-amber-500 text-white', 'Prioridad media'],
      baja: ['bg-emerald-50 border-emerald-200', 'bg-emerald-600 text-white', 'Informativa']
    };
    const icons = { demanda: 'trending-up', espera: 'clock', desabastecimiento: 'pill', ocupacion: 'bed', personal: 'users', cirugia: 'scissors' };
    const [box, badge, label] = styles[item.severity] || styles.baja;

    // Detalle por tipo de alerta: [encabezados, filas]
    const pct = v => (v === null || v === undefined ? '—' : `${v > 0 ? '+' : ''}${fmtNumber(v, 0)}%`);
    const tables = {
      demanda: [['Medicamento asociado', 'Cobertura', 'Pedir'],
        m => [m.name, `${fmtNumber(m.coverageDays, 0)} días`, m.orderQuantity ? `${fmtNumber(m.orderQuantity)} und` : 'Suficiente']],
      desabastecimiento: [['Mayor consumo', 'Cobertura', 'Pedir'],
        m => [m.name, `${fmtNumber(m.daysOfInventory, 1)} días`, `${fmtNumber(m.orderQuantity)} und`]],
      ocupacion: [['Servicio', 'Ocupación 7 días', 'Abrir'],
        s => [s.service, `${fmtNumber(s.avgOccupancyPct, 1)}%`, `+${fmtNumber(s.bedsToOpen)} camas`]],
      personal: [['Turno', 'Espera', 'Pacientes/día'],
        s => [`${s.shift} (${s.hours})`, `${fmtNumber(s.currentAvgWait, 0)} min`, fmtNumber(s.currentPerDay, 1)]],
      cirugia: [['Día', 'Cirugías/día', 'Vs. promedio hábil'],
        d => [d.day, fmtNumber(d.perDay, 1), pct(d.vsAveragePct)]]
    };
    const spec = detail ? tables[item.type] : null;
    const headers = spec ? spec[0] : [];
    const rows = spec ? (item.items || []).map(spec[1]) : [];
    const table = rows.length ? `
      <table class="w-full text-left text-[11px] bg-white/70 rounded-lg overflow-hidden">
        <thead class="text-[9px] uppercase text-slate-500">
          <tr><th class="px-2 py-1">${e(headers[0])}</th><th class="px-2 py-1 text-right">${e(headers[1])}</th><th class="px-2 py-1 text-right">${e(headers[2])}</th></tr>
        </thead>
        <tbody class="divide-y divide-slate-100">
          ${rows.map(([name, middle, last]) => `
          <tr>
            <td class="px-2 py-1 text-slate-700 max-w-[220px] truncate" title="${e(name)}">${e(name)}</td>
            <td class="px-2 py-1 text-right whitespace-nowrap">${e(middle)}</td>
            <td class="px-2 py-1 text-right font-bold text-primary whitespace-nowrap">${e(last)}</td>
          </tr>`).join('')}
        </tbody>
      </table>` : '';

    return `
      <div class="rounded-xl border ${box} p-3 space-y-1.5 text-xs">
        <div class="flex items-center justify-between gap-2 flex-wrap">
          <p class="font-bold text-slate-800 flex items-center gap-1.5">
            <i data-lucide="${icons[item.type] || 'alert-triangle'}" class="w-3.5 h-3.5"></i>${e(item.title)}
          </p>
          <span class="px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wide ${badge}">${label}</span>
        </div>
        <p class="text-slate-700 leading-relaxed">${e(item.message)}</p>
        ${item.action ? `
        <p class="text-primary font-semibold flex items-start gap-1.5">
          <i data-lucide="lightbulb" class="w-3.5 h-3.5 mt-0.5 shrink-0 text-amber-500"></i><span>${e(item.action)}</span>
        </p>` : ''}
        ${table}
      </div>`;
  },

  toast(msg, type = 'success') {
    const container = document.getElementById('toast-container');
    const el = document.createElement('div');
    const colors = {
      success: 'bg-emerald-800 text-white border-emerald-600',
      error: 'bg-rose-800 text-white border-rose-600',
      info: 'bg-primary text-white border-tertiary',
      warning: 'bg-amber-800 text-white border-amber-600'
    };
    const icons = {
      success: 'check-circle-2',
      error: 'alert-circle',
      info: 'info',
      warning: 'alert-triangle'
    };

    el.className = `flex items-center space-x-2.5 px-4 py-3 rounded-xl border shadow-xl ${colors[type] || colors.info} transform transition-all duration-300 pointer-events-auto text-xs font-semibold translate-y-3 opacity-0`;
    el.innerHTML = `
      <i data-lucide="${icons[type] || 'info'}" class="w-4 h-4 shrink-0"></i>
      <span class="flex-1">${this.escape(msg)}</span>
    `;
    container.appendChild(el);
    lucide.createIcons();

    requestAnimationFrame(() => {
      el.classList.remove('translate-y-3', 'opacity-0');
    });

    setTimeout(() => {
      el.classList.add('opacity-0', 'translate-x-4');
      setTimeout(() => el.remove(), 300);
    }, 3600);
  },

  describeApiStatus(status, reason) {
    const labels = {
      online: 'Conectado a la API REST real (hospital.db)',
      fallback: `Modo respaldo con mockData.js${reason ? ` · ${reason}` : ''}`,
      mock: 'Modo respaldo forzado (copia de la BD en mockData.js)',
      offline: `Sin conexión con el backend${reason ? ` · ${reason}` : ''}`,
      unknown: 'Comprobando conexión…'
    };
    return labels[status] || labels.unknown;
  },

  // Indicador de conexión del encabezado (verde = real, ámbar = respaldo, azul = simulación)
  setApiStatus(status, reason = '') {
    const styles = {
      online: { pill: 'bg-emerald-50 border-emerald-200 text-emerald-800 hover:bg-emerald-100', dot: 'bg-emerald-500', ping: 'bg-emerald-400', text: 'API Conectada (REST Real)' },
      fallback: { pill: 'bg-amber-50 border-amber-200 text-amber-800 hover:bg-amber-100', dot: 'bg-amber-500', ping: 'bg-amber-400', text: 'Modo Respaldo (Mock)' },
      mock: { pill: 'bg-blue-50 border-blue-200 text-blue-800 hover:bg-blue-100', dot: 'bg-blue-500', ping: 'bg-blue-400', text: 'Modo Simulación (Mock)' },
      offline: { pill: 'bg-rose-50 border-rose-200 text-rose-800 hover:bg-rose-100', dot: 'bg-rose-500', ping: 'bg-rose-400', text: 'Sin Conexión' },
      unknown: { pill: 'bg-slate-50 border-slate-200 text-slate-700 hover:bg-slate-100', dot: 'bg-slate-400', ping: 'bg-slate-300', text: 'Conectando…' }
    };
    const s = styles[status] || styles.unknown;
    const pill = document.getElementById('api-status-pill');
    if (pill) pill.className = `flex items-center space-x-1.5 px-2.5 py-1 rounded-full border text-xs font-medium cursor-pointer transition-colors ${s.pill}`;
    const dot = document.getElementById('api-status-dot');
    if (dot) dot.className = `relative inline-flex rounded-full h-2 w-2 ${s.dot}`;
    const ping = document.getElementById('api-status-ping');
    if (ping) ping.className = `api-pulse absolute inline-flex h-full w-full rounded-full opacity-75 ${s.ping}`;
    setText('api-status-text', s.text);
    if (pill) pill.title = this.describeApiStatus(status, reason);

    if (status === 'fallback' && this.lastStatus !== 'fallback') {
      this.toast('Backend no disponible o sin datos: usando la última copia de la base de datos (mockData.js)', 'warning');
    } else if (status === 'online' && this.lastStatus === 'fallback') {
      this.toast('Conexión con el backend restablecida', 'success');
    }
    this.lastStatus = status;
  }
};

// Inicializador del Widget de Accesibilidad
(function setupAccessibility() {
  const btnAccess = document.getElementById('btn-accessibility');
  const menuAccess = document.getElementById('accessibility-menu');
  const btnReset = document.getElementById('btn-reset-accessibility');
  const btnContrast = document.getElementById('btn-toggle-contrast');
  const contrastKnob = document.getElementById('contrast-slider-knob');
  const btnDyslexia = document.getElementById('btn-toggle-dyslexia');
  const dyslexiaKnob = document.getElementById('dyslexia-slider-knob');
  const fontButtons = document.querySelectorAll('.btn-font-size');

  btnAccess.addEventListener('click', (e) => {
    e.stopPropagation();
    menuAccess.classList.toggle('hidden');
  });

  document.addEventListener('click', (e) => {
    if (!document.getElementById('accessibility-dropdown-container').contains(e.target)) {
      menuAccess.classList.add('hidden');
    }
  });

  const sizes = { sm: 'font-size-sm', md: 'font-size-md', lg: 'font-size-lg', xl: 'font-size-xl' };
  fontButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const sz = btn.getAttribute('data-size');
      Object.values(sizes).forEach(c => document.documentElement.classList.remove(c));
      if (sz !== 'md') document.documentElement.classList.add(sizes[sz]);

      fontButtons.forEach(b => {
        b.classList.remove('bg-secondary', 'text-white');
        b.classList.add('hover:border-secondary');
      });
      btn.classList.add('bg-secondary', 'text-white');
      btn.classList.remove('hover:border-secondary');
      localStorage.setItem('medipulse_font_size', sz);
    });
  });

  let highContrast = localStorage.getItem('medipulse_contrast') === 'true';
  function applyContrast(state) {
    highContrast = state;
    if (state) {
      document.documentElement.classList.add('high-contrast-mode');
      btnContrast.classList.remove('bg-slate-200');
      btnContrast.classList.add('bg-secondary');
      contrastKnob.classList.add('translate-x-5');
    } else {
      document.documentElement.classList.remove('high-contrast-mode');
      btnContrast.classList.add('bg-slate-200');
      btnContrast.classList.remove('bg-secondary');
      contrastKnob.classList.remove('translate-x-5');
    }
    localStorage.setItem('medipulse_contrast', state);
  }
  btnContrast.addEventListener('click', () => applyContrast(!highContrast));
  if (highContrast) applyContrast(true);

  let dyslexia = localStorage.getItem('medipulse_dyslexia') === 'true';
  function applyDyslexia(state) {
    dyslexia = state;
    if (state) {
      document.body.classList.add('dyslexia-font');
      btnDyslexia.classList.remove('bg-slate-200');
      btnDyslexia.classList.add('bg-secondary');
      dyslexiaKnob.classList.add('translate-x-5');
    } else {
      document.body.classList.remove('dyslexia-font');
      btnDyslexia.classList.add('bg-slate-200');
      btnDyslexia.classList.remove('bg-secondary');
      dyslexiaKnob.classList.remove('translate-x-5');
    }
    localStorage.setItem('medipulse_dyslexia', state);
  }
  btnDyslexia.addEventListener('click', () => applyDyslexia(!dyslexia));
  if (dyslexia) applyDyslexia(true);

  btnReset.addEventListener('click', () => {
    applyContrast(false);
    applyDyslexia(false);
    Object.values(sizes).forEach(c => document.documentElement.classList.remove(c));
    localStorage.removeItem('medipulse_font_size');
    MediPulse.UI.toast('Accesibilidad restablecida', 'info');
  });
})();
