/**
 * MediPulse OS - Cliente HTTP Modular Asíncrono con Fallback Automático
 *
 * Patrón Repository / Adapter + Proxy con fallback: el resto de la app consume
 * este cliente sin saber si los datos provienen del backend FastAPI (hospital.db)
 * o de la copia de respaldo de la BD (mockData.js).
 *
 * Estrategia de resiliencia (para que la demo nunca se caiga):
 *  - useMock = true            -> siempre mock (modo simulación explícito).
 *  - backend OK con datos      -> datos reales (estado "online").
 *  - backend OK pero SIN datos -> mock (estado "fallback", motivo "empty").
 *  - red caída / timeout / 5xx -> mock (estado "fallback", motivo "error").
 *  - errores 4xx (validación, cama ocupada, no encontrado) NO hacen fallback:
 *    son errores de negocio y deben mostrarse al usuario.
 * Cada cambio de estado emite el evento `medipulse:api-status` para la interfaz.
 */

window.MediPulse = window.MediPulse || {};

MediPulse.ApiClient = {
  status: 'unknown',        // online | fallback | mock | offline
  statusReason: '',
  fallbackCode: null,       // 'error' (backend caído) | 'empty' (base de datos sin datos)

  // Endpoints que devuelven datos del hospital (los que deciden si hay datos reales)
  dataResources: ['dashboard', 'stats', 'rooms', 'patients', 'pharmacy', 'doctors', 'appointments'],

  isDataEndpoint(endpoint) {
    return this.dataResources.includes(endpoint.split('?')[0].replace(/^\//, '').split('/')[0]);
  },

  setStatus(status, reason = '', code = null) {
    this.fallbackCode = status === 'fallback' ? code : null;
    const changed = status !== this.status || reason !== this.statusReason;
    this.status = status;
    this.statusReason = reason;
    if (changed) {
      window.dispatchEvent(new CustomEvent('medipulse:api-status', { detail: { status, reason } }));
    }
  },

  buildUrl(endpoint, params) {
    const base = MediPulse.Config.apiUrl.replace(/\/+$/, '');
    const url = new URL(`${base}${endpoint}`, window.location.href);
    if (params) {
      Object.keys(params).forEach(key => {
        const value = params[key];
        if (value !== undefined && value !== null && value !== '') url.searchParams.append(key, value);
      });
    }
    return url.toString();
  },

  headers(jsonBody = true) {
    const headers = { 'Accept': 'application/json' };
    if (jsonBody) headers['Content-Type'] = 'application/json';
    return headers;
  },

  csrfToken() {
    const entry = document.cookie.split('; ').find(part => part.startsWith('medipulse_csrf='));
    return entry ? decodeURIComponent(entry.slice('medipulse_csrf='.length)) : '';
  },

  async fetchWithTimeout(url, init, timeoutMs) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      return await fetch(url, { ...init, signal: controller.signal });
    } finally {
      clearTimeout(timer);
    }
  },

  /**
   * Petición HTTP real contra el backend.
   * @param {string} endpoint Ruta relativa a Config.apiUrl (ej. '/patients').
   * @param {{method?: string, params?: object, body?: object, formData?: FormData, timeoutMs?: number}} options
   * @returns {Promise<object>} Cuerpo JSON de la respuesta.
   * @throws {Error} Con `network = true` si no hubo respuesta, o con `status`/`detail` del error HTTP
   *   (el backend siempre responde {success: false, message, detail}).
   */
  async httpRequest(endpoint, options = {}) {
    let response;
    try {
      response = await this.fetchWithTimeout(this.buildUrl(endpoint, options.params), {
        method: options.method || 'GET',
        headers: {
          ...this.headers(!options.formData),
          ...(['POST', 'PUT', 'PATCH', 'DELETE'].includes((options.method || 'GET').toUpperCase())
            ? { 'X-CSRF-Token': this.csrfToken() } : {})
        },
        body: options.formData || (options.body ? JSON.stringify(options.body) : undefined)
      }, options.timeoutMs || MediPulse.Config.requestTimeoutMs);
    } catch (error) {
      const err = new Error(error.name === 'AbortError'
        ? 'El servidor no respondió a tiempo'
        : 'No hay conexión con el servidor del hospital');
      err.network = true;
      throw err;
    }

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      const err = new Error(data.message || `Error del servidor HTTP ${response.status}`);
      err.status = response.status;
      err.detail = data.detail;
      // 401 = sesión inválida o vencida -> la SPA vuelve a la pantalla de login
      if (response.status === 401) {
        window.dispatchEvent(new CustomEvent('medipulse:unauthorized', { detail: { message: err.message } }));
      }
      throw err;
    }
    if (response.status === 204) return { success: true };
    return await response.json();
  },

  /**
   * ¿El error justifica usar el mock? Solo caídas de red y 5xx: los 4xx son errores de negocio
   * (validación, cama ocupada...) y deben llegar al usuario. 501 = función deshabilitada, no caída.
   */
  isRecoverable(error, options) {
    if (error.network) return true;
    if (options.fallback === 'network-only') return false;
    return error.status >= 500 && error.status !== 501;
  },

  /** ¿La respuesta viene vacía porque la base de datos no tiene datos? (solo lecturas sin filtros) */
  isEmptyDataset(endpoint, options, payload) {
    if ((options.method || 'GET').toUpperCase() !== 'GET' || options.fallback === 'network-only') return false;
    const path = endpoint.split('?')[0];
    const params = options.params || {};
    const data = payload && payload.data;
    if (path === '/dashboard') return !data || !data.kpis || data.kpis.totalBeds === 0;
    if (path === '/stats') return !data || data.totalBeds === 0;
    const filtered = ['q', 'status', 'department', 'triage', 'specialty', 'date', 'doctorId', 'category']
      .some(key => params[key] && params[key] !== 'all');
    if (filtered) return false;
    if (['/rooms', '/patients', '/pharmacy', '/doctors'].includes(path)) return Array.isArray(data) && data.length === 0;
    return false;
  },

  /**
   * Ejecuta una petición con fallback automático al mock.
   * options: { method, params, body, timeoutMs, fallback: 'auto' | 'network-only' | 'none' }
   */
  async request(endpoint, options = {}) {
    const config = MediPulse.Config;

    if (config.useMock) {
      this.setStatus('mock', 'Modo simulación activado en la configuración');
      if (config.mockLatency > 0) await new Promise(resolve => setTimeout(resolve, config.mockLatency));
      return this.mockResponse(endpoint, options, 'mock');
    }

    // Con la base de datos vacía, las escrituras de datos también van al mock para que
    // la demo sea coherente (p. ej. el wizard asigna camas del mismo origen que muestra).
    const method = (options.method || 'GET').toUpperCase();
    const emptyMode = this.status === 'fallback' && this.fallbackCode === 'empty';
    if (config.autoFallback && emptyMode && method !== 'GET' && this.isDataEndpoint(endpoint)) {
      return this.mockResponse(endpoint, options, 'empty');
    }

    try {
      const payload = await this.httpRequest(endpoint, options);
      if (config.autoFallback && options.fallback !== 'none' && this.isEmptyDataset(endpoint, options, payload)) {
        this.setStatus('fallback', 'La base de datos no tiene datos disponibles', 'empty');
        return this.mockResponse(endpoint, options, 'empty');
      }
      // Un endpoint sin datos del hospital (salud, IA) no saca al sistema del modo "BD vacía".
      // Se evalúa al terminar la petición (otra petición pudo cambiar el estado mientras tanto).
      const stillEmpty = this.status === 'fallback' && this.fallbackCode === 'empty';
      if (!(stillEmpty && !this.isDataEndpoint(endpoint))) this.setStatus('online');
      return payload;
    } catch (error) {
      if (config.autoFallback && options.fallback !== 'none' && this.isRecoverable(error, options)) {
        console.warn(`[MediPulse ApiClient] Fallback a mock en ${endpoint}: ${error.message}`);
        this.setStatus('fallback', error.message, 'error');
        return this.mockResponse(endpoint, options, 'error');
      }
      if (error.network) this.setStatus('offline', error.message);
      throw error;
    }
  },

  mockResponse(endpoint, options, reason) {
    const result = this.handleMockRequest(endpoint, options);
    if (result && typeof result === 'object') {
      Object.defineProperty(result, '_meta', { value: { source: 'mock', reason }, enumerable: false });
    }
    return result;
  },

  isMock(response) {
    return Boolean(response && response._meta && response._meta.source === 'mock');
  },

  // Métodos semánticos REST
  async get(endpoint, params = {}, extra = {}) {
    return this.request(endpoint, { ...extra, method: 'GET', params });
  },

  async post(endpoint, body = {}, extra = {}) {
    return this.request(endpoint, { ...extra, method: 'POST', body });
  },

  async put(endpoint, body = {}, extra = {}) {
    return this.request(endpoint, { ...extra, method: 'PUT', body });
  },

  async patch(endpoint, body = {}, extra = {}) {
    return this.request(endpoint, { ...extra, method: 'PATCH', body });
  },

  async delete(endpoint, extra = {}) {
    return this.request(endpoint, { ...extra, method: 'DELETE' });
  },

  /** Subida de archivos (multipart). No tiene fallback: la carga necesita el backend real. */
  async upload(endpoint, file, fieldName = 'file', extra = {}) {
    if (MediPulse.Config.useMock) {
      throw new Error('La carga de archivos requiere el backend. Desactive el modo simulación.');
    }
    const formData = new FormData();
    formData.append(fieldName, file, file.name || 'archivo');
    try {
      const payload = await this.httpRequest(endpoint, {
        method: 'POST', formData, timeoutMs: extra.timeoutMs || MediPulse.Config.uploadTimeoutMs
      });
      this.setStatus('online');
      return payload;
    } catch (error) {
      if (error.network) this.setStatus('offline', error.message);
      throw error;
    }
  },

  /**
   * Simulador de Backend REST (Mock Engine)
   * Resuelve endpoints estándar procesando datos almacenados en localStorage.
   * Todas las salidas pasan por MediPulse.Privacy (sin nombres ni documentos).
   */
  handleMockRequest(endpoint, options) {
    MediPulse.MockData.initialize();
    const Privacy = MediPulse.Privacy;
    const method = (options.method || 'GET').toUpperCase();
    const [path] = endpoint.split('?');
    const segments = path.replace(/^\/|\/$/g, '').split('/');
    const resource = segments[0];
    const resourceId = segments[1];

    // Leer colecciones actuales
    let patients = JSON.parse(localStorage.getItem('medipulse_patients') || '[]');
    let doctors = JSON.parse(localStorage.getItem('medipulse_doctors') || '[]');
    let appointments = JSON.parse(localStorage.getItem('medipulse_appointments') || '[]');
    let rooms = JSON.parse(localStorage.getItem('medipulse_rooms') || '[]');
    let pharmacy = JSON.parse(localStorage.getItem('medipulse_pharmacy') || '[]');

    // 1. RECURSO: PACIENTES (/patients)
    if (resource === 'patients') {
      if (method === 'GET' && !resourceId) {
        let results = [...patients];
        if (options.params) {
          const { q, status, department, triage } = options.params;
          if (q) {
            const query = q.toLowerCase();
            results = results.filter(p =>
              p.id.toLowerCase().includes(query) ||
              (p.diagnosis || '').toLowerCase().includes(query)
            );
          }
          if (status && status !== 'all') {
            results = results.filter(p => (status === 'active' ? p.status !== 'Dado de Alta' : p.status === status));
          }
          if (department && department !== 'all') {
            results = results.filter(p => p.department === department);
          }
          if (triage && triage !== 'all') {
            results = results.filter(p => String(p.triageLevel) === String(triage));
          }
        }
        return { data: results.map(p => Privacy.maskPatient(p)), count: results.length };
      }

      if (method === 'GET' && resourceId) {
        const item = patients.find(p => p.id === resourceId);
        if (!item) throw new Error(`Paciente con ID ${resourceId} no encontrado`);
        return { data: Privacy.maskPatient(item) };
      }

      if (method === 'POST') {
        const id = `PAC-${Math.floor(800 + Math.random() * 900)}`;
        // Privacidad: el mock tampoco conserva nombres ni documentos
        const newPatient = {
          ...options.body,
          id,
          name: `Paciente ${id}`,
          dni: `Doc. ${Privacy.MASK}`,
          phone: null,
          doctorAssignedName: options.body.doctorAssignedName || options.body.doctorName || null,
          admissionDate: new Date().toISOString().replace('T', ' ').substring(0, 16)
        };
        patients.unshift(newPatient);
        localStorage.setItem('medipulse_patients', JSON.stringify(patients));
        if (newPatient.bedId) {
          this.updateBedAssignment(rooms, newPatient.bedId, newPatient.id, newPatient.name);
        }
        return { data: newPatient, message: 'Paciente registrado exitosamente (modo respaldo)' };
      }

      if (method === 'PUT' && resourceId) {
        const index = patients.findIndex(p => p.id === resourceId);
        if (index === -1) throw new Error(`Paciente con ID ${resourceId} no encontrado`);
        const { name, dni, phone, ...changes } = options.body || {};
        patients[index] = { ...patients[index], ...changes };
        if (changes.status === 'Dado de Alta' && patients[index].bedId) {
          this.updateBedAssignment(rooms, patients[index].bedId, null, null);
        }
        localStorage.setItem('medipulse_patients', JSON.stringify(patients));
        return { data: Privacy.maskPatient(patients[index]), message: 'Datos del paciente actualizados' };
      }

      if (method === 'DELETE' && resourceId) {
        const patient = patients.find(p => p.id === resourceId);
        if (patient && patient.bedId) {
          this.updateBedAssignment(rooms, patient.bedId, null, null);
        }
        patients = patients.filter(p => p.id !== resourceId);
        localStorage.setItem('medipulse_patients', JSON.stringify(patients));
        return { success: true, message: 'Registro de paciente eliminado' };
      }
    }

    // 2. RECURSO: DOCTORES (/doctors)
    if (resource === 'doctors') {
      if (method === 'GET' && !resourceId) {
        let results = [...doctors];
        if (options.params && options.params.specialty && options.params.specialty !== 'all') {
          results = results.filter(d => d.specialty === options.params.specialty);
        }
        return { data: results, count: results.length };
      }
      if (method === 'GET' && resourceId) {
        const item = doctors.find(d => d.id === resourceId);
        if (!item) throw new Error('Doctor no encontrado');
        return { data: item };
      }
      if (method === 'PUT' && resourceId) {
        const index = doctors.findIndex(d => d.id === resourceId);
        if (index === -1) throw new Error('Doctor no encontrado');
        doctors[index] = { ...doctors[index], ...options.body };
        localStorage.setItem('medipulse_doctors', JSON.stringify(doctors));
        return { data: doctors[index] };
      }
    }

    // 3. RECURSO: CITAS MÉDICAS (/appointments)
    if (resource === 'appointments') {
      const maskAppointment = a => ({ ...a, patientName: a.patientId ? `Paciente ${a.patientId}` : 'Paciente anónimo' });
      if (method === 'GET' && !resourceId) {
        let results = [...appointments];
        if (options.params) {
          const { date, status, doctorId } = options.params;
          if (date) results = results.filter(a => a.date === date);
          if (status && status !== 'all') results = results.filter(a => a.status === status);
          if (doctorId && doctorId !== 'all') results = results.filter(a => a.doctorId === doctorId);
        }
        return { data: results.map(maskAppointment), count: results.length };
      }

      if (method === 'GET' && resourceId) {
        const item = appointments.find(a => a.id === resourceId);
        if (!item) throw new Error('Cita médica no encontrada');
        return { data: maskAppointment(item) };
      }

      if (method === 'POST') {
        const newApt = {
          id: `APT-${Math.floor(500 + Math.random() * 500)}`,
          status: 'Programada',
          priority: 'Normal',
          ...options.body
        };
        appointments.push(newApt);
        localStorage.setItem('medipulse_appointments', JSON.stringify(appointments));
        return { data: maskAppointment(newApt), message: 'Cita médica agendada correctamente' };
      }

      if (method === 'PATCH' || method === 'PUT') {
        const index = appointments.findIndex(a => a.id === resourceId);
        if (index === -1) throw new Error('Cita médica no encontrada');
        appointments[index] = { ...appointments[index], ...options.body };
        localStorage.setItem('medipulse_appointments', JSON.stringify(appointments));
        return { data: maskAppointment(appointments[index]) };
      }

      if (method === 'DELETE' && resourceId) {
        appointments = appointments.filter(a => a.id !== resourceId);
        localStorage.setItem('medipulse_appointments', JSON.stringify(appointments));
        return { success: true };
      }
    }

    // 4. RECURSO: HABITACIONES Y CAMAS (/rooms)
    if (resource === 'rooms') {
      if (method === 'GET') {
        return { data: rooms.map(w => ({ ...w, beds: w.beds.map(b => Privacy.maskBed(b)) })) };
      }
      if (method === 'PUT' && resourceId === 'bed-status') {
        const { bedId, status, patientId } = options.body;
        this.updateBedAssignment(rooms, bedId, patientId, patientId ? `Paciente ${patientId}` : null, status);
        return { success: true, message: 'Estado de cama modificado' };
      }
    }

    // 5. RECURSO: FARMACIA (/pharmacy)
    if (resource === 'pharmacy') {
      if (method === 'GET') {
        return { data: pharmacy, count: pharmacy.length };
      }
      if (method === 'PUT' && resourceId) {
        const index = pharmacy.findIndex(m => m.id === resourceId);
        if (index === -1) throw new Error('Insumo no encontrado');
        pharmacy[index] = { ...pharmacy[index], ...options.body };
        // Recalcular estado de stock
        if (pharmacy[index].stock <= pharmacy[index].minStock * 0.5) {
          pharmacy[index].status = 'Crítico';
        } else if (pharmacy[index].stock <= pharmacy[index].minStock) {
          pharmacy[index].status = 'Bajo';
        } else {
          pharmacy[index].status = 'Adecuado';
        }
        localStorage.setItem('medipulse_pharmacy', JSON.stringify(pharmacy));
        return { data: pharmacy[index], message: 'Stock actualizado' };
      }
    }

    // 6. RECURSO: ESTADÍSTICAS DASHBOARD (/stats)
    if (resource === 'stats') {
      const beds = rooms.flatMap(w => w.beds);
      const occupiedBeds = beds.filter(b => b.status === 'Ocupada').length;
      const freeBeds = beds.filter(b => b.status === 'Libre').length;
      return {
        data: {
          activePatients: patients.filter(p => p.status !== 'Dado de Alta').length,
          criticalPatients: patients.filter(p => p.status === 'Crítico' || p.triageLevel === 1).length,
          totalBeds: beds.length,
          occupiedBeds,
          freeBeds,
          maintenanceBeds: beds.length - occupiedBeds - freeBeds,
          occupancyRate: beds.length ? Math.round((occupiedBeds / beds.length) * 100) : 0,
          todayAppointments: appointments.length,
          availableDoctors: doctors.filter(d => d.status === 'Disponible').length,
          criticalMeds: pharmacy.filter(p => p.status === 'Crítico').length
        }
      };
    }

    // 7. RECURSO: DASHBOARD BI (/dashboard) — misma forma que GET /api/dashboard
    if (resource === 'dashboard') {
      return { data: this.buildMockDashboard(options.params || {}, { patients, rooms, pharmacy }) };
    }

    // 8. RECURSO: SALUD DEL SISTEMA (/health)
    if (resource === 'health') {
      return { status: 'mock', database: 'mockData.js', referenceDatetime: null, rowCounts: null };
    }

    // 9. RECURSO: ASISTENTE IA (/ai/...) — respaldo sin motor de IA
    if (resource === 'ai') {
      if (resourceId === 'providers') {
        const offline = mode => ({ mode, provider: 'respaldo', model: 'sin conexión', available: false, detail: 'Backend no disponible: modo respaldo con la copia de la BD' });
        return { defaultMode: 'local', allowFallback: false, providers: [offline('local'), offline('cloud')], voiceEnabled: false, voice: { enabled: false, detail: 'Requiere el backend' } };
      }
      if (resourceId === 'query') return this.mockAssistantAnswer((options.body || {}).question || '', { patients, rooms, pharmacy, doctors });
    }

    if (resource === 'upload') {
      throw new Error('La carga de archivos requiere conexión con el backend');
    }

    throw new Error(`Endpoint mock no implementado: [${method}] ${endpoint}`);
  },

  buildMockDashboard(params, { patients, rooms, pharmacy }) {
    const Privacy = MediPulse.Privacy;
    const period = params.period || 'today';
    const service = params.service || 'all';
    const days = { today: 1, '7d': 7, '30d': 30 }[period] || 1;
    const active = patients.filter(p => p.status !== 'Dado de Alta' && (service === 'all' || p.department === service));
    const beds = rooms.flatMap(w => w.beds);
    const occupied = beds.filter(b => b.status === 'Ocupada').length;
    const free = beds.filter(b => b.status === 'Libre').length;
    const rate = beds.length ? Math.round((occupied / beds.length) * 1000) / 10 : 0;
    const trendDays = Math.max(days, 7);
    const today = new Date();
    const dates = Array.from({ length: trendDays }, (_, i) => {
      const d = new Date(today); d.setDate(today.getDate() - (trendDays - 1 - i));
      return d.toISOString().slice(0, 10);
    });
    const byDepartment = {};
    patients.forEach(p => { byDepartment[p.department] = (byDepartment[p.department] || 0) + 1; });
    const triageOrder = p => (p.triageLevel || 9);

    return {
      source: 'mock',
      referenceDate: today.toISOString().slice(0, 10),
      period,
      periodLabel: { today: 'Hoy', '7d': 'Últimos 7 días', '30d': 'Último mes' }[period],
      service,
      services: MediPulse.Config.hospital.departments,
      lastSync: null,
      kpis: {
        totalBeds: beds.length, occupiedBeds: occupied, freeBeds: free, occupancyRate: rate,
        avgWaitMinutes: 38.5, waitPatients: patients.length,
        surgeriesScheduled: 10 * days, surgeriesPerformed: 8 * days, surgeryComplianceRate: 80,
        criticalMeds: pharmacy.filter(m => m.status === 'Crítico').length,
        lowStockMeds: pharmacy.filter(m => m.status === 'Bajo').length,
        medsUnder5Days: pharmacy.filter(m => m.status === 'Crítico').length,
        activePatients: active.length,
        criticalPatients: active.filter(p => p.status === 'Crítico' || p.triageLevel === 1).length,
        admissions: patients.length
      },
      occupancyTrend: {
        dates,
        labels: dates.map(d => `${d.slice(8, 10)}/${d.slice(5, 7)}`),
        occupancyPct: dates.map((_, i) => Math.max(0, Math.min(100, Math.round(rate + 8 * Math.sin(i / 1.7) - 4)))),
        admissions: dates.map((_, i) => 12 + ((i * 7) % 9)),
        windowDays: trendDays
      },
      serviceDistribution: { labels: Object.keys(byDepartment), values: Object.values(byDepartment) },
      wards: rooms.map(w => {
        const total = w.beds.length;
        const occ = w.beds.filter(b => b.status === 'Ocupada').length;
        const freeCount = w.beds.filter(b => b.status === 'Libre').length;
        return { wing: w.wing, total, occupied: occ, free: freeCount, unavailable: total - occ - freeCount, occupancyPct: total ? Math.round((occ / total) * 100) : 0 };
      }),
      urgentPatients: [...active].sort((a, b) => triageOrder(a) - triageOrder(b)).slice(0, 12).map(p => {
        const masked = Privacy.maskPatient(p);
        return { id: p.id, name: masked.name, triageLevel: p.triageLevel, diagnosis: p.diagnosis, roomNumber: p.roomNumber, department: p.department, admissionDate: p.admissionDate, status: p.status };
      }),
      criticalMeds: [...pharmacy].sort((a, b) => (a.stock / (a.minStock || 1)) - (b.stock / (b.minStock || 1))).slice(0, 8)
        .map(m => ({ id: m.id, name: m.name, stock: m.stock, minStock: m.minStock, daysOfInventory: null, dailyConsumption: null, status: m.status }))
    };
  },

  /** Respuestas de respaldo del asistente (sin motor de IA) para que la demo no se detenga. */
  mockAssistantAnswer(question, { patients, rooms, pharmacy, doctors }) {
    const q = MediPulse.Privacy.normalize(question);
    const base = {
      success: true, question, mode: 'respaldo', provider: 'mock', model: 'copia de la BD', explanation: 'Respuesta de respaldo calculada con la copia de la base de datos (sin motor de IA).',
      sql: null, category: 'hospital', blockedBy: null, rows: [], columns: [], columnLabels: [], rowCount: 0, truncated: false,
      attempts: [], timings: { totalMs: 0 }, referenceDate: null, fallbackUsed: true, datos_grafico: [], tipo_grafico: null,
      warnings: ['El backend no está disponible: respuesta con la última copia de la base de datos (mockData.js).']
    };
    const table = (labels, rows) => ({ columns: labels, columnLabels: labels, rows, rowCount: rows.length });

    if (q.includes('uci') || q.includes('cama')) {
      const beds = rooms.flatMap(w => w.beds.map(b => ({ ...b, wing: w.wing })));
      const icu = beds.filter(b => /uci|intensiv/i.test(`${b.wing} ${b.code} ${b.type}`));
      const scope = icu.length ? icu : beds;
      const occupied = scope.filter(b => b.status === 'Ocupada').length;
      return { ...base, answer: `Hay ${occupied} de ${scope.length} camas ocupadas${icu.length ? ' en UCI' : ''} (copia de la BD).`, ...table(['Cama', 'Estado'], scope.map(b => [b.code, b.status])) };
    }
    if (q.includes('triaj') || q.includes('triag') || q.includes('critic') && q.includes('paciente')) {
      const crit = patients.filter(p => p.triageLevel <= 2 && p.status !== 'Dado de Alta');
      return { ...base, answer: `Hay ${crit.length} pacientes activos en triaje nivel 1 o 2 (copia de la BD).`, ...table(['Ingreso', 'Nivel de triage', 'Diagnóstico', 'Servicio'], crit.map(p => [p.id, p.triageLevel, p.diagnosis, p.department])) };
    }
    if (q.includes('medicament') || q.includes('farmac') || q.includes('stock')) {
      const low = pharmacy.filter(m => m.status === 'Crítico' || m.status === 'Bajo');
      return { ...base, answer: `Hay ${low.length} medicamentos por debajo del stock de seguridad (copia de la BD).`, ...table(['Medicamento', 'Stock actual', 'Stock mínimo', 'Estado'], low.map(m => [m.name, m.stock, m.minStock, m.status])),
        tipo_grafico: low.length ? 'bar' : null, datos_grafico: low.slice(0, 30).map(m => ({ etiqueta: m.name, 'Stock actual': m.stock, 'Stock mínimo': m.minStock })) };
    }
    if (q.includes('medico') || q.includes('doctor') || q.includes('guardia') || q.includes('especialista')) {
      const available = doctors.filter(d => d.status === 'Disponible');
      return { ...base, answer: `Hay ${available.length} médicos disponibles (copia de la BD).`, ...table(['Médico (ID)', 'Especialidad', 'Turno'], available.map(d => [d.id, d.specialty, d.shift])) };
    }
    return { ...base, answer: 'El motor de IA no está disponible en este momento. En modo respaldo solo puedo responder las consultas rápidas con la copia de la base de datos.' };
  },

  /**
   * Helper para actualizar camas en salas (mock)
   */
  updateBedAssignment(rooms, bedId, patientId, patientName, customStatus = null) {
    let updated = false;
    rooms.forEach(wing => {
      wing.beds.forEach(bed => {
        if (bed.id === bedId) {
          if (customStatus) {
            bed.status = customStatus;
            if (customStatus === 'Libre' || customStatus === 'Desinfección' || customStatus === 'Mantenimiento') {
              bed.patientId = null;
              bed.patientName = null;
            }
          } else if (patientId) {
            bed.status = 'Ocupada';
            bed.patientId = patientId;
            bed.patientName = patientName;
          } else {
            bed.status = 'Libre';
            bed.patientId = null;
            bed.patientName = null;
          }
          updated = true;
        }
      });
    });
    if (updated) {
      localStorage.setItem('medipulse_rooms', JSON.stringify(rooms));
    }
  }
};
