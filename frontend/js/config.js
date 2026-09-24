/**
 * MediPulse OS - Configuración Global de la Aplicación
 * Define la arquitectura de conexión a la API REST, el fallback a mock y los feature flags.
 */

window.MediPulse = window.MediPulse || {};

(function () {
  // URL por defecto: si la SPA la sirve el backend (localhost:8000 o un despliegue como
  // PythonAnywhere) se usa el mismo origen; si se abre como archivo local o desde un servidor
  // de desarrollo de frontend (Live Server, Vite...), se apunta a localhost:8000.
  const devStaticPorts = ['5500', '5501', '5173', '3000', '8080'];
  const servedByBackend = location.protocol.startsWith('http') && !devStaticPorts.includes(location.port);
  const defaultApiUrl = servedByBackend ? `${location.origin}/api` : 'http://localhost:8000/api';
  const stored = key => {
    try { return localStorage.getItem(key); } catch (e) { return null; }
  };

  MediPulse.Config = {
    // ------------------------------------------------------------------------
    // FEATURE FLAGS (interruptores internos a nivel de código)
    // ------------------------------------------------------------------------
    // Botón de micrófono del asistente (voz a texto con Whisper local).
    // true  -> el botón se renderiza en el chat.
    // false -> el botón no se crea en el DOM (el usuario no nota que falta).
    ENABLE_VOICE_INPUT: true,
    // Enviar automáticamente la pregunta transcrita (false = el usuario la revisa y presiona Enviar).
    VOICE_AUTO_SUBMIT: false,
    // Duración máxima de una grabación de voz (ms).
    VOICE_MAX_RECORDING_MS: 30000,

    // ------------------------------------------------------------------------
    // API REST
    // ------------------------------------------------------------------------
    apiUrl: stored('medipulse_api_url') || defaultApiUrl,
    // JWT de la sesión actual (lo asigna MediPulse.AuthService al iniciar sesión)
    authToken: stored('medipulse_auth_token') || '',

    // true = forzar el modo simulación (no se llama al backend).
    useMock: stored('medipulse_use_mock') === 'true',

    // Fallback automático: si el backend falla o no hay datos, se usa mockData.js.
    autoFallback: stored('medipulse_auto_fallback') !== 'false',

    // Tiempo máximo de espera por petición (ms). La IA tiene su propio límite (modelos locales).
    requestTimeoutMs: parseInt(stored('medipulse_timeout_ms') || '8000', 10),
    aiTimeoutMs: 180000,
    uploadTimeoutMs: 600000,

    // Latencia simulada en milisegundos para emular condiciones de red reales en el mock
    mockLatency: parseInt(stored('medipulse_mock_latency') || '250', 10),

    // Refresco automático del dashboard mientras está visible (ms)
    dashboardRefreshMs: 60000,

    // Metadatos de la institución hospitalaria
    hospital: {
      name: 'Hospital Susana López de Valencia E.S.E.',
      code: 'HSLV',
      city: 'Popayán, Cauca',
      emergencyPhone: '(602) 000 0000',
      departments: [
        'Urgencias',
        'Hospitalización',
        'Cuidados Intensivos (UCI)',
        'Cuidado Intermedio',
        'Pediatría',
        'Gineco-Obstetricia',
        'Recuperación'
      ]
    },

    // Niveles de Triaje Internacional (Manchester / ESI)
    triageLevels: {
      1: { name: 'Nivel 1 - Resucitación', color: 'bg-rose-600 text-white', border: 'border-rose-600', badge: 'bg-rose-100 text-rose-800 border-rose-200', text: 'Inmediata' },
      2: { name: 'Nivel 2 - Emergencia', color: 'bg-orange-500 text-white', border: 'border-orange-500', badge: 'bg-orange-100 text-orange-800 border-orange-200', text: '< 10 min' },
      3: { name: 'Nivel 3 - Urgencia', color: 'bg-amber-500 text-white', border: 'border-amber-500', badge: 'bg-amber-100 text-amber-800 border-amber-200', text: '< 60 min' },
      4: { name: 'Nivel 4 - Menor', color: 'bg-emerald-600 text-white', border: 'border-emerald-600', badge: 'bg-emerald-100 text-emerald-800 border-emerald-200', text: '< 120 min' },
      5: { name: 'Nivel 5 - No Urgente', color: 'bg-blue-600 text-white', border: 'border-blue-600', badge: 'bg-blue-100 text-blue-800 border-blue-200', text: '< 240 min' }
    },

    // Guardar configuración modificada en tiempo de ejecución
    saveSettings(settings) {
      const persist = (key, value) => {
        try { localStorage.setItem(key, value); } catch (e) { /* almacenamiento no disponible */ }
      };
      if (settings.apiUrl !== undefined && settings.apiUrl.trim()) {
        this.apiUrl = settings.apiUrl.trim().replace(/\/+$/, '');
        persist('medipulse_api_url', this.apiUrl);
      }
      if (settings.useMock !== undefined) {
        this.useMock = Boolean(settings.useMock);
        persist('medipulse_use_mock', this.useMock);
      }
      if (settings.autoFallback !== undefined) {
        this.autoFallback = Boolean(settings.autoFallback);
        persist('medipulse_auto_fallback', this.autoFallback);
      }
      if (settings.mockLatency !== undefined) {
        this.mockLatency = parseInt(settings.mockLatency, 10) || 0;
        persist('medipulse_mock_latency', this.mockLatency);
      }
    },

    // URL base del servidor (sin /api) para endpoints de la IA y archivos
    serverOrigin() {
      return this.apiUrl.replace(/\/(api|v1)\/?$/, '');
    },

    // Restaurar datos de prueba a su estado original
    resetMockData() {
      ['medipulse_patients', 'medipulse_doctors', 'medipulse_appointments', 'medipulse_rooms', 'medipulse_pharmacy']
        .forEach(key => localStorage.removeItem(key));
      MediPulse.MockData.initialize(true);
    }
  };
})();
