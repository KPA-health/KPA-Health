/**
 * MediPulse OS - Banco de Datos Simulados (Mock Data)
 * Estructuras normalizadas listas para mapear a esquemas de base de datos relacionales o NoSQL.
 */

window.MediPulse = window.MediPulse || {};

MediPulse.MockData = {
  // Lista inicial de médicos especialistas
  initialDoctors: [
    {
      id: 'DOC-101',
      name: 'Dra. Elena Ramos Morales',
      specialty: 'Cardiología',
      department: 'Cardiología',
      licenseNumber: 'CMP-48291',
      shift: 'Mañana (07:00 - 15:00)',
      status: 'Disponible',
      phone: '+34 612 345 678',
      email: 'e.ramos@medipulse.org',
      consultingRoom: 'Cons. 104 - Ala Este',
      avatar: 'https://images.unsplash.com/photo-1559839734-2b71ea197ec2?auto=format&fit=crop&q=80&w=200'
    },
    {
      id: 'DOC-102',
      name: 'Dr. Carlos Mendoza Soler',
      specialty: 'Traumatología y Ortopedia',
      department: 'Traumatología',
      licenseNumber: 'CMP-39104',
      shift: 'Tarde (15:00 - 23:00)',
      status: 'En Cirugía',
      phone: '+34 623 456 789',
      email: 'c.mendoza@medipulse.org',
      consultingRoom: 'Quirófano Q-02',
      avatar: 'https://images.unsplash.com/photo-1622253692010-333f2da6031d?auto=format&fit=crop&q=80&w=200'
    },
    {
      id: 'DOC-103',
      name: 'Dra. Sofía Valenzuela Paz',
      specialty: 'Cuidados Intensivos (UCI)',
      department: 'Cuidados Intensivos (UCI)',
      licenseNumber: 'CMP-51203',
      shift: 'Guardia 24h',
      status: 'En Consulta',
      phone: '+34 634 567 890',
      email: 's.valenzuela@medipulse.org',
      consultingRoom: 'UCI Central - Box 3',
      avatar: 'https://images.unsplash.com/photo-1594824813576-928929949bb7?auto=format&fit=crop&q=80&w=200'
    },
    {
      id: 'DOC-104',
      name: 'Dr. Mateo Benítez Rivas',
      specialty: 'Pediatría',
      department: 'Pediatría',
      licenseNumber: 'CMP-29845',
      shift: 'Mañana (07:00 - 15:00)',
      status: 'Disponible',
      phone: '+34 645 678 901',
      email: 'm.benitez@medipulse.org',
      consultingRoom: 'Cons. 201 - Pabellón Infantil',
      avatar: 'https://images.unsplash.com/photo-1537368910025-700350fe46c7?auto=format&fit=crop&q=80&w=200'
    },
    {
      id: 'DOC-105',
      name: 'Dra. Carmen Navarro Gil',
      specialty: 'Neurología',
      department: 'Neurología',
      licenseNumber: 'CMP-60312',
      shift: 'Mañana (07:00 - 15:00)',
      status: 'Disponible',
      phone: '+34 656 789 012',
      email: 'c.navarro@medipulse.org',
      consultingRoom: 'Cons. 305 - Neurociencias',
      avatar: 'https://images.unsplash.com/photo-1559839734-2b71ea197ec2?auto=format&fit=crop&q=80&w=200'
    },
    {
      id: 'DOC-106',
      name: 'Dr. Alejandro Silva Torrico',
      specialty: 'Urgencias Médicas',
      department: 'Urgencias',
      licenseNumber: 'CMP-44129',
      shift: 'Guardia 24h',
      status: 'Disponible',
      phone: '+34 667 890 123',
      email: 'a.silva@medipulse.org',
      consultingRoom: 'Triaje de Urgencias',
      avatar: 'https://images.unsplash.com/photo-1612349317150-e413f6a5b16d?auto=format&fit=crop&q=80&w=200'
    }
  ],

  // Lista inicial de pacientes
  initialPatients: [
    {
      id: 'PAC-801',
      dni: '48921045A',
      name: 'Lucas Gabriel Herrera',
      age: 58,
      gender: 'Masculino',
      bloodType: 'O+',
      admissionDate: '2026-09-22 08:30',
      triageLevel: 1, // Resucitación
      status: 'Crítico',
      department: 'Cuidados Intensivos (UCI)',
      roomNumber: 'UCI-01',
      bedId: 'BED-101',
      doctorAssignedId: 'DOC-103',
      doctorAssignedName: 'Dra. Sofía Valenzuela Paz',
      diagnosis: 'Insuficiencia respiratoria aguda secundaria a sepsis bacteriana',
      allergies: 'Penicilina, Sulfamidas',
      vitals: { bp: '85/55', hr: '124 lpm', temp: '39.1°C', spo2: '88%' },
      notes: 'Monitorización hemodinámica continua. En ventilación mecánica invasiva.'
    },
    {
      id: 'PAC-802',
      dni: '52309184B',
      name: 'Mariana Isabel Vega Castro',
      age: 42,
      gender: 'Femenino',
      bloodType: 'A+',
      admissionDate: '2026-09-23 06:15',
      triageLevel: 2, // Emergencia
      status: 'Internado',
      department: 'Cardiología',
      roomNumber: 'HAB-204',
      bedId: 'BED-201',
      doctorAssignedId: 'DOC-101',
      doctorAssignedName: 'Dra. Elena Ramos Morales',
      diagnosis: 'Síndrome coronario agudo sin elevación del segmento ST (SCASEST)',
      allergies: 'Ninguna conocida',
      vitals: { bp: '145/95', hr: '88 lpm', temp: '36.8°C', spo2: '97%' },
      notes: 'Pendiente de coronariografía diagnóstica programada para el turno vespertino.'
    },
    {
      id: 'PAC-803',
      dni: '71049283C',
      name: 'Mateo Alejandro Ríos Flores',
      age: 7,
      gender: 'Masculino',
      bloodType: 'B+',
      admissionDate: '2026-09-23 11:20',
      triageLevel: 3, // Urgencia
      status: 'En Observación',
      department: 'Pediatría',
      roomNumber: 'OBS-102',
      bedId: 'BED-301',
      doctorAssignedId: 'DOC-104',
      doctorAssignedName: 'Dr. Mateo Benítez Rivas',
      diagnosis: 'Crisis asmática moderada con broncoespasmo severo',
      allergies: 'Aspirina, Polvo de ácaros',
      vitals: { bp: '100/65', hr: '110 lpm', temp: '37.3°C', spo2: '93%' },
      notes: 'Responde favorablemente a micronebulizaciones con salbutamol cada 4 horas.'
    },
    {
      id: 'PAC-804',
      dni: '38192048D',
      name: 'Joaquín Alberto Cruz Peña',
      age: 33,
      gender: 'Masculino',
      bloodType: 'AB-',
      admissionDate: '2026-09-21 16:45',
      triageLevel: 3, // Urgencia
      status: 'Internado',
      department: 'Traumatología',
      roomNumber: 'HAB-210',
      bedId: 'BED-204',
      doctorAssignedId: 'DOC-102',
      doctorAssignedName: 'Dr. Carlos Mendoza Soler',
      diagnosis: 'Fractura diafisaria de fémur derecho desplazada post-accidente de tránsito',
      allergies: 'Ibuprofeno',
      vitals: { bp: '120/80', hr: '76 lpm', temp: '36.6°C', spo2: '99%' },
      notes: 'Osteosíntesis con clavo endomedular exitosa. En plan de analgesia postoperatoria.'
    },
    {
      id: 'PAC-805',
      dni: '19483019E',
      name: 'Beatriz Teresa Domínguez',
      age: 69,
      gender: 'Femenino',
      bloodType: 'O-',
      admissionDate: '2026-09-20 14:10',
      triageLevel: 4, // Menor
      status: 'Internado',
      department: 'Medicina Interna',
      roomNumber: 'HAB-302',
      bedId: 'BED-303',
      doctorAssignedId: 'DOC-105',
      doctorAssignedName: 'Dra. Carmen Navarro Gil',
      diagnosis: 'Descompensación hiperglucémica simple en diabetes mellitus tipo 2',
      allergies: 'Lactosa, Ciprofloxacino',
      vitals: { bp: '130/85', hr: '72 lpm', temp: '36.5°C', spo2: '96%' },
      notes: 'Ajuste de esquema basal-bolo con insulina glargina. Tolerando dieta blanda.'
    },
    {
      id: 'PAC-806',
      dni: '64820194F',
      name: 'Valeria Nicole Morales Soto',
      age: 27,
      gender: 'Femenino',
      bloodType: 'A-',
      admissionDate: '2026-09-23 14:00',
      triageLevel: 4, // Menor
      status: 'Consulta Externa',
      department: 'Urgencias',
      roomNumber: 'Sin asignar',
      bedId: null,
      doctorAssignedId: 'DOC-106',
      doctorAssignedName: 'Dr. Alejandro Silva Torrico',
      diagnosis: 'Gastroenteritis aguda sin deshidratación severa',
      allergies: 'Ninguna',
      vitals: { bp: '115/75', hr: '80 lpm', temp: '37.8°C', spo2: '98%' },
      notes: 'Tratamiento ambulatorio con hidratación oral y antieméticos.'
    }
  ],

  // Citas médicas programadas
  initialAppointments: [
    {
      id: 'APT-501',
      patientId: 'PAC-802',
      patientName: 'Mariana Isabel Vega Castro',
      doctorId: 'DOC-101',
      doctorName: 'Dra. Elena Ramos Morales',
      specialty: 'Cardiología',
      date: '2026-09-23',
      time: '09:00',
      reason: 'Ecocardiograma Doppler de control y seguimiento post-crisis',
      status: 'Finalizada',
      priority: 'Urgente'
    },
    {
      id: 'APT-502',
      patientId: 'PAC-804',
      patientName: 'Joaquín Alberto Cruz Peña',
      doctorId: 'DOC-102',
      doctorName: 'Dr. Carlos Mendoza Soler',
      specialty: 'Traumatología y Ortopedia',
      date: '2026-09-23',
      time: '11:30',
      reason: 'Evaluación de herida quirúrgica y control radiológico de fémur',
      status: 'En Consulta',
      priority: 'Normal'
    },
    {
      id: 'APT-503',
      patientId: 'PAC-803',
      patientName: 'Mateo Alejandro Ríos Flores',
      doctorId: 'DOC-104',
      doctorName: 'Dr. Mateo Benítez Rivas',
      specialty: 'Pediatría',
      date: '2026-09-23',
      time: '16:00',
      reason: 'Control espirométrico y ajuste de broncodilatadores',
      status: 'Programada',
      priority: 'Normal'
    },
    {
      id: 'APT-504',
      patientId: 'PAC-805',
      patientName: 'Beatriz Teresa Domínguez',
      doctorId: 'DOC-105',
      doctorName: 'Dra. Carmen Navarro Gil',
      specialty: 'Neurología',
      date: '2026-09-24',
      time: '10:15',
      reason: 'Descarte de neuropatía diabética periférica con electromiografía',
      status: 'Programada',
      priority: 'Normal'
    },
    {
      id: 'APT-505',
      patientId: 'PAC-806',
      patientName: 'Valeria Nicole Morales Soto',
      doctorId: 'DOC-106',
      doctorName: 'Dr. Alejandro Silva Torrico',
      specialty: 'Urgencias',
      date: '2026-09-24',
      time: '12:00',
      reason: 'Reevaluación de tolerancia oral y alta definitiva',
      status: 'Programada',
      priority: 'Normal'
    }
  ],

  // Estructura de salas y camas hospitalarias
  initialRooms: [
    {
      wing: 'Pabellón de Cuidados Críticos',
      floor: 'Planta 1 - Ala Norte',
      code: 'UCI-P1',
      beds: [
        { id: 'BED-101', code: 'Cama UCI-01', status: 'Ocupada', patientId: 'PAC-801', patientName: 'Lucas Gabriel Herrera', type: 'Intensiva' },
        { id: 'BED-102', code: 'Cama UCI-02', status: 'Libre', patientId: null, patientName: null, type: 'Intensiva' },
        { id: 'BED-103', code: 'Cama UCI-03', status: 'Desinfección', patientId: null, patientName: null, type: 'Aislamiento' },
        { id: 'BED-104', code: 'Cama UCI-04', status: 'Libre', patientId: null, patientName: null, type: 'Intensiva' }
      ]
    },
    {
      wing: 'Hospitalización General y Cirugía',
      floor: 'Planta 2 - Ala Sur',
      code: 'HOSP-P2',
      beds: [
        { id: 'BED-201', code: 'Cama 201-A', status: 'Ocupada', patientId: 'PAC-802', patientName: 'Mariana Isabel Vega', type: 'General' },
        { id: 'BED-202', code: 'Cama 201-B', status: 'Libre', patientId: null, patientName: null, type: 'General' },
        { id: 'BED-203', code: 'Cama 202-A', status: 'Mantenimiento', patientId: null, patientName: null, type: 'General' },
        { id: 'BED-204', code: 'Cama 202-B', status: 'Ocupada', patientId: 'PAC-804', patientName: 'Joaquín Alberto Cruz', type: 'Traumatología' },
        { id: 'BED-205', code: 'Cama 203-A', status: 'Libre', patientId: null, patientName: null, type: 'General' },
        { id: 'BED-206', code: 'Cama 203-B', status: 'Libre', patientId: null, patientName: null, type: 'General' }
      ]
    },
    {
      wing: 'Pediatría y Observación',
      floor: 'Planta 3 - Ala Este',
      code: 'PED-P3',
      beds: [
        { id: 'BED-301', code: 'Cama OBS-01', status: 'Ocupada', patientId: 'PAC-803', patientName: 'Mateo Alejandro Ríos', type: 'Pediátrica' },
        { id: 'BED-302', code: 'Cama OBS-02', status: 'Libre', patientId: null, patientName: null, type: 'Pediátrica' },
        { id: 'BED-303', code: 'Cama 301-A', status: 'Ocupada', patientId: 'PAC-805', patientName: 'Beatriz Teresa Domínguez', type: 'Medicina Interna' },
        { id: 'BED-304', code: 'Cama 301-B', status: 'Libre', patientId: null, patientName: null, type: 'Medicina Interna' }
      ]
    }
  ],

  // Farmacia e insumos críticos
  initialPharmacy: [
    {
      id: 'MED-01',
      name: 'Epinefrina (Adrenalina)',
      generic: 'Epinephrine 1mg/ml Ampolla',
      category: 'Cuidados Críticos',
      stock: 45,
      minStock: 20,
      unit: 'Ampollas',
      batch: 'L-94021',
      expiry: '2027-04-30',
      status: 'Adecuado'
    },
    {
      id: 'MED-02',
      name: 'Salbutamol Solución Nebulizable',
      generic: 'Salbutamol 5mg/ml',
      category: 'Respiratorio',
      stock: 12,
      minStock: 25,
      unit: 'Frascos',
      batch: 'L-83912',
      expiry: '2026-12-15',
      status: 'Bajo'
    },
    {
      id: 'MED-03',
      name: 'Fentanilo Inyectable',
      generic: 'Fentanyl 0.05mg/ml 10ml',
      category: 'Analgésicos Controlados',
      stock: 6,
      minStock: 15,
      unit: 'Ampollas',
      batch: 'L-48190',
      expiry: '2026-11-20',
      status: 'Crítico'
    },
    {
      id: 'MED-04',
      name: 'Solución Fisiológica 0.9%',
      generic: 'Cloruro de Sodio 0.9% 1000ml',
      category: 'Sueros y Fluidos',
      stock: 180,
      minStock: 50,
      unit: 'Bolsas',
      batch: 'L-11928',
      expiry: '2028-01-10',
      status: 'Adecuado'
    },
    {
      id: 'MED-05',
      name: 'Ceftriaxona 1g Polvo Inyectable',
      generic: 'Ceftriaxone Sodium 1g',
      category: 'Antibióticos',
      stock: 8,
      minStock: 30,
      unit: 'Viales',
      batch: 'L-55201',
      expiry: '2026-10-30',
      status: 'Crítico'
    },
    {
      id: 'MED-06',
      name: 'Insulina Glargina 100 UI/ml',
      generic: 'Insulin Glargine Pen 3ml',
      category: 'Endocrinología',
      stock: 35,
      minStock: 20,
      unit: 'Plumas',
      batch: 'L-77402',
      expiry: '2027-02-18',
      status: 'Adecuado'
    }
  ],

  // Versión del esquema del mock: si cambia, se regeneran los datos locales
  // (evita mezclar estructuras antiguas guardadas en el navegador).
  version: '2',

  // Inicializar almacenamiento con persistencia local
  initialize(force = false) {
    if (localStorage.getItem('medipulse_mock_version') !== this.version) {
      force = true;
      localStorage.setItem('medipulse_mock_version', this.version);
    }
    if (force || !localStorage.getItem('medipulse_patients')) {
      localStorage.setItem('medipulse_patients', JSON.stringify(this.initialPatients));
    }
    if (force || !localStorage.getItem('medipulse_doctors')) {
      localStorage.setItem('medipulse_doctors', JSON.stringify(this.initialDoctors));
    }
    if (force || !localStorage.getItem('medipulse_appointments')) {
      localStorage.setItem('medipulse_appointments', JSON.stringify(this.initialAppointments));
    }
    if (force || !localStorage.getItem('medipulse_rooms')) {
      localStorage.setItem('medipulse_rooms', JSON.stringify(this.initialRooms));
    }
    if (force || !localStorage.getItem('medipulse_pharmacy')) {
      localStorage.setItem('medipulse_pharmacy', JSON.stringify(this.initialPharmacy));
    }
  }
};
