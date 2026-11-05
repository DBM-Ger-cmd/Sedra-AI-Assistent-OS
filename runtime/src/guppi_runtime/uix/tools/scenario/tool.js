(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  function human(nodes){
    const n = root.sedraWorkflowModel.node('noOp', nodes);n.name = 'Menschliche Prüfung ' + n.id.slice(-4);
    const p = root.sedraWorkflowProcess.blank(n);p.mode = 'manual';p.evidence = 'Dokumentierte menschliche Entscheidung';root.sedraWorkflowProcess.set(n, p);return n;
  }
  root.sedra.registerTool(root.sedraWorkflowEditor.create({id: 'scenario', title: 'Szenario Studio',
    objectType: 'scenario', style: 'scenario', className: 't-scenario',
    otherTitle: 'n8n Workflows', otherType: 'workflow', routeTitle: 'Routen', runTitle: 'Szenarioläufe',
    inspector: root.sedraScenarioForms.inspect, renderRun: root.sedraScenarioForms.run,
    palette: [{kind: 'manualTrigger', label: 'Auslöser'}, {kind: 'set', label: 'Daten bearbeiten'},
      {kind: 'if', label: 'Router (Ja/Nein)'}, {kind: 'noOp', label: 'Weitergabe'},
      {label: 'Menschliche Prüfung', make: human}, {kind: 'stickyNote', label: 'Notiz'}]}));
})();
