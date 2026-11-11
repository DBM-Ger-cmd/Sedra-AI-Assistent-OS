"""Der alte Produktname steht nur noch im Verlauf (Logbuch, historische und datierte Berichte, Concept Review)."""
import re
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ALT = ''.join(('gup', 'pi'))
VERLAUF_PREFIX = ('docs/LOGBUCH_AGENT_MANAGER.md', 'docs/historie/', 'concept_review/')
# Stellen, die den alten Namen mit Absicht nennen (Grund je Eintrag). Neue Treffer sind ein Fehler, ausser sie stehen hier mit Grund.
ERLAUBT = {
    'runtime/src/sedra_runtime/models/engine_provision.py': 'liest das alte Engine-Manifest installierter Staende (LEGACY_MANIFESTS)',
    'runtime/tests/test_engine_provision.py': 'prueft das Lesen des alten Engine-Manifests',
    '.claude/skills/sedra-fragen/SKILL.md': 'nennt den alten lokalen Schluessel in local_paths.yaml (Konfiguration der Maschine)',
    '.claude/skills/sedra-logs-lesen/SKILL.md': 'erklaert aelteren Notizen, den alten Ordnernamen vor dem Namenswechsel',
    'docs/ANALYSE_MOD-03_LUECKEN_STAND_87ce2a6.md': 'Analyse eines Standes, beschreibt den Namenswechsel selbst',
    'docs/WISSEN_SEDRA_GESAMT.md': 'Wissensdatei mit Verlauf (Name einer frueheren Windows-Aufgabe)',
}
DATIERT = re.compile(r'(^|/)[^/]*_20\d\d-\d\d-\d\d[^/]*$')


def verlauf(rel):
    return rel.startswith(VERLAUF_PREFIX) or rel.endswith('.sha256') or (rel.startswith('docs/') and DATIERT.search(rel) is not None)


def tracked():
    try:
        out = subprocess.run(['git', '-C', str(REPO), 'ls-files', '-z'], check=True, capture_output=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return [f for f in out.decode('utf-8').split('\0') if f]


class AlteNamen(unittest.TestCase):
    def test_kein_alter_name_in_dateien_oder_inhalt(self):
        files = tracked()
        if files is None:
            self.skipTest('kein Git-Repository')
        treffer = []
        for rel in files:
            if verlauf(rel) or rel in ERLAUBT:
                continue
            if ALT in rel.lower():
                treffer.append('Name: ' + rel)
                continue
            p = REPO / rel
            if not p.is_file() or p.stat().st_size > 5_000_000:
                continue
            raw = p.read_bytes()
            if b'\0' in raw[:4096]:
                continue
            try:
                text = raw.decode('utf-8')
            except UnicodeDecodeError:
                continue
            if ALT in text.lower():
                treffer.append('Inhalt: ' + rel)
        self.assertEqual(treffer, [], 'Alter Name außerhalb des Verlaufs: ' + ', '.join(treffer[:10]))


if __name__ == '__main__':
    unittest.main()
