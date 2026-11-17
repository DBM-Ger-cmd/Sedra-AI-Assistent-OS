const test=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const base=path.resolve(__dirname,'../src/sedra_runtime/uix/shells/harness');
require(path.join(base,'app.js'));
require(path.join(base,'startliste.js'));
test('alte Workflow- und Szenario-Einstiege öffnen genau einen Studio-Reiter',()=>{
  const offen=[],ziele=[];
  globalThis.sedraHarness.reiter={liste:()=>offen,aktivieren(_s,id){if(!offen.includes(id))offen.push(id);},aktiv:()=>offen[0]};
  const S={_workflowStudioAnsicht:{oeffneObjekt(o){ziele.push(o);}},hinweis(){}};
  const A=globalThis.sedraHarness.app;
  const erster=A.oeffnen(S,{type:'workflow',id:'rechnung',title:'n8n Workflows'});
  const zweiter=A.oeffnen(S,{type:'scenario',id:'rechnung',title:'Szenario Studio'});
  const dritter=A.oeffnen(S,{type:'workflow-studio',id:'app',title:'SEDRA Workflow Studio'});
  assert.equal(erster,'app:workflow-studio:app');assert.equal(zweiter,erster);assert.equal(dritter,erster);
  assert.equal(S._apps.size,1);assert.equal(offen.length,1);
  assert.deepEqual(ziele.map(o=>o.type),['workflow','scenario']);
});
test('Menü und Zuletzt benutzt enthalten keine alten Einzel-Apps, auch ohne Ausblendekonfiguration',()=>{
  const orte=['workflow-studio','workflow','scenario'].map(type=>({id:type,label:type,object:{type,id:type==='workflow-studio'?'app':'alle'}}));
  const L=globalThis.sedraStartliste;
  const liste=L.bauen(orte,[],()=>[{id:'tool',kind:'object'}],{},['workflow','scenario','workflow-studio']);
  assert.equal(liste.apps.length,1);assert.equal(liste.apps[0].label,'SEDRA Workflow Studio');
  assert.equal(liste.zuletzt.length,1);assert.equal(liste.zuletzt[0].id,'workflow-studio');
});
