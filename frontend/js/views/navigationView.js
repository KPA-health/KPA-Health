/**
 * MediPulse OS - Vista: navegación entre módulos, menú móvil y modal de configuración de la API.
 * Oculta los módulos para los que el rol no tiene permiso (el backend aplica la misma regla con 403).
 */

window.MediPulse = window.MediPulse || {};

// 1. SISTEMA DE NAVEGACIÓN RESPONSIVE
MediPulse.Navigation = {
  currentView: 'view-bi',

  // Vista -> permiso requerido (el backend aplica la misma regla con 403)
  viewPermissions: { 'view-bi': 'dashboard', 'view-ai': 'assistant', 'view-wizard': 'admissions', 'view-data': 'data' },

  firstAllowedView() {
    return Object.keys(this.viewPermissions).find(v => MediPulse.AuthService.can(this.viewPermissions[v])) || 'view-bi';
  },

  switchView(viewId) {
    if (!MediPulse.AuthService.can(this.viewPermissions[viewId])) {
      if (MediPulse.AuthService.session) MediPulse.UI.toast('Su rol no tiene acceso a ese módulo', 'warning');
      viewId = this.firstAllowedView();
    }
    this.currentView = viewId;

    // Ocultar todas las secciones
    document.querySelectorAll('.spa-view').forEach(view => {
      view.classList.add('hidden');
    });

    // Mostrar sección solicitada
    const target = document.getElementById(viewId);
    if (target) {
      target.classList.remove('hidden');
    }

    // Actualizar tabs en sidebar (escritorio)
    document.querySelectorAll('.nav-tab-btn').forEach(btn => {
      if (btn.getAttribute('data-target') === viewId) {
        btn.classList.add('bg-primary-light', 'text-white', 'shadow-inner');
        btn.classList.remove('text-white/90');
      } else {
        btn.classList.remove('bg-primary-light', 'shadow-inner');
        btn.classList.add('text-white/90');
      }
    });

    // Actualizar tabs en bottom bar (móvil)
    document.querySelectorAll('.mobile-tab-btn').forEach(btn => {
      if (btn.getAttribute('data-target') === viewId) {
        btn.classList.add('text-primary', 'font-bold');
        btn.classList.remove('text-slate-500', 'font-medium');
      } else {
        btn.classList.remove('text-primary', 'font-bold');
        btn.classList.add('text-slate-500', 'font-medium');
      }
    });

    // Actualizar contenido con datos reales (con fallback automático a mock)
    if (viewId === 'view-bi') {
      MediPulse.BI.render();
    } else if (viewId === 'view-wizard') {
      MediPulse.Wizard.prepare();
    } else if (viewId === 'view-data') {
      MediPulse.DataSync.refreshCounts();
    }

    // Cerrar sidebar móvil si está abierto
    this.closeMobileDrawer();

    window.scrollTo({ top: 0, behavior: 'smooth' });
    lucide.createIcons();
  },

  openMobileDrawer() {
    const sidebar = document.getElementById('app-sidebar');
    const overlay = document.getElementById('mobile-sidebar-overlay');
    sidebar.classList.remove('-translate-x-full');
    overlay.classList.remove('hidden');
  },

  closeMobileDrawer() {
    const sidebar = document.getElementById('app-sidebar');
    const overlay = document.getElementById('mobile-sidebar-overlay');
    sidebar.classList.add('-translate-x-full');
    overlay.classList.add('hidden');
  },

  openApiSettingsModal() {
    if (!MediPulse.AuthService.can('settings')) {
      MediPulse.UI.toast('Solo un administrador puede cambiar la configuración de la API', 'warning');
      return;
    }
    const config = MediPulse.Config;
    document.getElementById('cfg-use-mock-modal').checked = config.useMock;
    document.getElementById('cfg-auto-fallback-modal').checked = config.autoFallback;
    document.getElementById('cfg-api-url-modal').value = config.apiUrl;
    document.getElementById('cfg-api-lat-modal').value = config.mockLatency;
    document.getElementById('cfg-lat-val').innerText = `${config.mockLatency}ms`;
    setText('cfg-api-status', MediPulse.UI.describeApiStatus(MediPulse.ApiClient.status, MediPulse.ApiClient.statusReason));
    document.getElementById('modal-api-settings').classList.remove('hidden');
  },

  closeApiSettingsModal() {
    document.getElementById('modal-api-settings').classList.add('hidden');
  },

  saveApiSettings() {
    MediPulse.Config.saveSettings({
      useMock: document.getElementById('cfg-use-mock-modal').checked,
      autoFallback: document.getElementById('cfg-auto-fallback-modal').checked,
      apiUrl: document.getElementById('cfg-api-url-modal').value,
      mockLatency: document.getElementById('cfg-api-lat-modal').value
    });
    MediPulse.ApiClient.setStatus(MediPulse.Config.useMock ? 'mock' : 'unknown');
    this.closeApiSettingsModal();
    MediPulse.UI.toast('Configuración de la API guardada', 'success');
    MediPulse.AI.refreshProviders();
    this.switchView(this.currentView);
  }
};
