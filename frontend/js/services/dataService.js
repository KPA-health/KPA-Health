/**
 * MediPulse OS - Servicio de Gestión de Datos (ETL)
 * Carga de datasets del HIS por categoría y conteo de registros por tabla.
 */

window.MediPulse = window.MediPulse || {};

MediPulse.DataService = {
  // Tipo de carga del frontend -> tabla del HIS en hospital.db
  tables: {
    paciente: 'Paciente', triage: 'Triage', ingresos: 'Ingresos', atencion: 'Atencion',
    medicamento: 'MedicamentoInsumo', servicios: 'Servicios', cirugia: 'ProgramacionCirugia'
  },

  /**
   * Sube un archivo plano del HIS (separado por '|').
   * @param {string} type Tipo de carga (clave de `tables`, p. ej. 'paciente').
   * @param {File} file Archivo .txt o .csv.
   */
  async upload(type, file) {
    return MediPulse.ApiClient.upload(`/upload/${encodeURIComponent(type)}`, file);
  },

  /** Conteo de registros por tabla (null si el backend no está disponible). */
  async getStatus() {
    const response = await MediPulse.ApiClient.get('/health', {}, { fallback: 'auto' });
    return {
      source: MediPulse.ApiClient.isMock(response) ? 'mock' : 'api',
      rowCounts: response.rowCounts || null,
      referenceDatetime: response.referenceDatetime || null,
      refreshedAt: response.semanticLayerRefreshedAt || null
    };
  }
};
