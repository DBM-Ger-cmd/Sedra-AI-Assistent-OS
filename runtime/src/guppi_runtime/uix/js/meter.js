// Guppy meter window: how much code GUPPI and Claude have written (cards plus a weekly grid, like the example picture of the Captain of 2026-10-08).
// Classic script (shares the page's global scope). Read-only: it only reads /api/meter.

const METER_RANGES = [['today','Heute'],['7','7d'],['30','30T'],['all','Alle']];
const METER_DAYS = ['Mo','','Mi','','Fr','','So'];

let meterRange = 'today', meterView = null, meterSeenAt = null, meterError = null, meterTimer = null;
let meterDay = null;
let coinCanvas = null, coinHole = null, coinFrame = null, coinLast = 0;

function meterNumber(n){ return Number(n||0).toLocaleString('de-DE'); }

function meterCard(label, value){
  const c = el('div','meter-card'); c.append(el('span','meter-label',label), el('b','meter-value',value)); return c;
}

function meterGrid(grid){
  const box = el('div','meter-grid');
  box.setAttribute('role','img'); box.setAttribute('aria-label','Zeilen pro Tag der letzten Wochen');
  grid.forEach((row, r)=>{
    const line = el('div','meter-row'); line.append(el('span','meter-day',METER_DAYS[r]));
    row.forEach(cell=>{
      const c = el('span','meter-cell'+(cell ? ' l'+cell.level : ' none'));
      if(cell) c.title = cell.date+': '+meterNumber(cell.lines)+' Zeilen (GUPPI '+meterNumber(cell.guppi)+', Claude '+meterNumber(cell.claude)+')';
      line.append(c);
    });
    box.append(line);
  });
  return box;
}


// Coin hole (coin_hole.js, built by GUPPI): coins of the tokens used fall into a hole. The first reading drops the coins of the last run, later ones the new tokens.
function meterTokens(){ return meterView && meterView.tokens; }

function feedCoinHole(){
  const t = meterTokens();
  if(!t || !coinHole) return;
  const total = t.ranges.all.tokens;
  if(coinHole.stats().tokens === null && t.last) coinHole.update(Math.max(0, total - t.last.tokens));
  coinHole.update(total);
}

function coinLoop(now){
  const win = document.getElementById('meterWindow');
  if(!win || !win.classList.contains('active') || document.hidden || !coinHole){ coinFrame = null; return; }
  coinHole.tick(Math.min(0.05, (now - (coinLast || now)) / 1000)); coinLast = now;
  coinFrame = requestAnimationFrame(coinLoop);
}

function startCoinLoop(){ if(coinFrame === null){ coinLast = 0; coinFrame = requestAnimationFrame(coinLoop); } }

function tokenPanel(){
  const t = meterTokens();
  if(!t) return null;
  if(!coinCanvas){
    coinCanvas = el('canvas','coin-canvas'); coinCanvas.width = 360; coinCanvas.height = 140;
    coinCanvas.setAttribute('role','img'); coinCanvas.setAttribute('aria-label','Münzen fallen in ein Loch: je 100 Token eine Kupfermünze, 1.000 Silber, 10.000 Gold');
    coinHole = createCoinHole(coinCanvas);
  }
  feedCoinHole(); startCoinLoop();
  const c = t.ranges[meterRange] || t.ranges.all;
  if(meterRange !== 'today' || meterDay) coinHole.showPile(meterDay ? meterDay.tokens : c.tokens, meterDay ? meterDay.date : (meterRange === 'all' ? 'Gesamt' : meterRange+' Tage'), false);
  else coinHole.showPile(null);
  const panel = el('div','coin-panel'), side = el('div','coin-side');
  side.append(meterCard('Token '+(meterRange === 'today' ? 'heute' : meterRange === 'all' ? 'gesamt' : 'in '+meterRange+' Tagen'), meterNumber(c.tokens)+' ('+meterNumber(c.runs)+' Läufe)'),
              meterCard('Letzter Lauf', t.last ? meterNumber(t.last.tokens)+' · '+(t.last.spec||'?') : '–'));
  const max = Math.max(1, ...t.series.map(s=>s.tokens)), bars = el('div','coin-series');
  bars.setAttribute('role','img'); bars.setAttribute('aria-label','Token pro Tag, 14 Tage');
  t.series.forEach(s=>{ const b = el('span','coin-bar'); b.style.height = Math.max(2, Math.round(40*s.tokens/max))+'px'; b.title = s.date+': '+meterNumber(s.tokens)+' Token (Klick: Münzen im Loch)'; b.style.cursor = 'pointer'; b.onclick = ()=>{ meterDay = s; coinHole.showPile(s.tokens, s.date, true); }; bars.append(b); });
  side.append(bars);
  panel.append(coinCanvas, side);
  const legend = el('small','meter-foot','Kupfer 100 · Silber 1.000 · Gold 10.000 Token (Completion-Token der Bauläufe)');
  const wrap = el('div'); wrap.append(panel, legend);
  return wrap;
}

function renderMeter(){
  const box = document.getElementById('meterBody');
  if(!box) return;
  box.replaceChildren();
  const bar = el('div','meter-bar'), tabs = el('div','agent-tabs'), ranges = el('div','agent-tabs');
  const overview = el('button','tool on','Übersicht'); overview.setAttribute('aria-pressed','true'); tabs.append(overview);
  METER_RANGES.forEach(([id,label])=>{
    const b = el('button','tool'+(id===meterRange ? ' on' : ''),label); b.setAttribute('aria-pressed', id===meterRange ? 'true' : 'false');
    b.onclick = ()=>{ meterRange = id; meterDay = null; renderMeter(); };
    ranges.append(b);
  });
  bar.append(tabs, ranges); box.append(bar);
  const v = meterView;
  const stale = el('small','agent-stale', meterError ? 'Keine Verbindung zur Runtime – angezeigter Stand von '+(meterSeenAt||'unbekannt')+' ist veraltet ('+meterError+').' : (meterSeenAt ? 'Datenstand: '+meterSeenAt : ''));
  if(!v){ box.append(el('div','muted','Daten werden geladen ...'), stale); return; }
  const c = v.ranges[meterRange] || v.ranges.all;
  const cards = el('div','meter-cards');
  cards.append(meterCard('Zeilen gesamt', meterNumber(c.total_lines)), meterCard('Von GUPPI', meterNumber(c.guppi_lines)+' ('+c.guppi_share+' %)'), meterCard('Von Claude', meterNumber(c.claude_lines)),
               meterCard('Aktive Tage', meterNumber(c.active_days)), meterCard('Spitzentag', c.peak_date || '–'), meterCard('Letzte 30 Tage', meterNumber(c.last_30_lines)));
  const share = el('div','meter-share'); share.title = 'Anteil von GUPPI am geschriebenen Code (Ziel: mindestens 50 %)';
  const fill = el('div','meter-share-fill'); fill.style.width = Math.max(0, Math.min(100, c.guppi_share))+'%'; share.append(fill);
  box.append(cards, share, el('small','meter-foot','GUPPI-Anteil '+c.guppi_share+' % · Ziel mindestens 50 %'), meterGrid(v.grid));
  const legend = el('div','meter-legend'); legend.append(el('span',null,'weniger'));
  [0,1,2,3,4].forEach(l=>legend.append(el('span','meter-cell l'+l))); legend.append(el('span',null,'mehr'));
  const tokens = tokenPanel();
  if(tokens) box.append(tokens);
  box.append(legend, el('small','agent-stale',v.note), stale);
}

async function refreshMeter(){
  try{
    meterView = await api('/api/meter');
    meterSeenAt = new Date().toLocaleTimeString('de-DE');
    meterError = null;
  }catch(err){ meterError = err.message; }
  renderMeter();
}

async function openMeter(){
  showWindow('meterWindow');
  await refreshMeter();
  if(!meterTimer) meterTimer = setInterval(()=>{
    const w = document.getElementById('meterWindow');
    if(w.classList.contains('active') && w.classList.contains('focused') && !document.hidden) refreshMeter();
  }, 30000);
}
