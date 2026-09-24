/**
 * MediPulse OS - Vista: chat del asistente IA (NL2SQL), switch Local/Nube, detalle técnico y dictado por voz.
 * La IA corre en el backend (MediPulse.AIService); aquí solo se captura la pregunta y se pinta la respuesta.
 */

window.MediPulse = window.MediPulse || {};

// 3. VISTA 2: ASISTENTE IA KPA-HEALTH (NL2SQL + GUARDRAILS + VOZ)
// POST /api/ai/query con switch Local (Qwen 3 8B) / Nube. La vista por defecto muestra solo la
// respuesta en lenguaje natural; el detalle técnico (SQL) se ve al activar "Detalle técnico".
MediPulse.AI = {
  mode: localStorage.getItem('medipulse_ai_mode') || 'local',
  showTechnical: localStorage.getItem('medipulse_ai_show_technical') === 'true',
  providers: {},
  voiceStatus: null,
  busy: false,
  maxRenderedRows: 50,
  recorder: null,
  recordingTimer: null,

  async init() {
    this.renderModeSwitch();
    this.applyTechnicalView();
    this.setupVoiceInput();
    await this.refreshProviders();
  },

  async refreshProviders() {
    try {
      const data = await MediPulse.AIService.providers();
      this.providers = Object.fromEntries((data.providers || []).map(p => [p.mode, p]));
      this.voiceStatus = data.voice || null;
      if (!localStorage.getItem('medipulse_ai_mode') && data.defaultMode) this.mode = data.defaultMode;
      // Si el motor elegido no está disponible (p. ej. un PC sin Ollama) y el otro sí, se usa el otro
      const other = this.mode === 'local' ? 'cloud' : 'local';
      if (this.providers[this.mode] && !this.providers[this.mode].available && this.providers[other] && this.providers[other].available) {
        MediPulse.UI.toast(`Motor ${this.mode === 'local' ? 'local' : 'en la nube'} no disponible: se usa el motor ${other === 'local' ? 'local' : 'en la nube'}`, 'info');
        this.mode = other;
      }
    } catch (error) {
      this.providers = {};
      this.voiceStatus = null;
    }
    this.renderModeSwitch();
    this.renderVoiceButton();
  },

  setMode(mode) {
    this.mode = mode;
    localStorage.setItem('medipulse_ai_mode', mode);
    this.renderModeSwitch();
    const provider = this.providers[mode];
    const label = mode === 'local' ? 'Local' : 'Nube';
    if (provider && !provider.available) {
      MediPulse.UI.toast(`Modo ${label}: ${provider.detail}`, 'warning');
    } else {
      MediPulse.UI.toast(`Motor de IA: ${label}${provider ? ` (${provider.model})` : ''}`, 'info');
    }
  },

  renderModeSwitch() {
    ['local', 'cloud'].forEach(mode => {
      const btn = document.getElementById(`ai-mode-${mode}`);
      if (!btn) return;
      const active = this.mode === mode;
      btn.setAttribute('aria-pressed', active);
      btn.className = `px-2 sm:px-2.5 py-1 rounded-md text-[11px] font-bold flex items-center gap-1 transition-all ${active ? 'bg-white text-primary shadow-sm' : 'text-slate-500 hover:text-primary'}`;
    });

    const badge = document.getElementById('ai-status-badge');
    if (!badge) return;
    const provider = this.providers[this.mode];
    const base = 'px-2 py-0.5 rounded-full text-[9px] sm:text-[10px] font-bold border shrink-0';
    if (!provider) {
      badge.className = `${base} bg-rose-100 text-rose-700 border-rose-200`;
      badge.innerText = 'Motor sin conexión';
      badge.title = 'Inicie el backend: uvicorn backend.main:app --port 8000';
    } else if (provider.available) {
      badge.className = `${base} bg-emerald-100 text-emerald-800 border-emerald-200`;
      badge.innerText = `${this.mode === 'local' ? 'Motor local' : 'Motor en la nube'} listo`;
      badge.title = `${provider.model} · ${provider.detail}`;
    } else {
      badge.className = `${base} bg-amber-100 text-amber-800 border-amber-200`;
      badge.innerText = `${this.mode === 'local' ? 'Motor local' : 'Motor en la nube'} no disponible`;
      badge.title = provider.detail;
    }
  },

  // ------------------------------------------------ Detalle técnico (SQL)
  toggleTechnical() {
    this.showTechnical = !this.showTechnical;
    localStorage.setItem('medipulse_ai_show_technical', this.showTechnical);
    this.applyTechnicalView();
    MediPulse.UI.toast(this.showTechnical ? 'Detalle técnico visible (consulta SQL generada)' : 'Vista simplificada: solo la respuesta', 'info');
  },

  applyTechnicalView() {
    const chat = document.getElementById('ai-chat-messages');
    if (chat) chat.classList.toggle('show-technical', this.showTechnical);
    const toggle = document.getElementById('ai-tech-toggle');
    const knob = document.getElementById('ai-tech-knob');
    if (toggle) {
      toggle.setAttribute('aria-checked', this.showTechnical);
      toggle.classList.toggle('bg-secondary', this.showTechnical);
      toggle.classList.toggle('bg-slate-200', !this.showTechnical);
    }
    if (knob) knob.classList.toggle('translate-x-4', this.showTechnical);
  },

  // ------------------------------------------------------------ Voz (Whisper)
  // Feature flag: si MediPulse.Config.ENABLE_VOICE_INPUT es false, el botón NO se crea en el DOM.
  setupVoiceInput() {
    if (!MediPulse.Config.ENABLE_VOICE_INPUT) return;
    const supported = navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder;
    if (!supported) {
      console.info('[MediPulse AI] El navegador no permite grabar audio: el micrófono no se muestra.');
      return;
    }
    const submitBtn = document.getElementById('ai-chat-btn-submit');
    if (!submitBtn || document.getElementById('ai-voice-btn')) return;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.id = 'ai-voice-btn';
    btn.setAttribute('aria-label', 'Dictar pregunta por voz');
    btn.onclick = () => this.toggleRecording();
    submitBtn.parentNode.insertBefore(btn, submitBtn);
    this.renderVoiceButton();
  },

  renderVoiceButton(state = null) {
    const btn = document.getElementById('ai-voice-btn');
    if (!btn) return;
    const recording = this.recorder && this.recorder.state === 'recording';
    const current = state || (recording ? 'recording' : 'idle');
    const base = 'px-3 sm:px-3.5 py-2.5 sm:py-3 rounded-xl font-bold text-xs sm:text-sm shadow-sm transition-all flex items-center gap-1.5 shrink-0 focus:ring-2 focus:ring-secondary/40';
    const voice = this.voiceStatus;
    if (current === 'recording') {
      btn.className = `${base} bg-rose-600 hover:bg-rose-700 text-white voice-recording`;
      btn.innerHTML = '<i data-lucide="square" class="w-4 h-4"></i><span id="ai-voice-timer" class="text-[11px] tabular-nums">0:00</span>';
      btn.title = 'Detener y transcribir';
    } else if (current === 'transcribing') {
      btn.className = `${base} bg-slate-200 text-slate-600 cursor-wait`;
      btn.innerHTML = '<div class="w-4 h-4 border-2 border-secondary border-t-transparent rounded-full animate-spin"></div>';
      btn.title = 'Transcribiendo con Whisper local…';
    } else {
      btn.className = `${base} bg-white border border-slate-300 text-secondary hover:bg-secondary/5`;
      btn.innerHTML = '<i data-lucide="mic" class="w-4 h-4"></i>';
      btn.title = voice && voice.enabled
        ? `Dictar pregunta (voz local · ${voice.model || 'whisper'}${voice.loaded ? '' : ' · se carga en el primer uso'})`
        : 'Dictar pregunta por voz';
    }
    btn.disabled = current === 'transcribing';
    lucide.createIcons();
  },

  async toggleRecording() {
    if (this.recorder && this.recorder.state === 'recording') {
      this.recorder.stop();
      return;
    }
    if (this.busy) {
      MediPulse.UI.toast('Espere a que termine la consulta en curso', 'warning');
      return;
    }
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (error) {
      MediPulse.UI.toast('No se pudo acceder al micrófono. Revise los permisos del navegador.', 'error');
      return;
    }
    const mimeType = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4']
      .find(type => window.MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(type)) || '';
    const chunks = [];
    this.recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    this.recorder.ondataavailable = event => { if (event.data && event.data.size) chunks.push(event.data); };
    this.recorder.onstop = async () => {
      clearInterval(this.recordingTimer);
      stream.getTracks().forEach(track => track.stop());
      const blob = new Blob(chunks, { type: this.recorder.mimeType || mimeType || 'audio/webm' });
      await this.transcribe(blob);
    };
    this.recorder.start();
    const started = Date.now();
    this.renderVoiceButton('recording');
    MediPulse.UI.toast('Grabando… habla en español y presiona de nuevo para terminar', 'info');
    this.recordingTimer = setInterval(() => {
      const seconds = Math.floor((Date.now() - started) / 1000);
      setText('ai-voice-timer', `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`);
      if (Date.now() - started >= MediPulse.Config.VOICE_MAX_RECORDING_MS && this.recorder.state === 'recording') {
        this.recorder.stop();
      }
    }, 250);
  },

  async transcribe(blob) {
    if (!blob.size) {
      this.renderVoiceButton('idle');
      MediPulse.UI.toast('No se detectó audio en la grabación', 'warning');
      return;
    }
    this.renderVoiceButton('transcribing');
    try {
      const result = await MediPulse.AIService.transcribe(blob);
      const text = (result.text || '').trim();
      if (!text) {
        MediPulse.UI.toast('No se reconoció ninguna pregunta en el audio', 'warning');
        return;
      }
      const input = document.getElementById('ai-chat-input');
      input.value = text;
      input.focus();
      MediPulse.UI.toast(`Transcripción lista (${(result.elapsedMs / 1000).toFixed(1)} s). Revise y presione Enviar.`, 'success');
      if (MediPulse.Config.VOICE_AUTO_SUBMIT) {
        input.value = '';
        this.processQuery(text);
      }
    } catch (error) {
      const message = error.status === 501 ? 'El reconocimiento de voz está deshabilitado en el servidor' : error.message;
      MediPulse.UI.toast(message, 'error');
    } finally {
      this.renderVoiceButton('idle');
    }
  },

  // ---------------------------------------------------------------- Chat
  useFewShotPrompt(text) {
    const query = text.trim();
    document.getElementById('ai-chat-input').value = query;
    this.processQuery(query);
  },

  handleChatSubmit(e) {
    e.preventDefault();
    const input = document.getElementById('ai-chat-input');
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    this.processQuery(text);
  },

  async processQuery(userQuery) {
    if (this.busy) {
      MediPulse.UI.toast('Espere a que termine la consulta en curso', 'warning');
      return;
    }
    this.busy = true;
    const chatContainer = document.getElementById('ai-chat-messages');
    const submitBtn = document.getElementById('ai-chat-btn-submit');
    if (submitBtn) submitBtn.disabled = true;

    // Mensaje Usuario (texto escapado y sin documentos de identidad)
    const userMsg = document.createElement('div');
    userMsg.className = 'flex items-start justify-end space-x-2.5';
    userMsg.innerHTML = `
      <div class="bg-primary text-white rounded-2xl rounded-tr-sm p-3.5 text-xs max-w-lg shadow-sm">
        <p class="font-semibold">${MediPulse.UI.escape(MediPulse.Privacy.scrubText(userQuery))}</p>
      </div>
      <div class="w-8 h-8 rounded-xl bg-secondary text-white flex items-center justify-center font-bold text-xs shrink-0 shadow-sm">
        TÚ
      </div>
    `;
    chatContainer.appendChild(userMsg);

    // Indicador Cargando
    const loadingMsg = document.createElement('div');
    loadingMsg.className = 'flex items-start space-x-2.5 max-w-2xl';
    loadingMsg.innerHTML = `
      <div class="w-8 h-8 rounded-xl bg-primary text-white flex items-center justify-center shrink-0">
        <i data-lucide="sparkles" class="w-4 h-4 text-tertiary"></i>
      </div>
      <div class="bg-slate-50 border border-slate-200 rounded-2xl rounded-tl-sm p-3.5 text-xs text-slate-500 flex items-center space-x-2">
        <div class="w-3.5 h-3.5 border-2 border-secondary border-t-transparent rounded-full animate-spin"></div>
        <span>Analizando la información del hospital…</span>
      </div>
    `;
    chatContainer.appendChild(loadingMsg);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    lucide.createIcons();

    try {
      const data = await MediPulse.AIService.query(userQuery, this.mode);
      loadingMsg.remove();
      chatContainer.appendChild(this.renderAnswer(data));
    } catch (error) {
      loadingMsg.remove();
      chatContainer.appendChild(this.renderError(error.message));
    } finally {
      this.busy = false;
      if (submitBtn) submitBtn.disabled = false;
      chatContainer.scrollTop = chatContainer.scrollHeight;
      lucide.createIcons();
    }
  },

  renderAnswer(data) {
    const e = v => MediPulse.UI.escape(v);
    const t = data.timings || {};
    const hospital = (data.category || 'hospital') === 'hospital';
    const labels = (data.columnLabels && data.columnLabels.length) ? data.columnLabels : (data.columns || []);
    const rows = MediPulse.Privacy.maskTable(data.columns || [], data.rows || []);
    const engineLabel = data.fromMock ? 'Respaldo · datos simulados'
      : `${data.mode === 'local' ? 'Motor local' : 'Motor en la nube'} · ${data.model}`;

    let title = 'Respuesta del asistente';
    let icon = 'check-circle-2';
    let iconColor = 'text-emerald-600';
    if (!hospital) {
      // Categorías del contrato de /api/ai/query (backend/services/ai_agent/guardrails/messages.py)
      const titles = { greeting: 'Asistente KPA-Health', out_of_scope: 'Fuera del alcance del asistente', unsupported_language: 'Idioma no soportado', personal_data: 'Protección de datos personales', empty: 'Asistente KPA-Health' };
      title = titles[data.category] || 'Asistente KPA-Health';
      icon = data.category === 'personal_data' ? 'shield-check' : (data.category === 'greeting' ? 'sparkles' : 'info');
      iconColor = data.category === 'personal_data' ? 'text-primary' : 'text-secondary';
    } else if (!data.success) {
      title = 'No pude obtener esa información';
      icon = 'alert-triangle';
      iconColor = 'text-amber-600';
    }

    // Tabla de resultados (etiquetas en español; las respuestas de un solo dato se leen en el texto)
    const table = rows.length > 1 ? `
      <div class="overflow-x-auto rounded-xl border border-slate-200 bg-white max-h-80">
        ${this.renderTable(labels, rows)}
      </div>` : '';
    const technicalTable = rows.length === 1 ? `
      <div class="ai-tech overflow-x-auto rounded-xl border border-slate-200 bg-white">
        ${this.renderTable(labels, rows)}
      </div>` : '';

    const sqlBlock = data.sql ? `
      <div class="ai-tech rounded-xl overflow-hidden border border-emerald-950/40">
        <div class="bg-primary-dark text-tertiary text-[10px] font-bold px-3 py-1.5 flex justify-between items-center font-mono gap-2">
          <span>CONSULTA SQL GENERADA</span>
          <span class="text-white/60">IA ${e(t.llmMs ?? 0)} ms · SQL ${e(t.sqlMs ?? 0)} ms</span>
        </div>
        <pre class="sql-code-block p-3 text-[11px] overflow-x-auto"><code>${e(data.sql)}</code></pre>
      </div>` : '';

    const attempts = (data.attempts || []).length ? `
      <details class="ai-tech rounded-xl border border-amber-200 bg-amber-50 p-2.5 text-[11px] text-amber-900">
        <summary class="font-bold cursor-pointer">Autocorrección: ${data.attempts.length} intento(s) rechazado(s) por el validador</summary>
        ${data.attempts.map(a => `
          <pre class="mt-2 p-2 bg-white rounded border border-amber-100 overflow-x-auto"><code>${e(a.sql)}</code></pre>
          <p class="mt-1">${e(a.error)}</p>
        `).join('')}
      </details>` : '';

    const technicalMeta = [
      data.explanation ? `Interpretación: ${e(data.explanation)}` : '',
      data.blockedBy ? `Filtrado por: ${data.blockedBy === 'input_guard' ? 'guardrail de entrada (sin usar el modelo)' : 'clasificación del modelo'}` : '',
      `Categoría: ${e(data.category || 'hospital')}`,
      t.totalMs ? `Tiempo total ${(t.totalMs / 1000).toFixed(1)} s` : '',
      ...(data.warnings || []).map(w => e(w))
    ].filter(Boolean);

    const shown = Math.min(rows.length, this.maxRenderedRows);
    const footer = [
      data.referenceDate ? `Datos al ${fmtDate(data.referenceDate)}` : '',
      rows.length > 1 ? `${fmtNumber(data.rowCount)} resultado(s)${data.rowCount > shown ? ` · se muestran ${shown}` : ''}` : ''
    ].filter(Boolean).join(' · ');

    const aiMsg = document.createElement('div');
    aiMsg.className = 'flex items-start space-x-2.5 sm:space-x-3.5 max-w-3xl animate-in fade-in duration-200';
    aiMsg.innerHTML = `
      <div class="w-8 h-8 sm:w-9 sm:h-9 rounded-xl bg-primary text-white flex items-center justify-center shrink-0 shadow-sm">
        <i data-lucide="bot" class="w-4 h-4 sm:w-5 sm:h-5 text-tertiary"></i>
      </div>
      <div class="bg-slate-50 border border-slate-200 rounded-2xl rounded-tl-sm p-4 sm:p-5 text-xs text-slate-800 space-y-3 shadow-sm w-full min-w-0">
        <div class="flex items-center justify-between gap-2 flex-wrap">
          <p class="font-bold text-primary flex items-center gap-1.5">
            <i data-lucide="${icon}" class="w-4 h-4 ${iconColor}"></i>
            ${title}
          </p>
          <span class="ai-tech px-2 py-0.5 rounded-full text-[10px] font-bold bg-tertiary-light text-primary border border-tertiary">${e(engineLabel)}</span>
        </div>
        <p class="text-slate-700 leading-relaxed text-[13px]">${e(MediPulse.Privacy.scrubText(data.answer))}</p>
        ${table}
        ${sqlBlock}
        ${technicalTable}
        ${attempts}
        ${technicalMeta.length ? `<div class="ai-tech text-[10px] text-slate-500 space-y-0.5">${technicalMeta.map(m => `<p>${m}</p>`).join('')}</div>` : ''}
        ${footer ? `<p class="text-[10px] text-slate-400">${footer}</p>` : ''}
        ${data.fromMock ? '<p class="text-[10px] text-amber-700">Respuesta en modo respaldo con datos simulados: el motor de IA no está disponible.</p>' : ''}
      </div>
    `;
    return aiMsg;
  },

  renderTable(labels, rows) {
    const e = v => MediPulse.UI.escape(v);
    const format = cell => (typeof cell === 'number' ? fmtNumber(cell, Number.isInteger(cell) ? 0 : 1) : e(cell));
    const body = rows.slice(0, this.maxRenderedRows).map(row => `
      <tr>${row.map(cell => `<td class="p-2 text-slate-700 whitespace-nowrap">${cell === null ? '<span class="text-slate-300">—</span>' : format(cell)}</td>`).join('')}</tr>
    `).join('');
    return `
      <table class="w-full text-left text-xs">
        <thead class="bg-slate-100 text-slate-500 font-bold uppercase text-[10px] sticky top-0">
          <tr>${labels.map(c => `<th class="p-2 whitespace-nowrap">${e(c)}</th>`).join('')}</tr>
        </thead>
        <tbody class="divide-y divide-slate-100">
          ${body || `<tr><td class="p-2 text-slate-400" colspan="${labels.length}">Sin resultados</td></tr>`}
        </tbody>
      </table>
    `;
  },

  renderError(message) {
    const errorMsg = document.createElement('div');
    errorMsg.className = 'flex items-start space-x-2.5 sm:space-x-3.5 max-w-3xl';
    errorMsg.innerHTML = `
      <div class="w-8 h-8 sm:w-9 sm:h-9 rounded-xl bg-rose-600 text-white flex items-center justify-center shrink-0 shadow-sm">
        <i data-lucide="alert-circle" class="w-4 h-4 sm:w-5 sm:h-5"></i>
      </div>
      <div class="bg-rose-50 border border-rose-200 rounded-2xl rounded-tl-sm p-4 text-xs text-rose-900 space-y-1.5 shadow-sm">
        <p class="font-bold">No pude responder en este momento</p>
        <p>${MediPulse.UI.escape(message)}</p>
        <p class="text-[10px] text-rose-700">Verifique que el servidor del hospital esté activo y que el motor de IA seleccionado esté disponible.</p>
      </div>
    `;
    this.refreshProviders();
    return errorMsg;
  },

  clearHistory() {
    const container = document.getElementById('ai-chat-messages');
    container.innerHTML = `
      <div class="flex items-start space-x-2.5 sm:space-x-3.5 max-w-3xl">
        <div class="w-8 h-8 sm:w-9 sm:h-9 rounded-xl bg-primary text-white flex items-center justify-center shrink-0 shadow-sm">
          <i data-lucide="sparkles" class="w-4 h-4 sm:w-5 sm:h-5 text-tertiary"></i>
        </div>
        <div class="bg-slate-50 border border-slate-200 rounded-2xl rounded-tl-sm p-3.5 sm:p-4 text-xs text-slate-800 leading-relaxed shadow-sm">
          <p class="font-bold text-primary mb-1">Conversación reiniciada</p>
          <p>¡Hola de nuevo! Soy tu asistente KPA-Health del Hospital Susana López de Valencia E.S.E. ¿En qué puedo ayudarte hoy?</p>
        </div>
      </div>
    `;
    this.applyTechnicalView();
    lucide.createIcons();
    MediPulse.UI.toast('Historial del chat limpiado', 'info');
  }
};

// MediPulse.AI.init() lo invoca MediPulse.Auth al abrir la sesión (requiere el permiso 'assistant')
