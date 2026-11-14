"""Freigabe-Karte und Sitzungs-Erlaubnisse im Chat (04.11.2026): karte.js und erlaubnisse.js laufen mit node und einer Attrappe der Oberfläche.
Geprüft wird, was Rechte berührt: wann „Für diese Sitzung erlauben“ erscheint, was beim Klick an den Server geht, was bei einem Fehler passiert und dass „Zurücknehmen“ die richtige Karte trifft."""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1] / 'src' / 'sedra_runtime' / 'uix' / 'shells' / 'harness'

KOPF = """
function el(tag, klasse, text){
  const e = {tag, kinder: [], textContent: text || '', attrs: {}, dataset: {}, hidden: false, disabled: false, value: '', _k: new Set(klasse ? klasse.split(' ') : []),
    classList: {toggle: (k, an)=>{ (an === undefined ? !e._k.has(k) : an) ? e._k.add(k) : e._k.delete(k); }, contains: k=>e._k.has(k), add: k=>e._k.add(k), remove: k=>e._k.delete(k)},
    setAttribute(k, v){ e.attrs[k] = v; }, append(...c){ e.kinder.push(...c); }, replaceChildren(...c){ e.kinder = c; },
    querySelectorAll(sel){ const aus = []; const geh = n=>{ (n.kinder || []).forEach(k=>{ if(k.tag === sel) aus.push(k); geh(k); }); }; geh(e); return aus; }};
  return e;
}
const alle = n=>[n].concat(...(n.kinder || []).map(alle));
const text = n=>alle(n).map(x=>x.textContent).join(' ');
const knoepfe = n=>alle(n).filter(x=>x.tag === 'button');
const tick = ()=>new Promise(r=>setImmediate(r));
globalThis.setTimeout = ()=>0;
globalThis.sedraDom = {el};
globalThis.sedraHarness = {reiter: {oeffnen(S, id){ S.geoeffnet = id; }}};
require(%s);
require(%s);
const K = globalThis.sedraHarness.karte, E = globalThis.sedraHarness.erlaubnisse;
function stand(antworten){
  const S = {aufrufe: [], hinweise: [], async api(pfad, opt){ S.aufrufe.push({pfad, methode: (opt && opt.method) || 'GET', body: opt && opt.body});
              const a = antworten[(opt && opt.method || 'GET') + ' ' + pfad]; if(a instanceof Error) throw a; return typeof a === 'function' ? a(opt) : (a || {}); },
            hinweis(t, ton){ S.hinweise.push([t, ton]); }};
  return S;
}
const karte = (o)=>Object.assign({karte_id: 'K-1', werkzeug: 'datei_schreiben', ziel: 'docs/neu.md', stufe: 'captain', regel: null, vorschau: '+neu'}, o || {});
"""


@unittest.skipUnless(shutil.which('node'), 'node fehlt')
class KarteUndErlaubnisse(unittest.TestCase):
    def node(self, code):
        kopf = KOPF % (json.dumps(str(HARNESS / 'karte.js')), json.dumps(str(HARNESS / 'erlaubnisse.js')))
        r = subprocess.run(['node', '-e', kopf + '(async()=>{' + code + '})().catch(e=>{ console.error(e); process.exit(1); });'], capture_output=True, text=True, timeout=60, encoding='utf-8')
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    # ---- Karte

    def test_wann_fuer_diese_sitzung_erlauben_moeglich_ist(self):
        out = self.node("""
const m = K.sitzungMoeglich;
console.log(JSON.stringify({normal: m(karte()), vorbehalt: m(karte({vorbehalt: true})), warnung: m(karte({warnung: {text: 'x'}})), verboten: m(karte({stufe: 'verboten'})),
  laden: m(karte({werkzeug: 'modell_laden'})), entladen: m(karte({werkzeug: 'modell_entladen'})), aufgabe: m(karte({art: 'aufgabe'})), leer: m(null), ohne: m({karte_id: 'K'})}));
""")
        self.assertTrue(out['normal'])
        for schluessel in ('vorbehalt', 'warnung', 'verboten', 'laden', 'entladen', 'aufgabe', 'leer', 'ohne'):
            self.assertFalse(out[schluessel], schluessel)

    def test_mustervorschau_zeigt_ordner_befehlsanfang_oder_ziel(self):
        out = self.node("""
const v = K.mustervorschau;
console.log(JSON.stringify([v(karte()), v(karte({ziel: 'runtime\\\\src\\\\a.py'})), v(karte({ziel: 'a.md'})), v(karte({werkzeug: 'befehl', ziel: 'python -m py_compile x.py'})),
  v(karte({werkzeug: 'befehl', ziel: 'git push origin main'})), v(karte({werkzeug: 'lauf_starten', ziel: 'run_tests'}))]));
""")
        self.assertEqual(out, ['docs/**', 'runtime/src/**', 'a.md', 'python -m py_compile …', 'git push …', 'run_tests'])

    def test_klartext_sagt_was_die_erlaubnis_oeffnet(self):                    # S4.4 FS-12
        out = self.node("""
const k = K.klartext;
console.log(JSON.stringify([k(karte()), k(karte({ziel: 'a.md'})), k(karte({werkzeug: 'befehl', ziel: 'git push origin main'})), k(karte({werkzeug: 'lauf_starten', ziel: 'run_tests'}))]));
""")
        self.assertEqual(out, ['alle Dateien unter docs/ (datei_schreiben)', 'genau diese Datei: a.md (datei_schreiben)', 'Befehle, die so anfangen: git push …', 'genau dieses Ziel: run_tests'])

    def test_knoepfe_der_karte_je_nach_art(self):
        out = self.node("""
const S = stand({}), a = {};
const namen = k=>knoepfe(K.karteKarte(S, a, k)).map(b=>b.textContent);
const warn = K.karteKarte(S, a, karte({warnung: {text: 'Ersetzt die ganze Datei.'}}));
const fertig = K.karteKarte(S, a, karte(), {entscheidung: 'erlauben'});
console.log(JSON.stringify({normal: namen(karte()), vorbehalt: namen(karte({vorbehalt: true, regel: 'vorbehalt'})), warnung: knoepfe(warn).map(b=>b.textContent), alarm: text(warn),
  warnklasse: warn.classList.contains('warnung'), fertig: knoepfe(fertig).length, fertigText: text(fertig)}));
""")
        self.assertEqual(out['normal'], ['Erlauben', 'Für diese Sitzung erlauben', 'Befristet erlauben (2 Stunden, 50 Aufrufe)', 'Immer erlauben (Antrag)', 'Diff zeigen', 'Ablehnen'])      # S4.4 FS-20
        self.assertEqual(out['vorbehalt'], ['Erlauben', 'Diff zeigen', 'Ablehnen'])
        self.assertEqual(out['warnung'], ['Erlauben (ersetzt die Datei)', 'Diff zeigen', 'Ablehnen'])
        self.assertIn('Ersetzt die ganze Datei.', out['alarm'])
        self.assertTrue(out['warnklasse'])
        self.assertEqual(out['fertig'], 0)
        self.assertIn('Erlaubt', out['fertigText'])

    def test_klick_schickt_den_weg_an_die_richtige_karte_und_zeigt_die_entscheidung(self):
        out = self.node("""
const res = {};
for(const [name, weg] of [['Erlauben', 'erlauben'], ['Für diese Sitzung erlauben', 'sitzung'], ['Befristet erlauben (2 Stunden, 50 Aufrufe)', 'befristet'], ['Immer erlauben (Antrag)', 'immer'], ['Ablehnen', 'ablehnen']]){
  const S = stand({'POST /api/harness/karten/K-1': {erlaubnis: ['sitzung', 'befristet', 'immer'].includes(weg) ? {werkzeug: 'datei_schreiben', muster: 'docs/**', hinweis: weg === 'sitzung' ? undefined : 'Hinweis ' + weg} : undefined}});
  const box = K.karteKarte(S, {}, karte());
  const knopf = knoepfe(box).find(b=>b.textContent === name);
  knopf.onclick(); await tick();
  res[weg] = {post: S.aufrufe.filter(x=>x.methode === 'POST'), text: text(box), entschieden: box.classList.contains('entschieden')};
}
console.log(JSON.stringify(res));
""")
        for weg in ('erlauben', 'sitzung', 'befristet', 'immer', 'ablehnen'):
            self.assertEqual(out[weg]['post'], [{'pfad': '/api/harness/karten/K-1', 'methode': 'POST', 'body': {'weg': weg, 'notiz': None}}], weg)
            self.assertTrue(out[weg]['entschieden'], weg)
        self.assertIn('Erlaubt', out['erlauben']['text'])
        self.assertIn('Erlaubt – gilt für diese Sitzung', out['sitzung']['text'])
        self.assertIn('Erlaubt – befristet', out['befristet']['text'])
        self.assertIn('Hinweis befristet', out['befristet']['text'])
        self.assertIn('Antrag „Immer“ gestellt', out['immer']['text'])
        self.assertIn('Hinweis immer', out['immer']['text'])
        self.assertIn('datei_schreiben docs/**', out['sitzung']['text'])
        self.assertIn('Abgelehnt', out['ablehnen']['text'])

    def test_fehler_beim_senden_gibt_die_knoepfe_frei_und_sagt_es(self):
        out = self.node("""
const S = stand({'POST /api/harness/karten/K-1': new Error('karte_offen')});
const box = K.karteKarte(S, {}, karte());
knoepfe(box).find(b=>b.textContent === 'Erlauben').onclick(); await tick();
console.log(JSON.stringify({gesperrt: knoepfe(box).map(b=>b.disabled), hinweise: S.hinweise, entschieden: box.classList.contains('entschieden')}));
""")
        self.assertEqual(set(out['gesperrt']), {False})
        self.assertFalse(out['entschieden'])
        self.assertEqual(out['hinweise'], [['Freigabe nicht gesendet: karte_offen', 'bad']])

    def test_diff_wird_nach_vorzeichen_gefaerbt(self):
        out = self.node("""
const pre = K.diffZeilen('--- a\\n+++ b\\n@@ -1 +1 @@\\n-alt\\n+neu\\n kontext');
console.log(JSON.stringify(pre.kinder.map(z=>[z._k.has('hs-diff-neu') ? 'neu' : z._k.has('hs-diff-alt') ? 'alt' : z._k.has('hs-diff-ort') ? 'ort' : '-', z.textContent.trim()])));
""")
        self.assertEqual(out, [['-', '--- a'], ['-', '+++ b'], ['ort', '@@ -1 +1 @@'], ['alt', '-alt'], ['neu', '+neu'], ['-', 'kontext']])

    # ---- „Gilt gerade“ (S4.1 UI, FS-22 bis FS-24)

    ERL = """
const S = stand({
  'GET /api/harness/erlaubnisse?status=aktiv': {anzahl: 3, erlaubnisse: [
    {id: 'S-AAAAAAA1:K-7', art: 'sitzung', was: [{werkzeug: 'befehl', muster: 'git push*'}], wo: {projekt: 'p', sitzungen: ['S-AAAAAAA1']},
     dauer: {art: 'sitzung', bis: null, max_aufrufe: null}, warum: null, herkunft: {von: 'captain', karte_id: 'K-7', vorlage: null}, seit: '2026-11-14T10:00:00+01:00', status: 'aktiv'},
    {id: 'T-0000000A', art: 'aufgabe', was: [{werkzeug: 'datei_schreiben', muster: 'docs/**'}], wo: {projekt: 'p', sitzungen: ['S-AAAAAAA1']},
     dauer: {art: 'befristet', bis: '2026-11-14T12:00:00+01:00', max_aufrufe: 50}, aufrufe: 8, warum: 'Doku pflegen', herkunft: {von: 'captain', karte_id: null, vorlage: null}, status: 'aktiv'},
    {id: 'K:schreiben-docs', art: 'katalog', was: [{werkzeug: 'datei_schreiben', muster: 'docs/**'}], wo: {projekt: null, sitzungen: null},
     dauer: {art: 'immer'}, warum: 'Regel', herkunft: {von: 'captain'}, status: 'aktiv'}]},
  'PATCH /api/harness/sitzungen/S-AAAAAAA1': {}, 'POST /api/harness/aufgaben/T-0000000A/zuruecknehmen': {}});
const box = el('div');
const f = E.flaeche(S, box); await tick(); await tick();
const liste = alle(box).find(x=>x._k.has('hs-liste'));
const zeilen = ()=>alle(liste).filter(x=>x._k.has('hs-erlaubnis'));
"""

    def test_eine_liste_fuer_alle_laengen_ohne_katalogregeln(self):                    # FS-22
        out = self.node(self.ERL + """
console.log(JSON.stringify({ids: zeilen().map(x=>x.dataset.id), text: text(liste), titel: text(alle(box).find(x=>x._k.has('hs-ueber')))}));
""")
        self.assertEqual(out['ids'], ['S-AAAAAAA1:K-7', 'T-0000000A'])          # die Katalogregel steht im Katalog-Editor, nicht doppelt
        self.assertEqual(out['titel'], 'Gilt gerade')
        for stueck in ('befehl git push*', 'Sitzung S-AAAAAAA1', 'diese Sitzung (höchstens 24 Stunden)', 'Captain · Karte K-7',
                       'datei_schreiben docs/**', 'befristet · bis 2026-11-14 12:00 · noch 42 von 50 Aufrufen', 'Doku pflegen'):
            self.assertIn(stueck, out['text'])

    def test_zuruecknehmen_geht_je_art_ueber_den_bestehenden_weg_und_laedt_neu(self):                    # FS-15, FS-22
        out = self.node(self.ERL + """
knoepfe(zeilen()[0])[0].onclick(); await tick(); await tick();
knoepfe(zeilen()[1])[0].onclick(); await tick(); await tick();
console.log(JSON.stringify({aenderungen: S.aufrufe.filter(x=>x.methode !== 'GET'), geladen: S.aufrufe.filter(x=>x.methode === 'GET').length}));
""")
        self.assertEqual(out['aenderungen'], [
            {'pfad': '/api/harness/sitzungen/S-AAAAAAA1', 'methode': 'PATCH', 'body': {'erlaubnis_zuruecknehmen': 'K-7'}},
            {'pfad': '/api/harness/aufgaben/T-0000000A/zuruecknehmen', 'methode': 'POST', 'body': {'grund': 'zurückgenommen unter „Gilt gerade“'}}])
        self.assertEqual(out['geladen'], 3)

    def test_fehler_beim_zuruecknehmen_bleibt_sichtbar_und_der_knopf_frei(self):
        out = self.node(self.ERL.replace("'PATCH /api/harness/sitzungen/S-AAAAAAA1': {}", "'PATCH /api/harness/sitzungen/S-AAAAAAA1': new Error('weg')") + """
const knopf = knoepfe(zeilen()[0])[0]; knopf.onclick(); await tick(); await tick();
console.log(JSON.stringify({gesperrt: knopf.disabled, hinweise: S.hinweise, noch: zeilen().length}));
""")
        self.assertFalse(out['gesperrt'])
        self.assertEqual(out['hinweise'], [['Nicht zurückgenommen: weg', 'bad']])
        self.assertEqual(out['noch'], 2)

    def test_ohne_erlaubnisse_steht_ein_satz_und_nach_abbauen_wird_nichts_mehr_gezeichnet(self):
        out = self.node("""
const S = stand({'GET /api/harness/erlaubnisse?status=aktiv': {anzahl: 0, erlaubnisse: []}});
const box = el('div');
const f = E.flaeche(S, box); await tick(); await tick();
const liste = alle(box).find(x=>x._k.has('hs-liste'));
const leer = text(liste);
f.abbauen(); liste.replaceChildren(el('div', null, 'alt')); await f.laden();
console.log(JSON.stringify({leer, nachAbbau: text(liste)}));
""")
        self.assertIn('Keine Erlaubnis offen.', out['leer'])
        self.assertEqual(out['nachAbbau'].strip(), 'alt')

    def test_gegenprobe_lesefehler_zeigt_einen_satz_statt_leer(self):
        out = self.node("""
const S = stand({'GET /api/harness/erlaubnisse?status=aktiv': new Error('kaputt')});
const box = el('div');
E.flaeche(S, box); await tick(); await tick();
console.log(JSON.stringify(text(alle(box).find(x=>x._k.has('hs-liste')))));
""")
        self.assertIn('Erlaubnisse nicht lesbar: kaputt', out)

    def test_wortschatz_ohne_das_wort_aufgabe_in_der_liste(self):                    # FS-24
        js = (HARNESS / 'erlaubnisse.js').read_text(encoding='utf-8')
        sichtbar = re.findall(r"'([^']*[A-Za-zÄÖÜäöü][^']*)'", js)
        for satz in sichtbar:
            if ' ' in satz:
                self.assertNotIn('Aufgabe', satz, satz)


if __name__ == '__main__':
    unittest.main()
