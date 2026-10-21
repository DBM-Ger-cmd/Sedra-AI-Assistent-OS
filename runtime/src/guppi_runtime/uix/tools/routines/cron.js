// Werkzeug „Routinen“ – die reine Logik (Spec 4, D4.2.3): ein Cron-Ausdruck als deutscher Satz.
// Fünf Felder (Minute, Stunde, Tag, Monat, Wochentag) mit `*`, Zahl, Liste, Bereich, Schritt und Wochentag- oder Monatsnamen.
// Nur Anzeige: Termine berechnet der Server (`next_run`), und maßgeblich ist sein Urteil (`cron_invalid`). Was dieser Text nicht
// sicher sagen kann, gibt `null` – das Werkzeug zeigt dann den Ausdruck unverändert. Node prüft es ohne Browser (cron.test.js).

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const TAGE = ['sonntags', 'montags', 'dienstags', 'mittwochs', 'donnerstags', 'freitags', 'samstags'];
  const MONATE = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'];
  const TAG_NAMEN = {sun: 0, mon: 1, tue: 2, wed: 3, thu: 4, fri: 5, sat: 6, so: 0, mo: 1, di: 2, mi: 3, do: 4, fr: 5, sa: 6};
  const MONAT_NAMEN = {jan: 1, feb: 2, mar: 3, 'mär': 3, apr: 4, may: 5, mai: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, okt: 10, nov: 11, dec: 12, dez: 12};
  const FELDER = [{min: 0, max: 59}, {min: 0, max: 23}, {min: 1, max: 31}, {min: 1, max: 12, namen: MONAT_NAMEN}, {min: 0, max: 7, namen: TAG_NAMEN}];

  const zwei = n=>String(n).padStart(2, '0');
  function aufzaehlen(teile){ return teile.length < 2 ? teile.join('') : teile.slice(0, -1).join(', ') + ' und ' + teile[teile.length - 1]; }

  // Ein Feld in eine Form (rein): {art:'alle'} | {art:'werte', werte} | {art:'bereich', von, bis} | {art:'schritt', schritt, von}
  // Mehrere Einträge mit Komma werden zu Werten ausgerollt. Ungültig → null.
  function feld(text, f){
    const zahl = t=>{
      const k = String(t).toLowerCase();
      if(f.namen && Object.prototype.hasOwnProperty.call(f.namen, k)) return f.namen[k];
      if(!/^\d+$/.test(k)) return NaN;
      return Number(k);
    };
    const gut = n=>Number.isInteger(n) && n >= f.min && n <= f.max;
    function eins(t){
      let m;
      if(t === '*') return {art: 'alle'};
      if((m = /^(\*|[^-/]+)(?:-([^/]+))?\/(\d+)$/.exec(t))){
        const s = Number(m[3]), von = m[1] === '*' ? f.min : zahl(m[1]), bis = m[2] === undefined ? f.max : zahl(m[2]);
        return s > 0 && gut(von) && gut(bis) && von <= bis ? {art: 'schritt', schritt: s, von, bis, frei: m[1] === '*'} : null;
      }
      if((m = /^([^-]+)-([^-]+)$/.exec(t))){
        const von = zahl(m[1]), bis = zahl(m[2]);
        return gut(von) && gut(bis) && von <= bis ? {art: 'bereich', von, bis} : null;
      }
      const n = zahl(t);
      return gut(n) ? {art: 'werte', werte: [n]} : null;
    }
    const teile = String(text).split(',');
    const formen = teile.map(eins);
    if(formen.some(x=>!x)) return null;
    if(formen.length === 1) return formen[0];
    if(formen.some(x=>x.art === 'alle')) return null;
    const werte = new Set();
    formen.forEach(x=>{
      if(x.art === 'werte') x.werte.forEach(v=>werte.add(v));
      else for(let v = x.von; v <= x.bis; v += x.art === 'schritt' ? x.schritt : 1) werte.add(v);
    });
    return {art: 'werte', werte: Array.from(werte).sort((a, b)=>a - b)};
  }

  function zeit(m, h){
    const minuten = m.art === 'werte' ? m.werte : null;
    const wort = (minuten && minuten.length === 1 && minuten[0] === 0) ? ' zur vollen Stunde'
      : minuten ? (minuten.length === 1 ? ' zur Minute ' + zwei(minuten[0]) : ' zu den Minuten ' + aufzaehlen(minuten.map(zwei))) : '';
    const spanne = (von, bis)=>'von ' + zwei(von) + ':00 bis ' + zwei(bis) + ':59 Uhr';
    if(minuten && h.art === 'werte'){
      const z = [];
      h.werte.forEach(st=>minuten.forEach(mi=>z.push(zwei(st) + ':' + zwei(mi))));
      return z.length <= 8 ? {text: 'um ' + aufzaehlen(z) + ' Uhr', takt: false} : null;
    }
    if(minuten && h.art === 'alle') return {text: 'stündlich' + wort, takt: true};
    if(minuten && h.art === 'schritt') return {text: 'alle ' + h.schritt + ' Stunden' + (h.frei ? '' : ' ab ' + zwei(h.von) + ' Uhr') + wort, takt: true};
    if(minuten && h.art === 'bereich') return {text: 'stündlich von ' + zwei(h.von) + ' bis ' + zwei(h.bis) + ' Uhr' + wort, takt: true};
    const fenster = h.art === 'alle' ? '' : h.art === 'bereich' ? ' ' + spanne(h.von, h.bis)
      : h.art === 'werte' && h.werte.length === 1 ? ' ' + spanne(h.werte[0], h.werte[0]) : null;
    if(fenster === null) return null;
    if(m.art === 'alle') return {text: 'jede Minute' + fenster, takt: true};
    if(m.art === 'schritt' && m.frei) return {text: 'alle ' + m.schritt + ' Minuten' + fenster, takt: true};
    return null;
  }

  function wochentage(w){
    const name = n=>TAGE[n % 7];
    if(w.art === 'bereich') return name(w.von) + ' bis ' + name(w.bis);
    if(w.art === 'werte'){
      const tage = Array.from(new Set(w.werte.map(n=>n % 7))).sort((a, b)=>((a + 6) % 7) - ((b + 6) % 7));
      return aufzaehlen(tage.map(name));
    }
    return null;
  }

  function monatstage(t){
    if(t.art === 'werte') return 'am ' + aufzaehlen(t.werte.map(n=>n + '.')) + ' des Monats';
    if(t.art === 'bereich') return 'vom ' + t.von + '. bis ' + t.bis + '. des Monats';
    return null;
  }

  function monate(mo){
    if(mo.art === 'alle') return '';
    if(mo.art === 'werte') return 'im ' + aufzaehlen(mo.werte.map(n=>MONATE[n - 1]));
    if(mo.art === 'bereich') return 'von ' + MONATE[mo.von - 1] + ' bis ' + MONATE[mo.bis - 1];
    return null;
  }

  // Der Satz (rein): „jeden Tag um 06:30 Uhr“, „montags bis freitags um 09:00 Uhr“, „alle 15 Minuten“ – oder null
  function cronText(ausdruck, zeitzone){
    const teile = String(ausdruck || '').trim().split(/\s+/);
    if(teile.length !== 5 || !teile[0]) return null;
    const [m, h, tag, monat, woche] = teile.map((t, i)=>feld(t, FELDER[i]));
    if(!m || !h || !tag || !monat || !woche) return null;
    const z = zeit(m, h);
    if(!z) return null;
    let tage;
    if(tag.art === 'alle' && woche.art === 'alle') tage = 'jeden Tag';
    else{
      const a = tag.art === 'alle' ? '' : monatstage(tag), b = woche.art === 'alle' ? '' : wochentage(woche);
      if(a === null || b === null) return null;
      tage = [a, b].filter(Boolean).join(' oder ');      // Cron: Tag des Monats ODER Wochentag
    }
    const mon = monate(monat);
    if(mon === null) return null;
    const vorne = tage === 'jeden Tag' && z.takt && !mon ? '' : tage + (mon ? ' ' + mon : '') + ' ';
    return vorne + z.text + (zeitzone ? ' (' + zeitzone + ')' : '');
  }

  const pure = {cronText, feld};
  root.sedraRoutinesCron = pure;
  if(typeof module !== 'undefined' && module.exports) module.exports = pure;
})();
