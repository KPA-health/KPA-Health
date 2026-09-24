/**
 * MediPulse OS - Vista: asistente (wizard) de ingreso de pacientes en pasos.
 * Las reglas (cama libre, privacidad) las valida el backend; los errores 409/404 refrescan las camas.
 */

window.MediPulse = window.MediPulse || {};

// 4. VISTA 3: GESTIÓN DE INGRESOS (WIZARD RELACIONAL) — POST real a /api/patients
MediPulse.Wizard = {
  step: 1,
  submitting: false,

  async prepare() {
    await Promise.allSettled([this.loadDepartments(), this.loadDoctors()]);
    await this.filterAvailableBeds();
  },

  nextStep() {
    if (this.step === 1) {
      const name = document.getElementById('wiz-name').value.trim();
      const dni = document.getElementById('wiz-dni').value.trim();
      if (!name || !dni) {
        MediPulse.UI.toast('Complete el Nombre Completo y Documento', 'warning');
        return;
      }
      this.setStep(2);
    } else if (this.step === 2) {
      const symptoms = document.getElementById('wiz-symptoms').value.trim();
      if (!symptoms) {
        MediPulse.UI.toast('Ingrese el motivo de consulta del paciente', 'warning');
        return;
      }
      this.filterAvailableBeds();
      this.setStep(3);
    }
  },

  prevStep() {
    if (this.step > 1) {
      this.setStep(this.step - 1);
    }
  },

  setStep(newStep) {
    this.step = newStep;

    document.querySelectorAll('.wizard-step').forEach(el => el.classList.add('hidden'));
    document.getElementById(`wizard-step-${newStep}`).classList.remove('hidden');

    for (let i = 1; i <= 3; i++) {
      const indicator = document.getElementById(`wizard-step-indicator-${i}`);
      if (i === newStep) {
        indicator.className = 'w-9 h-9 sm:w-10 sm:h-10 rounded-full bg-secondary text-white font-black text-xs sm:text-sm flex items-center justify-center ring-4 ring-tertiary-light shadow-md transition-all';
        indicator.innerText = i;
      } else if (i < newStep) {
        indicator.className = 'w-9 h-9 sm:w-10 sm:h-10 rounded-full bg-emerald-600 text-white font-black text-xs sm:text-sm flex items-center justify-center shadow transition-all';
        indicator.innerHTML = '<i data-lucide="check" class="w-4 h-4 sm:w-5 sm:h-5"></i>';
      } else {
        indicator.className = 'w-9 h-9 sm:w-10 sm:h-10 rounded-full bg-slate-200 text-slate-600 font-black text-xs sm:text-sm flex items-center justify-center ring-4 ring-white shadow transition-all';
        indicator.innerText = i;
      }
    }

    const progressLine = document.getElementById('wizard-progress-line');
    if (newStep === 1) progressLine.style.width = '0%';
    if (newStep === 2) progressLine.style.width = '50%';
    if (newStep === 3) progressLine.style.width = '100%';

    const btnPrev = document.getElementById('wizard-btn-prev');
    const btnNext = document.getElementById('wizard-btn-next');
    const btnSubmit = document.getElementById('wizard-btn-submit');

    if (newStep === 1) {
      btnPrev.disabled = true;
      btnPrev.className = 'px-4 sm:px-5 py-2.5 rounded-xl border border-slate-300 text-slate-400 bg-slate-100 font-bold text-xs transition-all flex items-center gap-1.5 cursor-not-allowed';
      btnNext.classList.remove('hidden');
      btnSubmit.classList.add('hidden');
    } else if (newStep === 2) {
      btnPrev.disabled = false;
      btnPrev.className = 'px-4 sm:px-5 py-2.5 rounded-xl border border-slate-300 text-slate-700 bg-white hover:bg-slate-50 font-bold text-xs transition-all flex items-center gap-1.5 cursor-pointer';
      btnNext.classList.remove('hidden');
      btnSubmit.classList.add('hidden');
    } else if (newStep === 3) {
      btnPrev.disabled = false;
      btnPrev.className = 'px-4 sm:px-5 py-2.5 rounded-xl border border-slate-300 text-slate-700 bg-white hover:bg-slate-50 font-bold text-xs transition-all flex items-center gap-1.5 cursor-pointer';
      btnNext.classList.add('hidden');
      btnSubmit.classList.remove('hidden');
    }

    lucide.createIcons();
  },

  // Resalta visualmente el nivel de triaje seleccionado
  bindTriageSelector() {
    const radios = document.querySelectorAll('input[name="wiz-triage"]');
    const paint = () => radios.forEach(radio => {
      const label = radio.closest('label');
      label.classList.toggle('border-secondary', radio.checked);
      label.classList.toggle('bg-secondary/5', radio.checked);
      label.classList.toggle('ring-2', radio.checked);
      label.classList.toggle('ring-secondary/30', radio.checked);
    });
    radios.forEach(radio => radio.addEventListener('change', paint));
    paint();
  },

  // Servicios reales (camas del hospital) con respaldo a la lista de config.js
  async loadDepartments() {
    const select = document.getElementById('wiz-department');
    const previous = select.value;
    let services = [];
    try {
      const wings = await MediPulse.RoomService.getAll();
      if (wings.source === 'api') services = [...new Set(wings.map(w => w.floor))].sort();
    } catch (error) { /* se mantiene la lista por defecto */ }
    if (!services.length) services = MediPulse.Config.hospital.departments;
    select.innerHTML = services.map(s => `<option value="${MediPulse.UI.escape(s)}">${MediPulse.UI.escape(s)}</option>`).join('');
    select.value = services.includes(previous) ? previous : services[0];
    select.onchange = () => this.filterAvailableBeds();
  },

  async loadDoctors() {
    const select = document.getElementById('wiz-doctor');
    try {
      const doctors = await MediPulse.DoctorService.getAll();
      if (!doctors.length) return;
      const previous = select.value;
      select.innerHTML = doctors.map(d =>
        `<option value="${MediPulse.UI.escape(d.name)}" data-id="${MediPulse.UI.escape(d.id)}">${MediPulse.UI.escape(d.name)} - ${MediPulse.UI.escape(d.specialty || '')}</option>`
      ).join('');
      if ([...select.options].some(o => o.value === previous)) select.value = previous;
    } catch (error) { /* se conservan las opciones estáticas */ }
  },

  async filterAvailableBeds() {
    const bedSelect = document.getElementById('wiz-bed');
    const department = document.getElementById('wiz-department').value;
    const hint = document.getElementById('wiz-bed-hint');
    bedSelect.innerHTML = '<option value="">Cargando camas libres…</option>';
    try {
      const { beds, filtered, source } = await MediPulse.RoomService.getFreeBeds(department);
      bedSelect.innerHTML = '';
      if (!beds.length) {
        bedSelect.innerHTML = '<option value="">⚠️ No hay camas libres en este momento</option>';
      } else {
        const byWing = {};
        beds.forEach(bed => { (byWing[bed.wing] = byWing[bed.wing] || []).push(bed); });
        Object.entries(byWing).forEach(([wing, wingBeds]) => {
          const group = document.createElement('optgroup');
          group.label = wing;
          wingBeds.forEach(bed => {
            const opt = document.createElement('option');
            opt.value = bed.id;
            opt.setAttribute('data-code', bed.code);
            opt.innerText = `${bed.code} (${bed.service || wing})`;
            group.appendChild(opt);
          });
          bedSelect.appendChild(group);
        });
      }
      if (hint) {
        hint.textContent = `${beds.length} camas libres${filtered ? ` en ${department}` : ' (todas las áreas)'}${source === 'mock' ? ' · datos simulados' : ' · en vivo'}`;
      }
    } catch (error) {
      bedSelect.innerHTML = '<option value="">⚠️ No se pudieron cargar las camas</option>';
      MediPulse.UI.toast(`No se pudieron cargar las camas: ${error.message}`, 'error');
    }
  },

  async submit() {
    if (this.submitting) return;
    const bedSelect = document.getElementById('wiz-bed');
    const selectedBedId = bedSelect.value;
    const selectedBedCode = bedSelect.options[bedSelect.selectedIndex]?.getAttribute('data-code') || 'Cama Asignada';

    if (!selectedBedId) {
      MediPulse.UI.toast('Seleccione una cama disponible para continuar', 'error');
      return;
    }

    const selectedTriageRadio = document.querySelector('input[name="wiz-triage"]:checked');
    const triageLevel = selectedTriageRadio ? parseInt(selectedTriageRadio.value, 10) : 3;
    const doctorSelect = document.getElementById('wiz-doctor');
    const doctorOption = doctorSelect.options[doctorSelect.selectedIndex];

    // Los datos personales viajan solo en esta petición: el backend no guarda el nombre
    // (usa un seudónimo) y guarda el documento únicamente como hash.
    const payload = {
      name: document.getElementById('wiz-name').value.trim(),
      dni: document.getElementById('wiz-dni').value.trim(),
      age: parseInt(document.getElementById('wiz-age').value, 10) || 30,
      gender: document.getElementById('wiz-gender').value,
      bloodType: document.getElementById('wiz-blood').value,
      allergies: document.getElementById('wiz-allergies').value || 'Ninguna',
      triageLevel: triageLevel,
      vitals: {
        bp: document.getElementById('wiz-bp').value,
        hr: document.getElementById('wiz-hr').value + ' lpm',
        temp: document.getElementById('wiz-temp').value + '°C',
        spo2: document.getElementById('wiz-spo2').value + '%'
      },
      symptoms: document.getElementById('wiz-symptoms').value,
      department: document.getElementById('wiz-department').value,
      roomNumber: selectedBedCode,
      bedId: selectedBedId,
      doctorName: doctorSelect.value,
      doctorAssignedId: doctorOption ? doctorOption.getAttribute('data-id') : null,
      status: document.getElementById('wiz-status').value,
      diagnosis: document.getElementById('wiz-diagnosis').value.trim()
    };

    const submitBtn = document.getElementById('wizard-btn-submit');
    this.submitting = true;
    submitBtn.disabled = true;
    submitBtn.classList.add('opacity-60');
    try {
      const patient = await MediPulse.PatientService.create(payload);
      const safe = MediPulse.Privacy.maskPatient(patient);
      MediPulse.UI.toast(`¡Ingreso registrado! ${safe.name} asignado a ${patient.roomNumber || selectedBedCode}`, 'success');
      if (MediPulse.ApiClient.status === 'fallback' || MediPulse.ApiClient.status === 'mock') {
        MediPulse.UI.toast('Guardado en modo respaldo local: no se envió a hospital.db', 'warning');
      }
      this.reset();
      MediPulse.Navigation.switchView('view-bi');  // el dashboard se recalcula con el nuevo ingreso
    } catch (error) {
      MediPulse.UI.toast(`No se pudo registrar el ingreso: ${error.message}`, 'error');
      if (error.status === 409 || error.status === 404) this.filterAvailableBeds();
    } finally {
      this.submitting = false;
      submitBtn.disabled = false;
      submitBtn.classList.remove('opacity-60');
    }
  },

  reset() {
    document.getElementById('wizard-admission-form').reset();
    this.setStep(1);
    document.querySelectorAll('input[name="wiz-triage"]').forEach(r => r.dispatchEvent(new Event('change')));
  }
};
