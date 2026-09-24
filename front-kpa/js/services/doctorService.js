/**
 * MediPulse OS - Servicio de Personal Médico y Especialistas
 */

window.MediPulse = window.MediPulse || {};

MediPulse.DoctorService = {
  async getAll(filters = {}) {
    const response = await MediPulse.ApiClient.get('/doctors', filters);
    return response.data || [];
  },

  async getById(id) {
    const doctors = await this.getAll();
    return doctors.find(d => d.id === id);
  },

  async updateStatus(id, status) {
    const response = await MediPulse.ApiClient.put(`/doctors/${id}`, { status });
    return response.data;
  }
};
