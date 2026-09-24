/**
 * MediPulse OS - Filtro de Privacidad (capa de presentación)
 *
 * Defensa en profundidad: aunque el backend ya anonimiza, TODO dato que se
 * renderiza en dashboards, gráficos o respuestas del asistente pasa por aquí.
 * Garantiza que nunca se muestren nombres, apellidos ni documentos de identidad,
 * incluso cuando los datos vienen del mock de respaldo (mockData.js).
 */

window.MediPulse = window.MediPulse || {};

MediPulse.Privacy = {
  MASK: '•••',

  // Columnas que no son personales aunque su nombre lo sugiera (ej. NombreMedicamento)
  safeColumnTokens: ['medicament', 'diagnost', 'servicio', 'cama', 'grupo', 'area', 'especialidad',
    'categoria', 'insumo', 'procedimiento', 'municipio', 'departamento', 'asegurador', 'regimen'],
  personalColumn: /(nombre|apellido|document|cedula|dni|identificacion|telefono|celular|email|correo|direccion|nacimiento|pasaporte|name|phone)/,

  // "CC 1061234567", "cédula: 34.567.890", "DNI 74829104K"
  documentInText: /\b(c\.?\s?c\.?|c[eé]dulas?|documentos?(?:\s+de\s+identidad)?|dni|t\.?\s?i\.?|pasaportes?)(\s*(?:n(?:[uú]mero|o|º|°)\.?)?\s*[:#]?\s*)(\d(?:[\d.\-]|\s(?=\d)){4,}[A-Za-z]?)(?![A-Za-z])/gi,

  normalize(text) {
    return String(text || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  },

  // Seudónimo estable: nunca el nombre real
  pseudonym(patient) {
    if (!patient) return 'Paciente anónimo';
    if (typeof patient.name === 'string' && /^Paciente[ _]/.test(patient.name)) return patient.name;
    const id = patient.id || patient.patientId || '';
    return id ? `Paciente ${String(id).replace(/^Paciente[ _]/, '')}` : 'Paciente anónimo';
  },

  maskPatient(patient) {
    if (!patient) return patient;
    return {
      ...patient,
      name: this.pseudonym(patient),
      dni: `Doc. ${this.MASK}`,
      phone: null
    };
  },

  maskBed(bed) {
    if (!bed || !bed.patientName) return bed;
    return { ...bed, patientName: this.pseudonym({ name: bed.patientName, id: bed.patientId }) };
  },

  scrubText(text) {
    if (!text) return text;
    return String(text).replace(this.documentInText, (m, type, sep) => `${type}${sep}${this.MASK}`);
  },

  isPersonalColumn(column) {
    const normalized = this.normalize(column).replace(/[_\s]/g, '');
    if (this.safeColumnTokens.some(token => normalized.includes(token))) return false;
    return this.personalColumn.test(normalized);
  },

  // Enmascara columnas personales en resultados tabulares del asistente
  maskTable(columns, rows) {
    const personal = columns.map((c, i) => (this.isPersonalColumn(c) ? i : -1)).filter(i => i >= 0);
    if (!personal.length) return rows;
    return rows.map(row => row.map((cell, i) => (personal.includes(i) ? this.MASK : cell)));
  }
};
