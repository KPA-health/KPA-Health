/**
 * MediPulse OS - Servicio de Autenticación (JWT) y permisos por rol
 *
 * - login(): POST /api/auth/login -> JWT en cookie HttpOnly; JS no accede al token.
 * - La sesión se valida al iniciar con GET /api/auth/me.
 * - Los permisos vienen del backend (fuente única: backend/services/auth/permissions.py):
 *     admin -> todo · user -> dashboard, assistant, admissions
 */

window.MediPulse = window.MediPulse || {};

MediPulse.AuthService = {
  // Permisos del rol "user" para el modo demostración sin conexión
  DEMO_PERMISSIONS: ['admissions', 'assistant', 'dashboard'],

  session: null,          // { username, name, role, roleLabel, permissions, demo? }
  expiryTimer: null,

  url(path) {
    const base = MediPulse.Config.apiUrl.replace(/\/+$/, '');
    return new URL(`${base}${path}`, window.location.href).toString();
  },

  async request(path, options = {}) {
    let response;
    try {
      response = await MediPulse.ApiClient.fetchWithTimeout(this.url(path), {
        method: options.method || 'GET',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          ...(options.method === 'POST' && path !== '/auth/login' ? { 'X-CSRF-Token': MediPulse.ApiClient.csrfToken() } : {})
        },
        body: options.body ? JSON.stringify(options.body) : undefined
      }, MediPulse.Config.requestTimeoutMs);
    } catch (error) {
      const err = new Error('No hay conexión con el servidor del hospital');
      err.network = true;
      throw err;
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const err = new Error(data.message || `Error HTTP ${response.status}`);
      err.status = response.status;
      throw err;
    }
    return data;
  },

  /** { authEnabled, roles } — público */
  async config() {
    return this.request('/auth/config');
  },

  async login(username, password) {
    const data = await this.request('/auth/login', { method: 'POST', body: { username, password } });
    this.startSession(data.user, data.expiresIn);
    return data.user;
  },

  /** Restaura desde la cookie HttpOnly si el backend la acepta. */
  async restore() {
    const user = await this.request('/auth/me');
    this.startSession(user);
    return user;
  },

  startSession(user, expiresIn = null) {
    this.session = user;
    localStorage.removeItem('medipulse_auth_token');
    localStorage.removeItem('medipulse_user');
    if (expiresIn) this.scheduleExpiry(expiresIn);
  },

  /** Sesión sin backend: solo datos simulados (el backend exige un JWT real para los datos reales). */
  startDemoSession() {
    this.session = { username: 'demo', name: 'Modo demostración', role: 'user', roleLabel: 'Demostración', permissions: this.DEMO_PERMISSIONS, demo: true };
    MediPulse.Config.useMock = true;   // no se persiste: al recargar se vuelve a intentar el backend
    return this.session;
  },

  anonymousAdmin(roles) {
    const permissions = (roles && roles.admin && roles.admin.permissions) || [];
    this.session = { username: 'sin-autenticacion', name: 'Acceso libre', role: 'admin', roleLabel: 'Administrador', permissions, open: true };
    return this.session;
  },

  async logout() {
    try { await this.request('/auth/logout', { method: 'POST' }); } catch (_) { /* cierre local */ }
    this.clear();
    window.location.reload();
  },

  clear() {
    clearTimeout(this.expiryTimer);
    this.session = null;
    localStorage.removeItem('medipulse_auth_token');
    localStorage.removeItem('medipulse_user');
  },

  scheduleExpiry(expiresIn) {
    clearTimeout(this.expiryTimer);
    this.expiryTimer = setTimeout(() => {
      window.dispatchEvent(new CustomEvent('medipulse:unauthorized', { detail: { message: 'La sesión expiró. Inicie sesión de nuevo' } }));
    }, Math.max(expiresIn * 1000, 0));
  },

  can(permission) {
    return Boolean(this.session && this.session.permissions && this.session.permissions.includes(permission));
  }
};
