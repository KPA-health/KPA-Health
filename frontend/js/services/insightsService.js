/**
 * MediPulse OS - Servicio de insights: resumen proactivo, alertas predictivas y causa raíz.
 * Los cálculos los hace el backend (GET /api/insights/*) con reglas y estadística, sin IA generativa.
 */

window.MediPulse = window.MediPulse || {};

MediPulse.InsightsService = {
  /** Resumen proactivo: alertas ordenadas por prioridad con su acción recomendada. */
  async briefing(end = null) {
    return this.fetch('/insights/briefing', end);
  },

  /** Causa raíz del cambio de la espera en urgencias (semana que termina en `end`). */
  async waitDrivers(end = null) {
    return this.fetch('/insights/wait-drivers', end);
  },

  /** Picos de demanda por familia clínica y medicamentos a reforzar. */
  async demandAlerts(end = null) {
    return this.fetch('/insights/demand-alerts', end);
  },

  async fetch(endpoint, end) {
    // Sin respaldo simulado: un insight sobre datos inventados sería engañoso
    if (MediPulse.Config.useMock) throw new Error('Los insights requieren conexión con el servidor del hospital');
    const response = await MediPulse.ApiClient.get(endpoint, end ? { end } : {}, { fallback: 'none', timeoutMs: 20000 });
    return response.data || {};
  }
};
