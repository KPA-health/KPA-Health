/**
 * MediPulse OS - Punto de entrada de la SPA: conecta eventos globales e inicia la sesión al cargar el DOM.
 * Se carga el último: todas las vistas y servicios ya están definidos en window.MediPulse.
 */

window.MediPulse = window.MediPulse || {};

// 7. BOOTSTRAP DE LA APLICACIÓN AL CARGAR EL DOM
document.addEventListener('DOMContentLoaded', () => {
  MediPulse.MockData.initialize();
  window.addEventListener('medipulse:api-status', event => {
    MediPulse.UI.setApiStatus(event.detail.status, event.detail.reason);
  });
  MediPulse.UI.setApiStatus(MediPulse.Config.useMock ? 'mock' : 'unknown');
  MediPulse.Wizard.bindTriageSelector();

  // Control del Sidebar en Escritorio
  const sidebar = document.getElementById('app-sidebar');
  const btnToggleSidebar = document.getElementById('btn-toggle-sidebar');
  const toggleIcon = document.getElementById('sidebar-toggle-icon');

  btnToggleSidebar.addEventListener('click', () => {
    const isCollapsed = sidebar.classList.contains('md:w-20');
    if (isCollapsed) {
      sidebar.classList.remove('md:w-20');
      sidebar.classList.add('md:w-64');
      toggleIcon.classList.remove('rotate-180');
      document.querySelectorAll('.sidebar-text-content').forEach(el => el.classList.remove('hidden'));
    } else {
      sidebar.classList.remove('md:w-64');
      sidebar.classList.add('md:w-20');
      toggleIcon.classList.add('rotate-180');
      document.querySelectorAll('.sidebar-text-content').forEach(el => el.classList.add('hidden'));
    }
  });

  // Apertura y Cierre Móvil Off-Canvas
  document.getElementById('btn-open-mobile-sidebar').addEventListener('click', () => {
    MediPulse.Navigation.openMobileDrawer();
  });
  document.getElementById('btn-close-mobile-sidebar').addEventListener('click', () => {
    MediPulse.Navigation.closeMobileDrawer();
  });
  document.getElementById('mobile-sidebar-overlay').addEventListener('click', () => {
    MediPulse.Navigation.closeMobileDrawer();
  });

  // Sesión: login JWT y permisos por rol; al autenticar se abre la primera vista permitida
  window.addEventListener('medipulse:unauthorized', event => MediPulse.Auth.onUnauthorized(event.detail && event.detail.message));
  MediPulse.Auth.init();

  lucide.createIcons();
});
