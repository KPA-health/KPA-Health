/**
 * MediPulse OS - Servicio del Dashboard BI
 * Una sola llamada trae KPIs, tendencias, distribución, capacidad, censo y stock crítico.
 */

window.MediPulse = window.MediPulse || {};

MediPulse.DashboardService = {
  /** filters: { period: 'today' | '7d' | '30d', service: 'all' | <servicio> } */
  async get(filters = {}) {
    const response = await MediPulse.ApiClient.get('/dashboard', {
      period: filters.period || 'today',
      service: filters.service || 'all'
    });
    const data = response.data || {};
    data.source = MediPulse.ApiClient.isMock(response) ? 'mock' : (data.source || 'api');
    return data;
  }
};
