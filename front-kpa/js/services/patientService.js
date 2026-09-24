/**
 * MediPulse OS - Servicio de Gestión de Pacientes
 * Encapsula la lógica de negocio y las peticiones al ApiClient
 */

window.MediPulse = window.MediPulse || {};

MediPulse.PatientService = {
  /**
   * Obtener lista de pacientes con filtros opcionales
   */
  async getAll(filters = {}) {
    const response = await MediPulse.ApiClient.get('/patients', filters);
    return response.data || [];
  },

  /**
   * Obtener detalles de un paciente específico
   */
  async getById(id) {
    const response = await MediPulse.ApiClient.get(`/patients/${id}`);
    return response.data;
  },

  /**
   * Crear un nuevo paciente
   */
  async create(patientData) {
    // Validaciones básicas de integridad
    if (!patientData.name || !patientData.dni) {
      throw new Error('El nombre completo y la identificación (DNI) son obligatorios.');
    }

    const payload = {
      ...patientData,
      age: parseInt(patientData.age, 10) || 0,
      triageLevel: parseInt(patientData.triageLevel, 10) || 4,
      status: patientData.status || 'En Observación',
      vitals: patientData.vitals || { bp: '120/80', hr: '75 lpm', temp: '36.5°C', spo2: '98%' }
    };

    const response = await MediPulse.ApiClient.post('/patients', payload);
    return response.data;
  },

  /**
   * Actualizar datos clínicos del paciente
   */
  async update(id, patientData) {
    const response = await MediPulse.ApiClient.put(`/patients/${id}`, patientData);
    return response.data;
  },

  /**
   * Dar de alta médica a un paciente
   */
  async discharge(id, dischargeNotes = '') {
    const patient = await this.getById(id);
    const updated = {
      ...patient,
      status: 'Dado de Alta',
      dischargeDate: new Date().toISOString().replace('T', ' ').substring(0, 16),
      dischargeNotes: dischargeNotes || 'Alta médica autorizada con indicaciones ambulatorias.'
    };
    
    // Si tenía cama asignada, la liberamos
    if (patient.bedId) {
      await MediPulse.RoomService.releaseBed(patient.bedId);
      updated.bedId = null;
      updated.roomNumber = 'Dado de Alta';
    }

    return await this.update(id, updated);
  },

  /**
   * Eliminar registro de paciente
   */
  async delete(id) {
    return await MediPulse.ApiClient.delete(`/patients/${id}`);
  }
};
