"""F1-01: SEDRA/GUPPI Kompatibilitätsmatrix — Validierung.

Prüft, dass nach dem Namenswechsel (SEDRA-NAME-01) keine alten GUPPI-Bezeichnungen
mehr im neuen Code (`sedra_runtime`) verwendet werden. Alte Namen dürfen nur in
`legacy_names.py` (Übergang) und `engine_provision.py` (Lesen alter Manifests)
vorkommen.

Keine externen Abhängigkeiten, kein Modell, kein Netzwerk. Laufbar mit unittest.
"""
from __future__ import annotations

import re
from pathlib import Path

import unittest

# Das Repository-Root (Eltern-Eltern von tests/)
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'runtime' / 'src' / 'sedra_runtime'

# Muster, die im *neuen* Code nicht mehr vorkommen dürfen.
ALTE_NAMEN_MUSTER = [
    r'guppi_runtime',
    r'GUPPI_OS',
    r'GUPPI_Architecture',
    r'guppi_engine',
    r'GUPPI_API_KEY',
    r'GUPPI_ENDPOINT',
]

# Dateien, in denen alte Namen ausdrücklich als Legacy erlaubt sind.
ERLAUBTE_LEGACY_DATEIEN = {
    'legacy_names.py',          # Übergang für alte Installationen
    'engine_provision.py',      # Lese-only alte Manifests
    '__init__.py',              # ruft env_aliase() auf (Übergang)
}


def _datei_enthalt_alten_namen(pfad: Path) -> list[str]:
    """Gibt eine Liste der gefundenen alten Namen in der Datei zurück."""
    try:
        text = pfad.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return []
    gefundene: list[str] = []
    for muster in ALTE_NAMEN_MUSTER:
        if re.search(muster, text):
            gefundene.append(muster)
    return gefundene


class KompatibilitaetTest(unittest.TestCase):
    def test_keine_alten_imports_in_sedra_runtime(self):
        """Keine Datei unter sedra_runtime/ darf guppi_runtime als Paket importieren."""
        verstosse: dict[str, list[str]] = {}
        for pfad in sorted(SRC.rglob('*.py')):
            name = pfad.name
            if name in ERLAUBTE_LEGACY_DATEIEN:
                continue
            treffer = _datei_enthalt_alten_namen(pfad)
            if treffer:
                relativ = pfad.relative_to(ROOT).as_posix()
                verstosse[relativ] = treffer
        self.assertEqual(
            verstosse,
            {},
            'Alte GUPPI-Bezeichnungen im neuen Code gefunden: '
            + ', '.join(f'{k}: {v}' for k, v in sorted(verstosse.items())),
        )

    def test_legacy_names_enthalt_alten_namen(self):
        """legacy_names.py definiert die alten Namen als Konstanten (Übergang)."""
        pfad = SRC / 'legacy_names.py'
        self.assertTrue(pfad.is_file(), 'legacy_names.py fehlt')
        text = pfad.read_text(encoding='utf-8')
        # Die alten Namen sind absichtlich zerlegt gespeichert (siehe Doku in der Datei)
        self.assertIn("_ALT = ''.join(('GUP', 'PI'))", text)
        self.assertIn("PROJEKTORDNER_ALT = _ALT + '_OS'", text)
        self.assertIn("ARCHITEKTUR_ALT = _ALT + '_Architecture_'", text)
        self.assertIn("PAKET_ALT = _ALT_KLEIN + '_runtime'", text)

    def test_engine_provision_enthalt_legacy_manifest(self):
        """engine_provision.py darf guppi_engine.json als LEGACY_MANIFESTS kennen."""
        pfad = SRC / 'models' / 'engine_provision.py'
        self.assertTrue(pfad.is_file(), 'engine_provision.py fehlt')
        text = pfad.read_text(encoding='utf-8')
        self.assertIn('guppi_engine.json', text)


if __name__ == '__main__':
    unittest.main()
