/**
 * MediPulse OS - Servicio de Autenticación (JWT) y permisos por rol
 *
 * - login(): POST /api/auth/login -> guarda el JWT (lo usa apiClient.js en cada petición).
 * - El token se valida al iniciar (GET /api/auth/me) y la sesión se cierra sola al expirar.
 * - Los permisos vienen del backend (fuente única: backend/auth/permissions.py):
 *     admin -> todo · user -> dashboard, assistant, admissions
 */

window.MediPulse = window.MediPulse || {};

MediPulse.AuthService = {
  TOKEN_KEY: 'medipulse_auth_token',
  USER_KEY: 'medipulse_user',
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
          ...(options.token ? { Authorization: `Bearer ${options.token}` } : {})
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
    this.startSession(data.accessToken, data.user);
    return data.user;
  },

  /** Restaura la sesión guardada si el token sigue vigente y el backend lo acepta. */
  async restore() {
    const token = localStorage.getItem(this.TOKEN_KEY);
    if (!token || this.isExpired(token)) {
      this.clear();
      return null;
    }
    const user = await this.request('/auth/me', { token });
    this.startSession(token, user);
    return user;
  },

  startSession(token, user) {
    this.session = user;
    MediPulse.Config.authToken = token;
    localStorage.setItem(this.TOKEN_KEY, token);
    localStorage.setItem(this.USER_KEY, JSON.stringify(user));
    this.scheduleExpiry(token);
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

  logout() {
    this.clear();
    window.location.reload();
  },

  clear() {
    clearTimeout(this.expiryTimer);
    this.session = null;
    MediPulse.Config.authToken = '';
    localStorage.removeItem(this.TOKEN_KEY);
    localStorage.removeItem(this.USER_KEY);
  },

  decode(token) {
    try {
      const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
      return JSON.parse(decodeURIComponent(escape(atob(payload))));
    } catch (e) {
      return null;
    }
  },

  isExpired(token) {
    const claims = this.decode(token);
    return !claims || !claims.exp || claims.exp * 1000 <= Date.now();
  },

  scheduleExpiry(token) {
    clearTimeout(this.expiryTimer);
    const claims = this.decode(token);
    if (!claims || !claims.exp) return;
    const ms = claims.exp * 1000 - Date.now();
    this.expiryTimer = setTimeout(() => {
      window.dispatchEvent(new CustomEvent('medipulse:unauthorized', { detail: { message: 'La sesión expiró. Inicie sesión de nuevo' } }));
    }, Math.max(ms, 0));
  },

  can(permission) {
    return Boolean(this.session && this.session.permissions && this.session.permissions.includes(permission));
  }
};
