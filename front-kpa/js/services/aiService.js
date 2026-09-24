/**
 * MediPulse OS - Servicio del Asistente IA (NL2SQL + voz)
 * Las consultas usan fallback solo ante caídas de red: si el motor de IA
 * responde con un error, se muestra tal cual (no se inventan respuestas).
 */

window.MediPulse = window.MediPulse || {};

MediPulse.AIService = {
  async providers() {
    return MediPulse.ApiClient.get('/ai/providers', {}, { fallback: 'network-only', timeoutMs: 6000 });
  },

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
