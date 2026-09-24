/**
 * MediPulse OS - Servicio del Asistente IA (NL2SQL + voz)
 * Las consultas usan fallback solo ante caídas de red: si el motor de IA
 * responde con un error, se muestra tal cual (no se inventan respuestas).
 */

window.MediPulse = window.MediPulse || {};

MediPulse.AIService = {
  /** Estado de los motores Local/Nube y de la voz (GET /api/ai/providers). */
  async providers() {
    return MediPulse.ApiClient.get('/ai/providers', {}, { fallback: 'network-only', timeoutMs: 6000 });
  },

  /**
   * Envía una pregunta al agente NL2SQL.
   * @param {string} question Pregunta en español.
   * @param {'local'|'cloud'} [mode] Motor elegido en el switch (vacío = el del servidor).
   * @returns {Promise<object>} AIQueryResponse: answer, category (hospital | greeting | out_of_scope |
   *   unsupported_language | personal_data | empty), blockedBy (null | input_guard | model), sql, rows...
   */
  async query(question, mode) {
    const response = await MediPulse.ApiClient.post('/ai/query', { question, mode }, {
      fallback: 'network-only',
      timeoutMs: MediPulse.Config.aiTimeoutMs
    });
    response.fromMock = MediPulse.ApiClient.isMock(response);
    return response;
  },

  /** Voz a texto 100 % local (faster-whisper en el backend). */
  async transcribe(audioBlob) {
    const extension = (audioBlob.type || '').includes('mp4') ? 'mp4' : (audioBlob.type || '').includes('ogg') ? 'ogg' : 'webm';
    const file = new File([audioBlob], `pregunta.${extension}`, { type: audioBlob.type || 'audio/webm' });
    return MediPulse.ApiClient.upload('/ai/transcribe', file, 'audio', { timeoutMs: 120000 });
  }
};
