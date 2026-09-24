/**
 * MediPulse OS - Servicio de Agenda y Citas Médicas
 */

window.MediPulse = window.MediPulse || {};

MediPulse.AppointmentService = {
  async getAll(filters = {}) {
    const response = await MediPulse.ApiClient.get('/appointments', filters);
    return response.data || [];
  },

  async getById(id) {
    const response = await MediPulse.ApiClient.get(`/appointments/${id}`);
    return response.data;
  },

  /**
   * Agenda una cita. El backend guarda solo un seudónimo del paciente, nunca su nombre.
   * @param {{patientId?: string, patientName: string, doctorName: string, date: string}} appointmentData
   */
  async create(appointmentData) {
    if (!appointmentData.patientName || !appointmentData.doctorName || !appointmentData.date) {
      throw new Error('Todos los campos marcados con asterisco son obligatorios.');
    }
    const response = await MediPulse.ApiClient.post('/appointments', appointmentData);
    return response.data;
  },

  async updateStatus(id, status) {
    const response = await MediPulse.ApiClient.patch(`/appointments/${id}`, { status });
    return response.data;
  },

  async delete(id) {
    return await MediPulse.ApiClient.delete(`/appointments/${id}`);
  }
};
