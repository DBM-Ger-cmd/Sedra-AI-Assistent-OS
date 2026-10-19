"""Auto-Update Teil 2: Herunterladen und sicheres Entpacken. Ohne Netz: der Download wird durch ein Zip im Speicher ersetzt."""
import io
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

from guppi_runtime import update_holen as uh
from guppi_runtime.update_anwenden import UpdateFehler


def zip_mit(eintraege):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        for name, text in eintraege:
            zf.writestr(name, text)
    return buf.getvalue()


def zip_mit_link(name, ziel):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        info = zipfile.ZipInfo(name)
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        zf.writestr(info, ziel)
    return buf.getvalue()


class HolenTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_nur_release_tags_werden_geladen(self):
        for tag in ('main', 'v1.2', '../v1.2.3', 'v1.2.3/x'):
            with self.assertRaisesRegex(UpdateFehler, 'tag_ungueltig', msg=tag):
                uh.herunterladen(self.root, tag, holen=lambda url: b'')

    def test_stand_wird_ohne_oberordner_in_den_staging_ordner_gelegt(self):
        daten = zip_mit([('Sedra-1.22.0/runtime/src/guppi_runtime/kern.py', 'X = 1\n'), ('Sedra-1.22.0/release/MANIFEST.sha256', 'x\n')])
        ziel = uh.herunterladen(self.root, 'v1.22.0', holen=lambda url: daten)
        self.assertEqual((ziel / 'runtime/src/guppi_runtime/kern.py').read_text(encoding='utf-8'), 'X = 1\n')
        self.assertFalse((ziel / 'entpackt').exists())
        self.assertFalse((ziel.parent / 'v1.22.0.zip').exists())

    def test_pfad_nach_aussen_wird_abgelehnt(self):
        daten = zip_mit([('Sedra-1.22.0/../../evil.py', 'x')])
        with self.assertRaisesRegex(UpdateFehler, 'archiv_pfad_nicht_erlaubt'):
            uh.herunterladen(self.root, 'v1.22.0', holen=lambda url: daten)
        self.assertFalse((self.root / 'evil.py').exists())

    def test_link_im_archiv_wird_abgelehnt(self):
        daten = zip_mit_link('Sedra-1.22.0/runtime/src/guppi_runtime/link.py', '/etc/passwd')
        with self.assertRaisesRegex(UpdateFehler, 'archiv_link_nicht_erlaubt'):
            uh.herunterladen(self.root, 'v1.22.0', holen=lambda url: daten)

    def test_nur_github_als_quelle(self):
        with self.assertRaisesRegex(UpdateFehler, 'quelle_nicht_erlaubt'):
            uh._netz_holen('http://example.org/x.zip')


if __name__ == '__main__':
    unittest.main()
