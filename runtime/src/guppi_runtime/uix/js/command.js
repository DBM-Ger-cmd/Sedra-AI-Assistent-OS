// Kommando: one input for everything ("Was willst du tun?") – on the Deck and as a palette (Strg+K) from every window.
// A short navigation phrase opens the right place; everything else goes to GUPPI (the chat with its environment tools), and an order
// can be planned as a card from there. routeCommand() and matchCommands() are pure (text in, plain objects out) so node can judge them.
// Classic script: shares the page's global scope with the other files in uix/js; load order is set in retro_desktop.html.

const COMMANDS = [
  {id:'deck',       label:'Deck',                          hint:'Was wartet, was läuft, Besatzung',                words:['deck','start','übersicht','uebersicht','home']},
  {id:'chat',       label:'Mit GUPPI sprechen',            hint:'Frage oder Auftrag im Chat',                       words:['chat','guppi','sprechen','fragen']},
  {id:'plan',       label:'Als Karte planen',              hint:'Auftrag planen, Freigabe, Ausführung',             words:['karte planen','auftrag planen','mission planen','neue karte','neue mission']},
  {id:'model_add',  label:'Neues Modell hinzufügen',       hint:'GGUF wählen, Rezept prüfen, laden, testen',        words:['neues modell','modell hinzufügen','modell hinzufuegen','gguf','modell anlegen']},
  {id:'models',     label:'Werkstatt: Modelle',            hint:'Modell laden, wechseln, entladen',                 words:['modell','modelle','werkstatt','laden','entladen','wechseln']},
  {id:'test',       label:'Teststrecke',                   hint:'Kurztest und Standardtest des geladenen Modells',  words:['test','teststrecke','standardtest','kurztest','kontext testen']},
  {id:'project_new',label:'Neues Projekt anlegen',         hint:'Projektordner und Arbeitsbereich',                 words:['neues projekt','projekt anlegen','projekt erstellen']},
  {id:'projects',   label:'Projekte zeigen',               hint:'Projektordner auf dem Desktop',                    words:['projekt','projekte','ordner','workspace']},
  {id:'bridge',     label:'Karten (Brücke)',               hint:'Alle Karten, Freigaben zuerst',                    words:['brücke','bruecke','karten','freigabe','freigaben','missionen']},
  {id:'agents',     label:'Besatzung',                     hint:'Organigramm, Rollen, Agenten',                     words:['besatzung','agent','agenten','crew','organigramm','rollen']},
  {id:'meter',      label:'Guppy-Meter',                   hint:'Zeilen und Token: wer hat was geschrieben',        words:['meter','token','zeilen','budget','kosten','münzloch','muenzloch']},
  {id:'logbook',    label:'Logbuch',                       hint:'Missionen, Audit-Kette, Jobs',                     words:['logbuch','audit','verlauf','protokoll']},
  {id:'hardware',   label:'Hardware',                      hint:'GPU, Speicher, Profil',                            words:['hardware','gpu','grafikkarte','speicher','vram']},
  {id:'machine',    label:'Maschinenraum',                 hint:'Live-Status der Runtime',                          words:['maschinenraum','runtime','status','system']},
  {id:'dev',        label:'Entwicklungsumgebung',          hint:'Isolierte Ausführung, Blocker',                    words:['entwicklung','entwicklungsumgebung','sandbox','devvm','microvm']},
  {id:'switches',   label:'Schalter',                      hint:'Modell-Loader, llama-server, Richtlinien',          words:['schalter','loader']},
  {id:'settings',   label:'Einstellungen',                 hint:'API-Einstellungen für Cloud-Modelle und Schlüssel', words:['einstellung','einstellungen','api','api-einstellungen','schlüssel','schluessel','cloud']},
  {id:'library',    label:'Bibliothek',                    hint:'Skills ansehen, eigene schreiben',                 words:['bibliothek','skill','skills','skill-bibliothek','nachschlagen']},
  {id:'theme',      label:'Erscheinungsbild wechseln',     hint:'Retro, Klar oder Nacht – z. B. „thema nacht“',      words:['thema','theme','erscheinungsbild','aussehen','dunkel','hell','nachtmodus','desktop wechseln','desktop anpassen','skin']}
];

// orders start like this: the palette then offers "Als Karte planen" next to the chat
const ORDER_WORDS = ['erstelle','erstell','baue','bau','schreibe','schreib','implementiere','programmiere','entwickle','ändere','aendere','repariere','behebe','füge','fuege','lege','teste','prüfe','pruefe','refaktoriere','optimiere','erweitere','generiere','migriere','dokumentiere'];

// questions and explanations are for GUPPI, never a window: first word or a question mark decides
const QUESTION_WORDS = ['was','wie','warum','wieso','weshalb','welche','welcher','welches','wer','wann','wo','wozu','erkläre','erklär','erklaere','beschreibe','sag','sage','zeig','zeige','kannst','kann','ist','sind','hat','gibt','soll','hilf','hilfe'];

function normalizeCommand(text){
  return String(text||'').toLowerCase().replace(/[„“"'.,!?;:()]+/g,' ').replace(/\s+/g,' ').trim();
}

function wordMatch(hay, needle){
  const i = hay.indexOf(needle);
  if(i < 0) return false;
  const before = i === 0 || hay[i-1] === ' ', after = i + needle.length === hay.length || hay[i+needle.length] === ' ';
  return before && after;
}

// commands that fit the text, best first: an exact phrase beats a word, a longer phrase beats a shorter one
function matchCommands(text, commands){
  const q = normalizeCommand(text);
  if(!q) return [];
  const list = commands || COMMANDS, scored = [];
  list.forEach(c=>{
    let best = 0;
    c.words.forEach(w=>{
      if(q === w) best = Math.max(best, 100 + w.length);
      else if(wordMatch(q, w)) best = Math.max(best, 50 + w.length);
      else if(q.length >= 3 && w.startsWith(q)) best = Math.max(best, 20 + q.length);
    });
    if(normalizeCommand(c.label).startsWith(q)) best = Math.max(best, 30 + q.length);
    if(best) scored.push({id:c.id, label:c.label, hint:c.hint, score:best});
  });
  return scored.sort((a,b)=>b.score - a.score || a.label.localeCompare(b.label));
}

// {kind:'command', id} for a short navigation phrase; {kind:'chat', text, order} otherwise ('/…' always goes to the chat: /status, /plan …)
function routeCommand(text, commands){
  const raw = String(text||'').trim();
  if(!raw) return null;
  if(raw.startsWith('/')) return {kind:'chat', text:raw, order:false};
  const q = normalizeCommand(raw), words = q.split(' ');
  const first = words[0];
  const order = ORDER_WORDS.includes(first) || /^(bitte|guppi) /.test(q) && ORDER_WORDS.includes(words[1]);
  const question = QUESTION_WORDS.includes(first) || raw.endsWith('?');
  if(words.length <= 4 && !order && !question){
    const hits = matchCommands(raw, commands);
    if(hits.length && hits[0].score >= 50) return {kind:'command', id:hits[0].id, text:raw};
  }
  return {kind:'chat', text:raw, order};
}

// ---- the browser part: run a command, show the palette

function runCommandId(id, text){
  const go = {
    deck: ()=>openDeck(), chat: ()=>openGuppi(), plan: ()=>{ openGuppi(); if(text && routeCommand(text).kind === 'chat') planCard(text); },
    model_add: ()=>openModelAdd(), models: ()=>openModels(), test: ()=>openModelsAt('Teststrecke'), switches: ()=>openModelsAt('Schalter'),
    project_new: ()=>createProject(), projects: ()=>openProjectRegistry(), bridge: ()=>openBridge(), agents: ()=>openAgents(),
    meter: ()=>openMeter(), logbook: ()=>openLogbook(), hardware: ()=>openHardware(), machine: ()=>openMachineRoom(), dev: ()=>openDevEnv(),
    library: ()=>openLibrary(), settings: ()=>openSettings(),
    theme: ()=>{ const t = themeCommand(text||''); if(t) setTheme(t); else document.getElementById('startMenu').classList.add('active'); }
  }[id];
  if(!go) throw new Error('Unbekanntes Kommando: '+id);
  return go();
}

// the one entry point: Deck input, palette and the start menu's "Kommando" use it
function runCommand(text){
  const route = routeCommand(text);
  if(!route) return;
  closePalette();
  if(route.kind === 'command') return runCommandId(route.id, route.text);
  openGuppi();
  return sendText(route.text, true, []);
}

async function openModelsAt(section){
  await openModels();
  const h = [...document.querySelectorAll('#modelBody h3')].find(x=>x.textContent.startsWith(section));
  if(h) h.scrollIntoView({block:'start', behavior: REDUCED_MOTION ? 'auto' : 'smooth'});
}

let paletteIndex = 0;

function paletteRows(text){
  const route = routeCommand(text) || {kind:'chat', text:'', order:false};
  const rows = [], hits = matchCommands(text).slice(0, 6);
  const chat = {id:'__chat', label:'An GUPPI senden: '+text.trim().slice(0,60), hint: route.order ? 'Der Chat antwortet; von dort aus „Als Auftrag planen“' : 'Frage, Auftrag oder /status, /plan …'};
  if(route.kind === 'command') rows.push(...hits, chat);                    // a navigation phrase: the window first, the chat as the way out
  else { if(text.trim()) rows.push(chat); if(route.order) rows.push({id:'__plan', label:'Als Karte planen: '+text.trim().slice(0,60), hint:'Plan, Freigabe, Ausführung – ohne Umweg über den Chat'}); rows.push(...hits); }
  if(!text.trim()) COMMANDS.slice(0, 8).forEach(c=>rows.push(c));
  return rows;
}

function renderPalette(){
  const input = document.getElementById('paletteInput'), list = document.getElementById('paletteList');
  const rows = paletteRows(input.value);
  paletteIndex = Math.max(0, Math.min(paletteIndex, rows.length - 1));
  list.replaceChildren(...rows.map((r,i)=>{
    const d = el('div','palette-row'+(i === paletteIndex ? ' on' : ''));
    d.append(el('b',null,r.label), el('small',null,r.hint||''));
    d.onmousedown = e=>{ e.preventDefault(); paletteIndex = i; palettePick(); };
    d.onmousemove = ()=>{ if(paletteIndex !== i){ paletteIndex = i; renderPalette(); } };
    return d;
  }));
}

function palettePick(){
  const input = document.getElementById('paletteInput'), rows = paletteRows(input.value), r = rows[paletteIndex];
  if(!r) return;
  const text = input.value.trim();
  closePalette();
  if(r.id === '__chat'){ openGuppi(); return sendText(text, true, []); }
  if(r.id === '__plan'){ openGuppi(); return planCard(text); }
  return runCommandId(r.id, text);
}

function openPalette(){
  const p = document.getElementById('palette'), input = document.getElementById('paletteInput');
  p.classList.add('active'); input.value = ''; paletteIndex = 0; renderPalette(); input.focus();
}

function closePalette(){
  const p = document.getElementById('palette');
  if(p) p.classList.remove('active');
}

function togglePalette(){
  const p = document.getElementById('palette');
  if(p.classList.contains('active')) closePalette(); else openPalette();
}

// keys of the palette input: arrows move, Enter picks, Escape closes
function paletteKey(e){
  const rows = paletteRows(e.target.value);
  if(e.key === 'ArrowDown'){ e.preventDefault(); paletteIndex = Math.min(rows.length - 1, paletteIndex + 1); renderPalette(); }
  else if(e.key === 'ArrowUp'){ e.preventDefault(); paletteIndex = Math.max(0, paletteIndex - 1); renderPalette(); }
  else if(e.key === 'Enter'){ e.preventDefault(); palettePick(); }
  else if(e.key === 'Escape'){ closePalette(); }
}
