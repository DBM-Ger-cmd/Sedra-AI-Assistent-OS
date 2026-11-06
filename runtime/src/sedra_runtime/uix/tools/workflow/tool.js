(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  root.sedra.registerTool(root.sedraWorkflowEditor.create({id: 'workflow', title: 'n8n Workflows',
    objectType: 'workflow', style: 'diagram', className: 't-n8n-workflow', runBar: true, runLabel: 'Workflow testen', noSchedule: true, ndv: true,
    otherTitle: 'Szenario Studio', otherType: 'scenario', palette: [
      {kind: 'manualTrigger', label: 'Manual Trigger'}, {kind: 'set', label: 'Edit Fields (Set)'},
      {kind: 'if', label: 'IF'}, {kind: 'noOp', label: 'No Operation'}, {kind: 'stickyNote', label: 'Sticky Note'}]}));
})();
