/**
 * MediPulse OS - Vista: gestión de datos (carga de archivos del HIS y conteo de registros por tabla).
 * La limpieza e inserción las hace el backend (POST /api/upload/{type}).
 */

window.MediPulse = window.MediPulse || {};

// 5. LÓGICA PARA GESTIÓN Y SUBIDA DE DATOS (ETL real contra hospital.db)
MediPulse.DataSync = {
  handleFileSelect(input, labelId) {
    const label = document.getElementById(labelId);
    if (input.files && input.files.length > 0) {
      const fileName = input.files[0].name;
      label.innerHTML = `<span class="text-primary font-bold"><i data-lucide="file-text" class="w-3 h-3 inline mr-1"></i>${MediPulse.UI.escape(fileName)}</span>`;
      lucide.createIcons();
    } else {
      label.innerText = 'Ningún archivo nuevo seleccionado';
    }
  },

  async refreshCounts() {
    const badge = document.getElementById('db-sync-badge');
    try {
      const status = await MediPulse.DataService.getStatus();
      const online = status.source === 'api' && status.rowCounts;
      Object.entries(MediPulse.DataService.tables).forEach(([type, table]) => {
        setText(`count-${type}`, online ? `${fmtNumber(status.rowCounts[table])} registros en BD` : 'Sin conexión con la BD');
      });
      badge.innerHTML = online
        ? `<span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span> DB sincronizada · datos al ${fmtDate((status.referenceDatetime || '').slice(0, 10))}`
        : '<span class="w-2 h-2 rounded-full bg-amber-500"></span> Backend no disponible';
      badge.className = `px-3 py-1.5 rounded-lg border text-xs font-bold flex items-center gap-2 shrink-0 ${online ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-amber-200 bg-amber-50 text-amber-800'}`;
    } catch (error) {
      badge.innerHTML = '<span class="w-2 h-2 rounded-full bg-rose-500"></span> Sin conexión';
    }
  },

  async uploadFile(type) {
    const input = document.getElementById(`file-${type}`);
    const label = document.getElementById(`label-${type}`);

    if (!input.files || input.files.length === 0) {
      MediPulse.UI.toast('Por favor, selecciona un archivo .txt primero', 'warning');
      return;
    }

    const file = input.files[0];
    const button = document.querySelector(`[data-upload="${type}"]`);
    if (button) { button.disabled = true; button.classList.add('opacity-60'); }
    label.innerHTML = '<span class="text-secondary font-bold">Procesando…</span>';
    MediPulse.UI.toast(`Procesando e inyectando datos de ${file.name}...`, 'info');

    try {
      const result = await MediPulse.DataService.upload(type, file);
      const d = result.data || {};
      label.innerHTML = `<span class="text-emerald-700 font-bold">✔ ${fmtNumber(d.rowsRead)} leídos · ${fmtNumber(d.rowsInserted)} nuevos · ${fmtNumber(d.rowsUpdatedOrSkipped)} actualizados</span>`;
      MediPulse.UI.toast(result.message || `¡Base de datos de ${type} actualizada con éxito!`, 'success');
      MediPulse.UI.toast('Dashboards sincronizados con la nueva data.', 'info');
      await this.refreshCounts();
    } catch (error) {
      const missing = error.detail && error.detail.missingColumns;
      const detail = missing ? ` Faltan columnas: ${missing.join(', ')}` : '';
      label.innerHTML = `<span class="text-rose-600 font-bold">✖ ${MediPulse.UI.escape(error.message)}</span>`;
      MediPulse.UI.toast(`No se pudo cargar ${file.name}: ${error.message}.${detail}`, 'error');
    } finally {
      input.value = '';
      if (button) { button.disabled = false; button.classList.remove('opacity-60'); }
    }
  }
};
