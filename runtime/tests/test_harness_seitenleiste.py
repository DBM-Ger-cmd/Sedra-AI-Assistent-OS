"""Seitenleiste (03.11.2026): viele Sitzungen auf einmal aufräumen (POST aufraeumen) und die reine Logik von Suche, Sortierung und Schnellauswahl (seitenleiste.js, mit node)."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.harness.api import HarnessApi, NichtGefunden
from guppi_runtime.harness.sitzung import Sitzungen
from guppi_runtime.harness.strom import Stroeme

JS = Path(__file__).resolve().parents[1] / 'src' / 'guppi_runtime' / 'uix' / 'shells' / 'harness' / 'seitenleiste.js'


class AufraeumenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sitzungen = Sitzungen(Path(self.tmp.name))
        self.stroeme = Stroeme()
        self.api = HarnessApi.__new__(HarnessApi)
        self.api.sitzungen, self.api.stroeme = self.sitzungen, self.stroeme
        self.gesehen = []
        self.api._audit = lambda event, payload: self.gesehen.append((event, payload))
        self.api._melden = lambda *a, **k: None
        self.api._mission_stand = lambda *a, **k: None
        self.ids = [self.sitzungen.anlegen('p', titel=f'Antworte in einem Satz {i}')['id'] for i in range(4)]

    def test_mehrere_sitzungen_werden_verschoben_nichts_wird_geloescht(self):
        out = self.api.aufraeumen({'ids': self.ids[:3]})
        self.assertEqual(out['verschoben'], self.ids[:3])
        self.assertEqual(out['uebersprungen'], [])
        verbleibend = [s['id'] for s in self.sitzungen.liste()]
        self.assertEqual(verbleibend, [self.ids[3]])
        self.assertEqual(len(list((Path(self.tmp.name) / 'geloescht').glob('S-*.jsonl'))), 3)             # nur verschoben
        self.assertEqual(self.gesehen[-1], ('HARNESS_SITZUNGEN_AUFGERAEUMT', {'verschoben': 3, 'uebersprungen': 0}))

    def test_eine_laufende_antwort_und_unbekannte_ids_werden_uebersprungen_mit_grund(self):
        self.stroeme.anlegen(self.ids[0])                                                                 # läuft
        out = self.api.aufraeumen({'ids': [self.ids[0], self.ids[1], 'S-00000000', self.ids[1]]})
        self.assertEqual(out['verschoben'], [self.ids[1]])                                                # doppelt genannt: einmal
        gruende = {u['id']: u['grund'] for u in out['uebersprungen']}
        self.assertIn('antwort_laeuft', gruende[self.ids[0]])
        self.assertIn('sitzung_unbekannt', gruende['S-00000000'])

    def test_ungueltige_listen_werden_abgelehnt(self):
        for bad in (None, [], 'S-00000001', ['../x'], ['S-ZZZZZZZZ'], [self.ids[0]] * 0, ['S-%08X' % i for i in range(201)], [1]):
            with self.assertRaises(ValueError):
                self.api.aufraeumen({'ids': bad})


@unittest.skipUnless(shutil.which('node'), 'node fehlt')
class SichtbarkeitTests(unittest.TestCase):
    def test_die_knoepfe_der_werkzeugzeile_sind_immer_sichtbar(self):
        """Captain 03.11.2026: „die Kästchen zum Anhaken sehe ich nicht“ – .hs-sz-knopf ist sonst nur beim Überfahren einer Zeile sichtbar, der ☑-Knopf stand aber in der Werkzeugzeile."""
        css = (JS.parent / 'shell.css').read_text(encoding='utf-8')
        self.assertIn('.hs-sl-zeile .hs-sz-knopf{visibility:visible', css)
        self.assertIn('.hs-sz-knopf{', css)


class LogikTests(unittest.TestCase):
    def node(self, code):
        skript = ("globalThis.localStorage = {_d: {}, getItem(k){ return this._d[k] ?? null; }, setItem(k, v){ this._d[k] = v; }};\n"
                  f"require({json.dumps(str(JS))});\nconst sl = globalThis.sedraHarness.seitenleiste;\n"
                  "const tage = n=>new Date(Date.now() - n * 86400000).toISOString();\n" + code)
        r = subprocess.run(['node', '-e', skript], capture_output=True, text=True, timeout=60, encoding='utf-8')
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_suche_und_sortierung(self):
        out = self.node("""
const S = {sitzungen: [{id:'S-1', titel:'Rekorder testen', zuletzt: tage(1)}, {id:'S-2', titel:'Antworte in einem Satz', zuletzt: tage(2)}, {id:'S-3', titel:'Baut Ordner', zuletzt: tage(3)}], _filter: ''};
const r = {};
r.alle = sl.ordnen(S, S.sitzungen).map(s=>s.id);
S._filter = ' REKORDER '; r.filter = sl.ordnen(S, S.sitzungen).map(s=>s.id); S._filter = '';
localStorage.setItem('sedra.harness.seitenleiste', JSON.stringify({sort: 'alt', alt: 7})); r.alt = sl.ordnen(S, S.sitzungen).map(s=>s.id);
localStorage.setItem('sedra.harness.seitenleiste', JSON.stringify({sort: 'titel', alt: 7})); r.titel = sl.ordnen(S, S.sitzungen).map(s=>s.id);
console.log(JSON.stringify(r));""")
        self.assertEqual(out['alle'], ['S-1', 'S-2', 'S-3'])
        self.assertEqual(out['filter'], ['S-1'])
        self.assertEqual(out['alt'], ['S-3', 'S-2', 'S-1'])
        self.assertEqual(out['titel'], ['S-2', 'S-3', 'S-1'])

    def test_schnellauswahl_dubletten_alt_leer_und_nie_laufende_aktive_oder_vorarbeiter(self):
        out = self.node("""
const mk = (id, titel, zuletzt, extra)=>Object.assign({id, titel, projekt: 'p', zuletzt, nachrichten: 6}, extra || {});
const S = {sitzungen: [
  mk('S-1', 'Antworte in einem Satz', tage(1)), mk('S-2', 'Antworte in einem Satz', tage(2)), mk('S-3', ' antworte  in einem satz ', tage(3)),
  mk('S-4', 'Antworte in einem Satz', tage(4), {laeuft: true}), mk('S-5', 'Anderes', tage(20), {nachrichten: 1}), mk('S-6', 'Chef', tage(30), {vorlage: 'vorarbeiter'}),
  mk('S-7', 'Aktiv', tage(40))],
  vorarbeiter: {p: {sitzung_id: 'S-6'}}, aktive: ()=>({id: 'S-7'}), _filter: ''};
const r = {};
r.dubletten = sl.kandidaten(S, 'dubletten'); r.alt = sl.kandidaten(S, 'alt'); r.leer = sl.kandidaten(S, 'leer'); r.alle = sl.kandidaten(S, 'alle');
localStorage.setItem('sedra.harness.seitenleiste', JSON.stringify({sort: 'neu', alt: 0})); r.nieAlt = sl.kandidaten(S, 'alt');
console.log(JSON.stringify(r));""")
        self.assertEqual(sorted(out['dubletten']), ['S-2', 'S-3'])                     # S-1 ist die neueste, S-4 läuft und bleibt
        self.assertEqual(sorted(out['alt']), ['S-5'])                                  # nur über 7 Tage, ohne Vorarbeiter (S-6) und ohne die aktive (S-7)
        self.assertEqual(out['leer'], ['S-5'])
        self.assertNotIn('S-4', out['alle'])
        self.assertNotIn('S-6', out['alle'])
        self.assertNotIn('S-7', out['alle'])
        self.assertEqual(out['nieAlt'], [])                                            # „nie einklappen“ heißt: keine Alt-Auswahl


if __name__ == '__main__':
    unittest.main()
