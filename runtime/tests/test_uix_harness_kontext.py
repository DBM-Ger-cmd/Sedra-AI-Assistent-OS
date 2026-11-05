"""Harness-Shell: Kontextmenü (Captain 05.11.2026, kontext.js und kontextmodule.js) – die Module melden sich an, ein Rechtsklick findet sie von innen nach außen, der Entwurf für den Chat
nennt Ort, Modul und Dateien. Reine Teile mit node, ohne Browser; die Dateien, die die Tabelle nennt, müssen es wirklich geben."""
import re
import unittest

from test_uix_contract import NODE, UIX, run_js

HARNESS = UIX / 'shells' / 'harness'
DATEIEN = [UIX / 'ui' / 'dom.js', HARNESS / 'kontext.js']

KNOTEN = """
  const knoten = (klassen, eltern)=>({nodeType: 1, parentElement: eltern || null, matches(sel){ return sel.split(',').some(s=>{ s = s.trim(); return s === 'body' ? klassen.includes('body') : klassen.includes(s.replace(/^\\./, '')); }); }});
  const body = knoten(['body']);
  const taskleiste = knoten(['hs-taskleiste'], body);
  const zelle = knoten(['hs-zelle'], taskleiste);
"""


class Kontextmenue(unittest.TestCase):
    def setUp(self):
        if not NODE:
            self.skipTest('node is not installed')

    def test_modul_anmelden_ersetzt_gleiche_id_und_prueft_die_felder(self):
        out = run_js(DATEIEN, """
          const K = box.sedraHarness.kontext;
          K.registrieren({id: 'a', titel: 'A', selektor: '.a', dateien: ['a.js']});
          K.registrieren({id: 'a', titel: 'A neu', selektor: '.a', dateien: ['b.js']});
          let fehler = [];
          for(const kaputt of [null, {id: 'x'}, {id: 'x', titel: 'X'}, {id: 1, titel: 'X', selektor: '.x'}]){ try{ K.registrieren(kaputt); fehler.push(false); }catch(e){ fehler.push(e.message); } }
          console.log(JSON.stringify({liste: K.liste().map(m=>[m.id, m.titel, m.dateien]), fehler}));
        """)
        self.assertEqual(out['liste'], [['a', 'A neu', ['b.js']]], 'dieselbe ID ersetzt, nichts doppelt')
        self.assertEqual(out['fehler'], ['kontext_modul_ungueltig'] * 4)

    def test_rechtsklick_findet_die_module_von_innen_nach_aussen(self):
        out = run_js(DATEIEN, KNOTEN + """
          const K = box.sedraHarness.kontext;
          K.registrieren({id: 'harness', titel: 'Sedra Harness', selektor: 'body', dateien: ['shell.js']});
          K.registrieren({id: 'taskleiste', titel: 'Taskleiste', selektor: '.hs-taskleiste', dateien: ['taskleiste.js']});
          K.registrieren({id: 'zelle', titel: 'Statuszelle', selektor: '.hs-zelle', dateien: ['taskleiste.js']});
          K.registrieren({id: 'kaputt', titel: 'Kaputt', selektor: '[[[', dateien: []});
          console.log(JSON.stringify({von_zelle: K.finden(zelle).map(t=>t.modul.id), von_leiste: K.finden(taskleiste).map(t=>t.modul.id), nichts: K.finden(null)}));
        """)
        self.assertEqual(out['von_zelle'], ['zelle', 'taskleiste', 'harness'], 'das innerste zuerst; ein kaputter Selektor stört nicht')
        self.assertEqual(out['von_leiste'], ['taskleiste', 'harness'])
        self.assertEqual(out['nichts'], [])

    def test_entwurf_nennt_ort_modul_dateien_und_inhalt(self):
        out = run_js(DATEIEN, KNOTEN + """
          const K = box.sedraHarness.kontext;
          K.registrieren({id: 'harness', titel: 'Sedra Harness', selektor: 'body', dateien: ['shell.js']});
          K.registrieren({id: 'taskleiste', titel: 'Taskleiste', selektor: '.hs-taskleiste', dateien: ['taskleiste.js']});
          K.registrieren({id: 'zelle', titel: 'Statuszelle', selektor: '.hs-zelle', dateien: ['taskleiste.js', 'shell.css']});
          const t = K.finden(zelle);
          console.log(JSON.stringify({anpassen: K.entwurf('anpassen', t, 'Temp 43 °C'), frage: K.entwurf('frage', t, ''), pfad: K.PFAD}));
        """)
        self.assertEqual(out['anpassen'].split('\n'), [
            'Passe diesen Teil der Oberfläche von Sedra an:', 'Teil: Sedra Harness › Taskleiste › Statuszelle',
            'Modul: zelle (' + out['pfad'] + 'taskleiste.js, ' + out['pfad'] + 'shell.css)', 'Sichtbarer Inhalt: „Temp 43 °C“', 'Was soll anders sein: '])
        self.assertNotIn('Sichtbarer Inhalt', out['frage'], 'ohne Inhalt keine leere Zeile')
        self.assertTrue(out['frage'].startswith('Erkläre mir diesen Teil'))

    def test_die_tabelle_nennt_nur_dateien_die_es_gibt_und_die_shell_laedt_sie(self):
        quelle = (HARNESS / 'kontextmodule.js').read_text(encoding='utf-8')
        dateien = set(re.findall(r"dateien: \[([^\]]*)\]", quelle))
        namen = {n for liste in dateien for n in re.findall(r"'([^']+)'", liste)}
        self.assertTrue(namen)
        for n in namen:
            self.assertTrue((HARNESS / n).exists(), f'{n} steht in kontextmodule.js, liegt aber nicht in der Harness')
        yaml = (HARNESS / 'shell.yaml').read_text(encoding='utf-8')
        self.assertLess(yaml.index('kontext.js'), yaml.index('kontextmodule.js'), 'erst die Anmeldung, dann die Tabelle')
        self.assertIn('kontext.css', yaml)
        ids = re.findall(r"\{id: '([^']+)'", quelle)
        self.assertEqual(len(ids), len(set(ids)), 'jede Modul-ID nur einmal')

    def test_keine_modulbeschreibung_nutzt_html(self):
        quelle = (HARNESS / 'kontext.js').read_text(encoding='utf-8')
        self.assertNotIn('innerHTML', quelle, 'Texte kommen nur als textContent in die Oberfläche')


if __name__ == '__main__':
    unittest.main()
