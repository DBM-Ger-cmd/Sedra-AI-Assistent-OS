"""F0-06B: Einheitstests für release_meta.py (autoritäre Versionsquelle).

Keine externen Abhängigkeiten, kein Netzwerk, keine Git-Schreiboperationen.
Laufbar mit unittest.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sedra_runtime.release_meta import (  # noqa: E402
    lese_release_meta,
    release_meta,
    schreibe_release_meta,
    validate_release_meta,
)


class ReleaseMetaTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[2]

    def test_release_meta_hat_alle_felder(self):
        meta = release_meta(self.root, '1.22.3')
        for feld in ('version', 'commit', 'commit_kurz', 'manifest_hash',
                     'build_datum', 'pruefbereiche', 'dateien'):
            self.assertIn(feld, meta, f'Feld {feld} fehlt')
        self.assertEqual(meta['version'], '1.22.3')
        self.assertEqual(len(meta['commit_kurz']), 12)
        self.assertEqual(len(meta['commit']), 40)
        self.assertEqual(meta['pruefbereiche'],
                         ['runtime/src/sedra_runtime/', 'runtime/config/'])
        self.assertIsInstance(meta['dateien'], int)
        self.assertGreater(meta['dateien'], 0)

    def test_validate_konsistentes_meta_ist_leer(self):
        meta = release_meta(self.root, '1.23.0')  # CODE_VERSION ist 1.23.0
        fehler = validate_release_meta(meta, self.root)
        self.assertEqual(fehler, [])

    def test_validate_inkonsistente_version(self):
        meta = release_meta(self.root, '1.23.0')
        meta['version'] = '9.9.9'
        fehler = validate_release_meta(meta, self.root)
        self.assertTrue(any('version_inkonsistent' in f for f in fehler))

    def test_validate_inklusiver_commit(self):
        meta = release_meta(self.root, '1.23.0')
        meta['commit'] = '0' * 40
        fehler = validate_release_meta(meta, self.root)
        self.assertTrue(any('commit_inkonsistent' in f for f in fehler))

    def test_validate_inklusiver_manifest_hash(self):
        meta = release_meta(self.root, '1.23.0')
        meta['manifest_hash'] = '0' * 64
        fehler = validate_release_meta(meta, self.root)
        self.assertTrue(any('manifest_hash_inkonsistent' in f for f in fehler))

    def test_schreibe_lese_roundtrip(self):
        meta = release_meta(self.root, '1.22.3')
        with tempfile.TemporaryDirectory() as tmp:
            pfad = Path(tmp) / 'release_meta.json'
            schreibe_release_meta(meta, pfad)
            gelesen = lese_release_meta(pfad)
            self.assertEqual(gelesen, meta)

    def test_schreibe_ist_deterministisch(self):
        meta1 = release_meta(self.root, '1.22.3')
        meta2 = release_meta(self.root, '1.22.3')
        self.assertEqual(meta1['manifest_hash'], meta2['manifest_hash'])
        self.assertEqual(meta1['commit'], meta2['commit'])
        # build_datum kann unterscheiden (Sekunden-Auflösung), daher nicht vergleichen


if __name__ == '__main__':
    unittest.main()
