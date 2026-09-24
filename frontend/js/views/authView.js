/**
 * MediPulse OS - Vista: pantalla de login, modo demo y aplicación de permisos por rol en la interfaz.
 * La autenticación real (JWT) la resuelve MediPulse.AuthService contra /api/auth/*.
 */

window.MediPulse = window.MediPulse || {};

// 8. SESIÓN Y ROLES (login JWT). Solo tras autenticar se cargan datos y vistas.
MediPulse.Auth = {
  started: false,

  async init() {
    let config = null;
    try {
      config = await MediPulse.AuthService.config();
    } catch (error) {
      if (MediPulse.Config.useMock) return this.enter(MediPulse.AuthService.startDemoSession());
      return this.showLogin(error.network ? 'No hay conexión con el servidor. Puede continuar en modo demostración.' : error.message, error.network);
    }
    if (!config.authEnabled) return this.enter(MediPulse.AuthService.anonymousAdmin(config.roles));
    try {
      const user = await MediPulse.AuthService.restore();
      if (user) return this.enter(user);
    } catch (error) {
      MediPulse.AuthService.clear();
    }
    this.showLogin();
  },

  showLogin(message = '', offline = false) {
    document.getElementById('login-screen').classList.remove('hidden');
    const error = document.getElementById('login-error');
    error.textContent = message;
    error.classList.toggle('hidden', !message);
    document.getElementById('login-demo').classList.toggle('hidden', !offline);
    setTimeout(() => document.getElementById('login-username').focus(), 50);
    lucide.createIcons();
  },

  async submit(event) {
    event.preventDefault();
    const button = document.getElementById('login-submit');
    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;
    button.disabled = true;
    button.classList.add('opacity-60');
    try {
      const user = await MediPulse.AuthService.login(username, password);
      document.getElementById('login-password').value = '';
      this.enter(user);
      MediPulse.UI.toast(`Bienvenido(a), ${user.name}`, 'success');
    } catch (error) {
      this.showLogin(error.message, Boolean(error.network));
    } finally {
      button.disabled = false;
      button.classList.remove('opacity-60');
    }
  },

  enterDemo() {
    this.enter(MediPulse.AuthService.startDemoSession());
    MediPulse.UI.toast('Modo demostración: última copia de la base de datos, sin conexión al hospital', 'warning');
  },

  // Oculta del DOM visible todo lo que el rol no puede usar
  applyPermissions() {
    document.querySelectorAll('[data-perm]').forEach(el => {
      el.classList.toggle('hidden', !MediPulse.AuthService.can(el.dataset.perm));
    });
    const session = MediPulse.AuthService.session || {};
    const name = session.name || '—';
    setText('session-user-name', name);
    setText('session-user-role', `${session.roleLabel || session.role || ''}${session.demo ? ' · sin conexión' : ''}${session.open ? ' · sin login' : ''}`);
    setText('session-user-initials', name.split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]).join('').toUpperCase() || '—');
    document.getElementById('btn-logout').classList.toggle('hidden', Boolean(session.open));
  },

  enter(user) {
    document.getElementById('login-screen').classList.add('hidden');
    this.applyPermissions();
    if (!this.started) {
      this.started = true;
      if (MediPulse.AuthService.can('assistant')) MediPulse.AI.init();
      MediPulse.BI.startAutoRefresh();
    }
    MediPulse.Navigation.switchView(MediPulse.Navigation.firstAllowedView());
    lucide.createIcons();
    return user;
  },

  logout() {
    MediPulse.AuthService.logout();
  },

  // Token vencido o revocado: se vuelve al login sin perder la página
  onUnauthorized(message) {
    if (!MediPulse.AuthService.session || MediPulse.AuthService.session.open || MediPulse.AuthService.session.demo) return;
    MediPulse.AuthService.clear();
    this.started = false;
    clearInterval(MediPulse.BI.refreshTimer);
    this.showLogin(message || 'Su sesión terminó. Inicie sesión de nuevo');
  }
};
