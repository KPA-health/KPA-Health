/**
 * MediPulse OS - Servicio de Farmacia e Inventario
 */

window.MediPulse = window.MediPulse || {};

MediPulse.PharmacyService = {
  async getAll(filters = {}) {
    const response = await MediPulse.ApiClient.get('/pharmacy', filters);
    return response.data || [];
  },

  async updateStock(id, changes) {
    const response = await MediPulse.ApiClient.put(`/pharmacy/${encodeURIComponent(id)}`, changes);
    return response.data;
  }
};
