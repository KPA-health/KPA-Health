/**
 * MediPulse OS - Servicio de Farmacia e Inventario
 */

window.MediPulse = window.MediPulse || {};

MediPulse.PharmacyService = {
  /** Inventario ordenado por urgencia. filters: { status, category, q, limit }. */
  async getAll(filters = {}) {
    const response = await MediPulse.ApiClient.get('/pharmacy', filters);
    return response.data || [];
  },

  /** Actualiza stock/lote/vencimiento; el estado (Crítico/Bajo/Adecuado) lo recalcula el backend. */
  async updateStock(id, changes) {
    const response = await MediPulse.ApiClient.put(`/pharmacy/${encodeURIComponent(id)}`, changes);
    return response.data;
  }
};
