/**
 * MediPulse OS - Utilidades de presentación compartidas por las vistas (formato de números/fechas y DOM).
 * Se declaran como constantes globales porque las usan varias vistas; se cargan antes que ellas.
 */

window.MediPulse = window.MediPulse || {};

// Utilidades de presentación compartidas por los módulos de la SPA
const fmtNumber = (value, decimals = 0) => (value === null || value === undefined || Number.isNaN(Number(value)))
  ? '—'
  : Number(value).toLocaleString('es-CO', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
const fmtDate = iso => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}` : '—');
const setText = (id, value) => { const el = document.getElementById(id); if (el) el.textContent = value; };
