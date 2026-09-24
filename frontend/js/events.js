/** Eventos registrados fuera de atributos HTML para una CSP script-src self. */
(function () {
  const actions = {
    a0(event) { MediPulse.Navigation.switchView('view-bi'); },
    a1(event) { MediPulse.Navigation.switchView('view-ai'); },
    a2(event) { MediPulse.Navigation.switchView('view-wizard'); },
    a3(event) { MediPulse.Navigation.switchView('view-data'); },
    a4(event) { MediPulse.Navigation.openApiSettingsModal(); },
    a5(event) { MediPulse.Auth.logout(); },
    a6(event) { MediPulse.BI.applyFilters(); },
    a7(event) { MediPulse.BI.render(); },
    a8(event) { MediPulse.BI.switchTab('tab-exec', this); },
    a9(event) { MediPulse.BI.switchTab('tab-urgency', this); },
    a10(event) { MediPulse.BI.switchTab('tab-resources', this); },
    a11(event) { MediPulse.BI.openDiagnosis(); },
    a12(event) { MediPulse.BI.setAnalysisDate(this.value); },
    a13(event) { MediPulse.BI.setAnalysisDate(null); },
    a14(event) { MediPulse.BI.closeDiagnosis(); },
    a15(event) { MediPulse.BI.loadForecast(); },
    a16(event) { MediPulse.BI.loadForecast(); },
    a17(event) { MediPulse.AI.toggleTechnical(); },
    a18(event) { MediPulse.AI.setMode('local'); },
    a19(event) { MediPulse.AI.setMode('cloud'); },
    a20(event) { MediPulse.AI.clearHistory(); },
    a21(event) { MediPulse.AI.useFewShotPrompt(this.innerText); },
    a22(event) { MediPulse.AI.handleChatSubmit(event); },
    a23(event) { MediPulse.Wizard.reset(); },
    a24(event) { event.preventDefault(); },
    a25(event) { MediPulse.Wizard.prevStep(); },
    a26(event) { MediPulse.Wizard.nextStep(); },
    a27(event) { MediPulse.Wizard.submit(); },
    a28(event) { document.getElementById('file-paciente').click(); },
    a29(event) { MediPulse.DataSync.handleFileSelect(this, 'label-paciente'); },
    a30(event) { MediPulse.DataSync.uploadFile('paciente'); },
    a31(event) { document.getElementById('file-triage').click(); },
    a32(event) { MediPulse.DataSync.handleFileSelect(this, 'label-triage'); },
    a33(event) { MediPulse.DataSync.uploadFile('triage'); },
    a34(event) { document.getElementById('file-ingresos').click(); },
    a35(event) { MediPulse.DataSync.handleFileSelect(this, 'label-ingresos'); },
    a36(event) { MediPulse.DataSync.uploadFile('ingresos'); },
    a37(event) { document.getElementById('file-atencion').click(); },
    a38(event) { MediPulse.DataSync.handleFileSelect(this, 'label-atencion'); },
    a39(event) { MediPulse.DataSync.uploadFile('atencion'); },
    a40(event) { document.getElementById('file-medicamento').click(); },
    a41(event) { MediPulse.DataSync.handleFileSelect(this, 'label-medicamento'); },
    a42(event) { MediPulse.DataSync.uploadFile('medicamento'); },
    a43(event) { document.getElementById('file-servicios').click(); },
    a44(event) { MediPulse.DataSync.handleFileSelect(this, 'label-servicios'); },
    a45(event) { MediPulse.DataSync.uploadFile('servicios'); },
    a46(event) { document.getElementById('file-cirugia').click(); },
    a47(event) { MediPulse.DataSync.handleFileSelect(this, 'label-cirugia'); },
    a48(event) { MediPulse.DataSync.uploadFile('cirugia'); },
    a49(event) { MediPulse.Navigation.closeApiSettingsModal(); },
    a50(event) { document.getElementById('cfg-lat-val').innerText = this.value + 'ms'; },
    a51(event) { MediPulse.Navigation.saveApiSettings(); },
    a52(event) { MediPulse.Auth.submit(event); },
    a53(event) { MediPulse.Auth.enterDemo(); },
  };
  for (const type of ['click', 'change', 'input', 'submit']) {
    document.addEventListener(type, event => {
      const target = event.target.closest(`[data-csp-${type}]`);
      if (!target) return;
      const action = actions[target.getAttribute(`data-csp-${type}`)];
      if (action) action.call(target, event);
    });
  }
})();
