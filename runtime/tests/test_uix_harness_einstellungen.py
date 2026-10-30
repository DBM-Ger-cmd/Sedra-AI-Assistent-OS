"""Harness-Shell Stufe 5 (SPEC_HARNESS_SHELL_v1 G2/G3 Stufe 5): die reine Prüfung des Katalog-Entwurfs (N4, katalog_editor_pruefung.js)
mit node, ohne Browser; die Einstellungen-Seite selbst prüft benchmarks/uix_check.py --shell harness und harness_abnahme.py --stufe5."""
import unittest

import yaml

from test_uix_contract import NODE, UIX, run_js

from guppi_runtime.harness import katalog

HARNESS = UIX / 'shells' / 'harness'


class KatalogPruefung(unittest.TestCase):
    KOPF = """
      const P = box.sedraKatalogPruefung;
      const vorlage = [
        {id: 'lesen-alles', werkzeug: ['datei_lesen', 'dateien_auflisten', 'suchen'], muster: ['**'], stufe: 'frei', begruendung: 'Lesen ändert nichts.'},
        {id: 'lesen-geheim', werkzeug: '*', muster: ['.env', '**/*.key'], stufe: 'verboten', begruendung: 'Geheimnisse nie.'},
        {id: 'schreiben-docs', werkzeug: ['datei_schreiben', 'datei_aendern'], muster: ['docs/**'], stufe: 'vorarbeiter', begruendung: 'Doku.'},
        {id: 'befehl-tests', werkzeug: 'befehl', muster: ['python -m pytest*'], stufe: 'captain', begruendung: 'Tests laufen lange.'},
      ];
      const kopie = ()=>JSON.parse(JSON.stringify(vorlage));
    """

    def setUp(self):
        if not NODE:
            self.skipTest('node is not installed')

    def js(self, probe):
        return run_js([HARNESS / 'katalog_editor_pruefung.js'], self.KOPF + probe)

    def test_01_unveraendert_ist_kein_antrag(self):
        out = self.js("console.log(JSON.stringify(P.pruefen(vorlage, kopie(), vorlage)));")
        self.assertEqual((out['fehler'], out['befunde'], out['unveraendert'], out['antragMoeglich']), ([], [], True, False))

    def test_02_diff_neu_geaendert_entfernt(self):
        out = self.js("""
          const e = kopie(); e[2].stufe = 'frei'; e.splice(3, 1); e.push({id: 'neu-1', werkzeug: ['befehl'], muster: ['git status'], stufe: 'frei', begruendung: 'x'});
          console.log(JSON.stringify(P.diff(vorlage, e)));
        """)
        self.assertEqual(out, {'neu': ['neu-1'], 'entfernt': ['befehl-tests'], 'geaendert': ['schreiben-docs']})

    def test_03_lockerung_ist_rot(self):
        out = self.js("const e = kopie(); e[2].stufe = 'frei'; const p = P.pruefen(vorlage, e, vorlage); console.log(JSON.stringify([p.befunde.map(b=>b.art), p.rot, p.antragMoeglich]));")
        self.assertEqual(out, [['lockerung'], 1, True], 'eine Lockerung ist ein roter Befund, aber kein Fehler – der Antrag geht mit Risiko ans Gate')

    def test_04_verschaerfung_ist_kein_befund(self):
        out = self.js("const e = kopie(); e[2].stufe = 'captain'; console.log(JSON.stringify(P.befunde(e, vorlage)));")
        self.assertEqual(out, [])

    def test_05_verbotene_vorlage_regel_ist_gesperrt(self):
        out = self.js("""
          const a = kopie(); a[1].stufe = 'captain';
          const b = kopie(); b.splice(1, 1);
          console.log(JSON.stringify([P.pruefen(vorlage, a, vorlage).antragMoeglich, P.befunde(a, vorlage).map(x=>x.art), P.befunde(b, vorlage).map(x=>x.art)]));
        """)
        self.assertEqual(out, [False, ['gesperrt'], ['gesperrt']], 'D-U3: Vorlage-verboten lässt sich weder lockern noch entfernen')

    def test_06_weites_muster_und_fehler(self):
        out = self.js("""
          const e = kopie(); e.push({id: 'alles', werkzeug: ['datei_schreiben'], muster: ['*'], stufe: 'frei', begruendung: 'x'});
          e.push({id: 'Kaputt', werkzeug: ['zaubern'], muster: [], stufe: 'egal', begruendung: ''});
          e.push({id: 'raus', werkzeug: ['datei_lesen'], muster: ['../geheim'], stufe: 'frei', begruendung: 'x'});
          e.push({id: 'lesen-alles', werkzeug: ['datei_lesen'], muster: ['a'], stufe: 'frei', begruendung: 'x'});
          const p = P.pruefen(vorlage, e, vorlage);
          console.log(JSON.stringify({weit: p.befunde.filter(b=>b.art === 'weit').map(b=>b.id), fehler: p.fehler.map(f=>f.satz.split(':')[0] + ':' + f.satz.split('–')[0].split(':')[1].trim()), moeglich: p.antragMoeglich}));
        """)
        self.assertEqual(out['weit'], ['alles'])
        self.assertFalse(out['moeglich'])
        self.assertEqual(out['fehler'], ['Kaputt:ID ungültig', 'Kaputt:Werkzeug unbekannt', 'Kaputt:Muster fehlt', 'Kaputt:Stufe unbekannt', 'Kaputt:Begründung fehlt',
                                         'raus:Dateimuster relativ zur Projektwurzel, ohne „..“', 'lesen-alles:ID doppelt'])

    def test_07_befehl_muster_duerfen_absolut_sein(self):
        out = self.js("console.log(JSON.stringify(P.fehler([{id: 'git', werkzeug: 'befehl', muster: ['/usr/bin/git *'], stufe: 'frei', begruendung: 'x'}])));")
        self.assertEqual(out, [])

    def test_08_yaml_vorschau_liest_der_server(self):
        out = self.js("const e = kopie(); e.push({id: 'neu-1', werkzeug: ['befehl'], muster: [\"echo 'hi' *\"], stufe: 'frei', begruendung: 'Sagt: hallo.'}); console.log(JSON.stringify(P.alsYamlVorschau(e)));")
        regeln = katalog.pruefen(yaml.safe_load(out))
        self.assertEqual([r['id'] for r in regeln], ['lesen-alles', 'lesen-geheim', 'schreiben-docs', 'befehl-tests', 'neu-1'])
        self.assertEqual(regeln[4]['muster'], ["echo 'hi' *"])
        self.assertEqual(regeln[1]['werkzeug'], ['*'])


if __name__ == '__main__':
    unittest.main()
