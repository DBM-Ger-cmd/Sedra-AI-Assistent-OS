"""Die Wissensbasis des Arbeitsumfelds (arbeitsumfeld_wissen.py): Ordner, Läufe, Regeln, Modelle, Vorarbeiter.

Alle Tests arbeiten in einem Wegwerf-Ordner mit nachgebautem Layout. Ein Geheimnis in local_config/cloud_keys.json und ein
Prompt im Protokoll dürfen nie im Ergebnis auftauchen.
"""
import json
import tempfile
import unittest
from pathlib import Path

from guppi_runtime import arbeitsumfeld_wissen as aw
from guppi_runtime.arbeitsumfeld_wissen import ArbeitsumfeldWissen, DATEI
from host_isolation import setUpModule, tearDownModule  # noqa: F401

GEHEIM = 'GEHEIMER-SCHLUESSEL-123'
PROMPT = 'Bitte prüfe Lena Beispiel, lena@example.com, Kundennummer K-1042'

REGELWERK = """# Regelwerk Standardläufe

## 1. Geltungsbereich und Grundsätze

1. **Sandbox statt Live-Code.** Ein Lauf schreibt nur in seinen eigenen Schreibbereich unter `workspace/GUPPI_OS/redesign/`.

## 8. Präzedenzfälle

| Lauf | Modell | Schreibbereich | Zweck | Besonderheit |
|---|---|---|---|---|
| shells | je Shell ein eigenes | je Shell ein eigener Dateibereich | Umbau der sechs Oberflächen | Modellwahl je Shell |
| drache | nemotron-3.5-super-vl | `drache_lab/drache.js` | Seedrache als Entwurf | Ausgangsversion als Vorlage |
| omni | nemotron-3.5-super-vl | `omni_lab/out/` | Bewertung eines fremden Projekts | Fremde Auszüge vor dem Versand bereinigt |

## 10. Frei anlegbare Läufe

Neue Aufträge werden als Definition angelegt.
"""

AUFTRAG = """# Auftrag: einheitlicher Import

## 1. Anlass

Der Captain konnte mit dem bisherigen Weg nichts richtig importieren.

## 3. Ablauf (verbindlich)

1. **Quelle wählen.** Ein Feld für den vollständigen Ordnerpfad.
"""

VORARBEITER = '''LAUFE = {"shells": [], "drache": []}
SPERRE_S = 6 * 3600
def aktion(project_root, name, args, audit=None):
    if name == "lauf_status":
        pass
    elif name == "lauf_anlegen":
        pass
    elif name == "neue_unbeschriebene":
        pass
'''


class DasArbeitsumfeld(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='arbeitsumfeld-'); self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / 'repo'
        self.project = self.repo / 'workspace' / 'GUPPI_OS'
        (self.repo / 'docs').mkdir(parents=True)
        (self.repo / 'runtime' / 'src' / 'guppi_runtime').mkdir(parents=True)
        (self.repo / 'docs' / 'REGELWERK_STANDARDLAEUFE.md').write_text(REGELWERK, encoding='utf-8')
        (self.repo / 'docs' / 'AUFTRAG_EINHEITLICHER_IMPORT_2026-10-16.md').write_text(AUFTRAG, encoding='utf-8')
        (self.repo / 'runtime' / 'src' / 'guppi_runtime' / 'vorarbeiter.py').write_text(VORARBEITER, encoding='utf-8')
        (self.project / 'local_config').mkdir(parents=True)
        (self.project / 'local_config' / 'cloud_keys.json').write_text(json.dumps({'key': GEHEIM}), encoding='utf-8')
        (self.project / 'local_config' / 'modell_zustand.json').write_text(json.dumps({
            'nvidia|nemotron-3.5-super-vl-120b-a12b': {'ok': True, 'ms': 2100, 'zeit': '2026-10-16 14:52:53'},
            'nvidia|langsam-modell': {'ok': True, 'ms': 9000, 'zeit': '2026-10-16 14:55:00'},
            'nvidia|kaputt-modell': {'ok': False, 'ms': 0, 'zeit': '2026-10-16 14:56:00'},
        }), encoding='utf-8')
        (self.project / 'redesign' / 'laeufe').mkdir(parents=True)
        (self.project / 'redesign' / 'laeufe' / 'sedra-drache.json').write_text(json.dumps({
            'name': 'sedra-drache', 'art': 'bauen', 'beschreibung': 'Sedra-Drache als OpenSCAD-Objekt', 'lab': 'workbench',
            'provider': 'nvidia', 'model': 'nvidia/nemotron-3.5-super-vl-120b-a12b', 'task': 'Geheimer Auftragstext',
            'allow': ['objekt.scad'], 'outputs': ['objekt.scad', 'beschreibung.md']}), encoding='utf-8')
        (self.project / 'redesign' / 'workbench').mkdir()
        (self.project / 'redesign' / 'einreichen').mkdir()
        (self.project / 'redesign' / 'unbekannter_ordner').mkdir()
        (self.project / 'redesign' / 'lauf_retro.jsonl').write_text('\n'.join([
            json.dumps({'t': '11:29:02', 'event': 'LAUF_START', 'payload': {'shell': 'retro'}}),
            json.dumps({'t': '11:29:05', 'event': 'SG_MODEL_CALL', 'payload': {'prompt': PROMPT}}),
            json.dumps({'t': '11:30:00', 'event': 'LAUF_ENDE', 'payload': {}}),
        ]), encoding='utf-8')
        (self.project / 'redesign' / 'lauf_abbruch.jsonl').write_text(
            json.dumps({'t': '12:00:00', 'event': 'LAUF_START', 'payload': {}}) + '\n', encoding='utf-8')
        self.w = ArbeitsumfeldWissen(self.project, self.repo)
        self.addCleanup(self.w.close)

    def alle_texte(self):
        return ' '.join(str(row) for row in self.w._db.execute('SELECT id, art, titel, text, quelle FROM wissen').fetchall())

    def eintrag(self, rid):
        rows = self.w._db.execute('SELECT art, titel, text, quelle FROM wissen WHERE id = ?', (rid,)).fetchall()
        self.assertEqual(len(rows), 1, rid)
        return rows[0]

    # ---- Ordner
    def test_folders_are_described_and_unknown_ones_say_so(self):
        self.assertIn('Sandbox', self.eintrag('O-redesign')[2])
        self.assertIn('Einträge', self.eintrag('O-redesign/workbench')[2] + ' Einträge')
        self.assertIn('Zweck im Projekt nicht beschrieben', self.eintrag('O-redesign/einreichen')[2])
        self.assertIn('Zweck nicht beschrieben', self.eintrag('O-redesign/unbekannter_ordner')[2])

    def test_the_key_file_is_never_read(self):
        self.assertNotIn(GEHEIM, self.alle_texte())
        self.assertIn('Schlüssel', self.eintrag('O-local_config')[2])

    # ---- Läufe
    def test_the_precedent_table_becomes_one_entry_per_run(self):
        self.assertEqual(self.eintrag('L-drache')[0], 'lauf')
        self.assertIn('drache_lab/drache.js', self.eintrag('L-drache')[2])
        self.assertIn('Präzedenzfall', self.eintrag('L-omni')[1])
        self.assertIsNone(self.w._db.execute("SELECT id FROM wissen WHERE id = 'L-Lauf'").fetchone())

    def test_defined_runs_show_their_purpose_and_outputs(self):
        text = self.eintrag('L-sedra-drache')[2]
        self.assertIn('Sedra-Drache als OpenSCAD-Objekt', text)
        self.assertIn('beschreibung.md', text)
        self.assertNotIn('Geheimer Auftragstext', self.alle_texte())

    def test_protocol_status_without_content(self):
        self.assertIn('beendet', self.eintrag('P-retro')[2])
        self.assertIn('nicht sauber beendet', self.eintrag('P-abbruch')[2])
        self.assertNotIn(PROMPT, self.alle_texte())
        self.assertIn('lauf_retro', self.eintrag('O-redesign/lauf_retro.jsonl')[1] + ' lauf_retro')

    # ---- Regeln und Auftrag
    def test_rules_and_brief_sections_are_stored_and_found(self):
        self.assertEqual(self.eintrag('R-01')[0], 'regel')
        self.assertEqual(self.eintrag('A-01')[0], 'auftrag')
        treffer = [t['id'] for t in self.w.suche('Schreibbereich Sandbox Lauf', limit=20)]
        self.assertIn('R-01', treffer)
        self.assertIn('A-01', [t['id'] for t in self.w.suche('Anlass Captain')])

    # ---- Modelle
    def test_model_state_comes_as_traffic_light(self):
        self.assertIn('Ampel: gruen', self.eintrag('M-nvidia-nemotron-3.5-super-vl-120b-a12b')[2])
        self.assertIn('Ampel: gelb', self.eintrag('M-nvidia-langsam-modell')[2])
        self.assertIn('Ampel: rot', self.eintrag('M-nvidia-kaputt-modell')[2])

    def test_without_model_file_the_entry_says_grey(self):
        (self.project / 'local_config' / 'modell_zustand.json').unlink()
        w = ArbeitsumfeldWissen(self.project, self.repo)
        self.addCleanup(w.close)
        self.assertIn('grau', w._db.execute("SELECT text FROM wissen WHERE id = 'M-leer'").fetchone()[0])

    # ---- Vorarbeiter
    def test_actions_come_from_source_and_unknown_ones_are_marked(self):
        self.assertIn('Liste der Läufe', self.eintrag('V-lauf_status')[2])
        self.assertIn('ohne Beschreibung', self.eintrag('V-neue_unbeschriebene')[2])
        self.assertIn('6 Stunden', self.eintrag('V-sperre')[2])

    def test_every_action_in_the_real_source_has_a_description(self):
        # Drift-Wache: fügt der Vorarbeiter eine Aktion hinzu, muss AKTION_ZWECK sie ebenfalls kennen.
        import re
        quelle = Path(__file__).resolve().parents[1] / 'src' / 'guppi_runtime' / 'vorarbeiter.py'
        namen = set(re.findall(r'name == "(\w+)"', quelle.read_text(encoding='utf-8')))
        self.assertTrue(namen)
        for n in namen:
            self.assertIn(n, aw.AKTION_ZWECK, f'Aktion {n} ohne Beschreibung in AKTION_ZWECK')

    # ---- Suche und Kontext
    def test_search_ignores_stopwords_and_empty_questions(self):
        self.assertEqual(self.w.suche('wie ist das?'), [])
        self.assertEqual(self.w.suche(''), [])

    def test_search_ranks_title_hits_first(self):
        treffer = self.w.suche('drache')
        self.assertTrue(treffer)
        self.assertEqual(treffer[0]['id'], 'L-drache')

    def test_context_block_keeps_the_limit_and_names_sources(self):
        block = self.w.kontext('drache', limit=5, zeichen=600)
        self.assertTrue(block)
        self.assertLessEqual(len(block), 600)
        self.assertIn('(Quelle:', block)
        self.assertEqual(self.w.kontext('zzzz qqqq'), '')

    # ---- Aufbau und Quellen
    def test_rebuild_replaces_instead_of_duplicating(self):
        anzahl = self.w.anzahl()
        self.assertEqual(self.w.aufbauen(), anzahl)
        self.assertEqual(self.w.anzahl(), anzahl)

    def test_rebuild_picks_up_changes_on_disk(self):
        (self.project / 'redesign' / 'spec_lab').mkdir()
        self.w.aufbauen()
        self.assertIn('Einträge', self.eintrag('O-redesign/spec_lab')[2] + ' Einträge')

    def test_sources_list_hash_and_presence(self):
        quellen = {q['pfad']: q for q in self.w.quellen()}
        self.assertTrue(quellen['docs/REGELWERK_STANDARDLAEUFE.md']['vorhanden'])
        self.assertEqual(len(quellen['docs/REGELWERK_STANDARDLAEUFE.md']['sha256']), 16)
        (self.repo / 'docs' / 'AUFTRAG_EINHEITLICHER_IMPORT_2026-10-16.md').unlink()
        self.assertFalse({q['pfad']: q for q in self.w.quellen()}['docs/AUFTRAG_EINHEITLICHER_IMPORT_2026-10-16.md']['vorhanden'])

    def test_the_store_lives_under_local_config(self):
        self.assertEqual(self.w.path, self.project / DATEI)
        self.assertTrue(self.w.path.is_file())


if __name__ == '__main__':
    unittest.main()
