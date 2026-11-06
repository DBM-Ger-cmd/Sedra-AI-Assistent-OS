"""Eigene Skills von SEDRA: eine Quelle (skills/), Kopien für Claude Code (.claude/skills/), eigene Bibliothek für SEDRA (skill_library.yaml, Eintrag `sedra`)."""
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.skill_library import SkillLibrary
from guppi_runtime.skill_library import config as skill_config

REPO = Path(__file__).resolve().parents[2]
QUELLE = REPO / 'skills'
KOPIE = REPO / '.claude' / 'skills'
FRONT = re.compile(r'\A---\nname: ([a-z0-9-]+)\ndescription: (.+)\n---\n', re.S)


def skills():
    return sorted(p.parent.name for p in QUELLE.glob('*/SKILL.md'))


class EigeneSkills(unittest.TestCase):
    def test_es_gibt_die_skills(self):
        self.assertEqual(skills(), ['chat-sichern', 'sedra-tests-windows', 'sedra-ui-vertrag', 'selbstabbild-erweitern', 'update-einspielen'])

    def test_kopf_und_ordnername_stimmen(self):
        for name in skills():
            text = (QUELLE / name / 'SKILL.md').read_bytes().decode('utf-8').replace('\r\n', '\n')
            m = FRONT.match(text)
            self.assertIsNotNone(m, name)
            self.assertEqual(m.group(1), name)
            self.assertGreater(len(m.group(2)), 60, 'die Beschreibung sagt, wann der Skill gilt')
            self.assertLess(len(text.splitlines()), 120, 'ein Skill bleibt kurz')

    def test_keine_lokalen_pfade_und_keine_schluessel(self):
        for name in skills():
            text = (QUELLE / name / 'SKILL.md').read_text(encoding='utf-8')
            self.assertIsNone(re.search(r'[A-Za-z]:[\\/](Users|Sedra|KI)', text), name)
            self.assertIsNone(re.search(r'(ghp_|sk-)[A-Za-z0-9]{16,}', text), name)

    def test_kopien_fuer_claude_code_sind_gleich(self):
        for name in skills():
            kopie = KOPIE / name / 'SKILL.md'
            self.assertTrue(kopie.is_file(), f'{name}: Kopie fehlt, skills/ nach .claude/skills/ kopieren')
            self.assertEqual(kopie.read_bytes(), (QUELLE / name / 'SKILL.md').read_bytes(), f'{name}: Kopie weicht ab')

    def test_sedra_baut_seine_bibliothek_aus_den_skills(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(QUELLE, Path(tmp) / 'skills')      # die Quelle ../skills zählt ab dem runtime-Ordner
            (Path(tmp) / 'runtime').mkdir()
            bericht = skill_config.build_configured('sedra', runtime=Path(tmp) / 'runtime')
            self.assertTrue(bericht)
            lib = SkillLibrary(Path(tmp) / 'runtime' / 'runtime_data' / 'skill_library_sedra')
            treffer = lib.search('update einspielen patch pruefen', limit=3)
            self.assertTrue(any(t['id'] == 'update-einspielen' for t in treffer), treffer)


if __name__ == '__main__':
    unittest.main()
