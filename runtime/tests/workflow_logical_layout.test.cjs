const test=require('node:test'),assert=require('node:assert/strict');
const L=require('../src/sedra_runtime/uix/ui/workflow-layout.js');
test('logical view keeps execution and revision unchanged and separates AI supply',()=>{
 const node=(name,type='noOp')=>({name,type:'n8n-nodes-base.'+type,position:[999,999]});
 const doc={nodes:[node('PDF','formTrigger'),node('Extract'),node('Compare'),node('Check','if'),node('OK'),node('Review'),node('HTML'),node('Model','lmChatOpenAi')],connections:{}};
 const edge=(a,b,index=0,kind='main')=>{doc.connections[a]??={};doc.connections[a][kind]??=[];doc.connections[a][kind][index]=[{node:b}];};
 edge('PDF','Extract');edge('Extract','Compare');edge('Compare','Check');edge('Check','OK');edge('Check','Review',1);edge('OK','HTML');edge('Review','HTML');edge('Model','Extract',0,'ai_languageModel');
 const before=JSON.stringify(doc),out=L.logisch(doc),pos=Object.fromEntries(out.nodes.map(n=>[n.name,n.position]));
 assert.equal(JSON.stringify(doc),before);assert.deepEqual(out.connections,doc.connections);
 for(const e of L.kanten(out).filter(e=>e.art==='main'))assert.ok(pos[e.nach][0]>pos[e.von][0]);
 assert.equal(pos.Model[0],pos.Extract[0]);assert.ok(pos.Model[1]>pos.Extract[1]);
 assert.equal(pos.OK[0],pos.Review[0]);assert.ok(pos.Review[1]>pos.OK[1]);
});
