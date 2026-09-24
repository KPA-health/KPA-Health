/**
 * MediPulse OS - Servicio de Camas y Pabellones
 */

window.MediPulse = window.MediPulse || {};

MediPulse.RoomService = {
  async getAll() {
    const response = await MediPulse.ApiClient.get('/rooms');
    const wings = response.data || [];
    wings.source = MediPulse.ApiClient.isMock(response) ? 'mock' : 'api';
    return wings;
  },

  /** Camas libres; si se indica un servicio y existen camas de ese servicio, se filtran. */
  async getFreeBeds(service) {
    const wings = await this.getAll();
    const beds = wings.flatMap(w => w.beds.map(b => ({ ...b, wing: w.wing, service: w.floor })));
    const free = beds.filter(b => b.status === 'Libre');
    const ofService = service ? free.filter(b => b.type === service || b.service === service) : [];
    return { beds: ofService.length ? ofService : free, filtered: ofService.length > 0, source: wings.source, all: beds };
  },

  async updateStatus(bedId, status, patientId = null) {
    return MediPulse.ApiClient.put('/rooms/bed-status', { bedId, status, patientId });
  },

  async releaseBed(bedId) {
    return this.updateStatus(bedId, 'Auto');
  }
};
