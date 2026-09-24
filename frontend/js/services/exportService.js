/**
 * MediPulse OS - Servicio de exportación: CSV (JavaScript puro + Blob) y PDF visual (html2canvas + jsPDF).
 * Las librerías del PDF se descargan solo la primera vez que se pide un PDF: no pesan en la carga inicial.
 */

window.MediPulse = window.MediPulse || {};

MediPulse.ExportService = {
  libs: {
    html2canvas: 'https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js',
    jspdf: 'https://cdn.jsdelivr.net/npm/jspdf@2.5.1/dist/jspdf.umd.min.js'
  },
  loading: {},

  /** Celda CSV (RFC 4180): comillas si trae separador, comillas o saltos de línea. */
  csvCell(value) {
    if (value === null || value === undefined) return '';
    const text = String(value);
    return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  },

  /** Tabla -> texto CSV. `sections` permite varias tablas en un archivo: [{ title, headers, rows }]. */
  toCSV(sections) {
    return sections.map(({ title, headers, rows }) => [
      title ? this.csvCell(title) : null,
      headers.map(h => this.csvCell(h)).join(','),
      ...rows.map(row => row.map(cell => this.csvCell(cell)).join(','))
    ].filter(line => line !== null).join('\r\n')).join('\r\n\r\n');
  },

  /** Descarga un CSV. El BOM hace que Excel abra las tildes y la ñ correctamente. */
  downloadCSV(filename, sections) {
    const blob = new Blob(['﻿', this.toCSV(sections)], { type: 'text/csv;charset=utf-8' });
    this.downloadBlob(blob, filename);
  },

  downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  },

  /** Nombre de archivo con fecha: kpa-health-dashboard-2026-09-24.csv */
  filename(base, extension) {
    const today = new Date();
    const pad = n => String(n).padStart(2, '0');
    return `kpa-health-${base}-${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}.${extension}`;
  },

  loadScript(key) {
    if (!this.loading[key]) {
      this.loading[key] = new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = this.libs[key];
        script.onload = resolve;
        script.onerror = () => {
          delete this.loading[key];
          reject(new Error('No se pudo descargar la librería de PDF (revise la conexión a internet)'));
        };
        document.head.appendChild(script);
      });
    }
    return this.loading[key];
  },

  /**
   * Captura un elemento (con sus gráficos de Chart.js) y lo guarda como PDF A4 de varias páginas.
   * Los elementos con `data-html2canvas-ignore` (botones, menús) no salen en el reporte.
   */
  async downloadElementPDF(element, filename, { title = '', subtitle = '' } = {}) {
    await Promise.all([this.loadScript('html2canvas'), this.loadScript('jspdf')]);
    const canvas = await window.html2canvas(element, {
      scale: Math.min(2, window.devicePixelRatio || 1.5),
      backgroundColor: '#ffffff',
      useCORS: true,
      logging: false,
      windowWidth: Math.max(element.scrollWidth, 1280)
    });

    const { jsPDF } = window.jspdf;
    const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
    const pageWidth = pdf.internal.pageSize.getWidth();
    const pageHeight = pdf.internal.pageSize.getHeight();
    const margin = 10;
    const header = title ? 14 : 0;
    const contentWidth = pageWidth - 2 * margin;
    const contentHeight = pageHeight - 2 * margin - header;

    // La imagen se corta en franjas del alto de una página
    const pxPerMm = canvas.width / contentWidth;
    const sliceHeightPx = Math.floor(contentHeight * pxPerMm);
    const pages = Math.max(1, Math.ceil(canvas.height / sliceHeightPx));
    for (let page = 0; page < pages; page++) {
      if (page > 0) pdf.addPage();
      if (title) {
        pdf.setFontSize(12);
        pdf.setTextColor(31, 74, 42);
        pdf.text(title, margin, margin + 4);
        pdf.setFontSize(8);
        pdf.setTextColor(100, 116, 139);
        pdf.text(`${subtitle}${subtitle ? ' · ' : ''}Página ${page + 1} de ${pages}`, margin, margin + 9);
      }
      const slice = document.createElement('canvas');
      slice.width = canvas.width;
      slice.height = Math.min(sliceHeightPx, canvas.height - page * sliceHeightPx);
      slice.getContext('2d').drawImage(canvas, 0, page * sliceHeightPx, canvas.width, slice.height, 0, 0, canvas.width, slice.height);
      pdf.addImage(slice.toDataURL('image/jpeg', 0.92), 'JPEG', margin, margin + header, contentWidth, slice.height / pxPerMm);
    }
    pdf.save(filename);
  }
};
