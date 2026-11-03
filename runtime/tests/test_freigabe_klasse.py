"""G9-01 (SPEC_APPS_v1_O3PLUS_G9_G2 §3.3): die Klassen H/N der Freigaben – Ablehnen ist immer N, Unbekanntes ist H."""
import unittest

from guppi_runtime.desk.freigabeklasse import ARTEN, H, N, klasse


class Grundregeln(unittest.TestCase):
    def test_ablehnen_und_zuruecknehmen_sind_immer_n(self):
        for art in list(ARTEN) + ['gibt-es-nicht']:
            for weg in ('ablehnen', 'zuruecknehmen', 'zur_kenntnis'):
                self.assertEqual(klasse(art, weg, {}), N, (art, weg))

    def test_unbekanntes_ist_h(self):
        self.assertEqual(klasse('gibt-es-nicht', 'einmal'), H)
        self.assertEqual(klasse('request:switch', 'gibt-es-nicht'), H)
        self.assertEqual(klasse('request:neu', 'freigeben_und_anwenden'), H)
        self.assertEqual(klasse(None, None), H)

    def test_jede_art_ergibt_h_oder_n(self):
        for art in ARTEN:
            for weg in ('einmal', 'freigeben_und_anwenden', 'aendern', 'cloud_diesen_lauf', 'bestaetigen', 'erlauben', 'sitzung',
                        'uebernehmen', 'zuruecksetzen'):
                self.assertIn(klasse(art, weg, {}), (H, N), (art, weg))


class Tabelle(unittest.TestCase):
    """§3.3 Zeile für Zeile, wie vom Captain am 03.11.2026 übernommen (E2)."""

    def test_regeln_code_und_rechte_sind_h(self):
        for art in ('gate', 'request:switch', 'request:routing', 'request:boundaries', 'request:harness_katalog', 'request:harness_vorlage',
                    'request:install', 'request:trust', 'request:update', 'request:model_add', 'request:skill', 'request:cloud_url',
                    'request:orchestra', 'request:standing', 'request:harness_projekt', 'request:wissen_quelle', 'request:wissen_vorschlag'):
            self.assertEqual(klasse(art, 'freigeben_und_anwenden', {}), H, art)
            self.assertEqual(klasse(art, 'einmal', {}), H, art)

    def test_grenze_und_cloud(self):
        self.assertEqual(klasse('boundary', 'einmal', {}), H)
        self.assertEqual(klasse('boundary', 'aendern', {}), H)
        self.assertEqual(klasse('cloud_offload', 'cloud_diesen_lauf', {}), H)
        self.assertEqual(klasse('slot_server', 'bestaetigen', {}), N)                    # E2c

    def test_gateway_nach_weg(self):
        self.assertEqual(klasse('request:gateway', 'freigeben_und_anwenden', {'weg': 'LOCAL_ONLY'}), N)
        self.assertEqual(klasse('request:gateway', 'freigeben_und_anwenden', {'weg': 'CLOUD_ALLOWED'}), H)
        self.assertEqual(klasse('request:gateway', 'freigeben_und_anwenden', {'weg': 'CLOUD_AFTER_PSEUDONYMIZATION'}), H)
        self.assertEqual(klasse('request:gateway', 'freigeben_und_anwenden', {}), H)

    def test_inhaltsschutz_nach_weg_des_aufrufs(self):
        self.assertEqual(klasse('content', 'einmal', {'route': 'local'}), N)
        self.assertEqual(klasse('content', 'einmal', {'route': 'cloud'}), H)
        self.assertEqual(klasse('content', 'einmal', {}), H)                             # ohne `route` (heute) H

    def test_harness_karte(self):
        def k(werkzeug, ziel='', weg='erlauben'):
            return klasse('harness_freigabe', weg, {'werkzeug': werkzeug, 'ziel': ziel})
        self.assertEqual(k('befehl', 'python x.py'), H)
        self.assertEqual(k('lauf_starten', 'run_tests'), H)
        self.assertEqual(k('datei_schreiben', 'docs/notiz.md'), N)
        self.assertEqual(k('datei_aendern', 'runtime/tests/test_x.py'), N)
        self.assertEqual(k('datei_aendern', 'runtime/src/guppi_runtime/core/guard.py'), H)      # harter Vorbehalt
        self.assertEqual(k('datei_schreiben', 'runtime/src/guppi_runtime/harness/freigabe.py'), H)
        self.assertEqual(k('datei_schreiben', 'local_config/switches.yaml'), H)
        self.assertEqual(k('datei_aendern', 'runtime/src/guppi_runtime/desk/freigabeklasse.py'), H)           # die Tabelle selbst
        self.assertEqual(k('modell_laden', 'chat.local'), N)
        self.assertEqual(k('sitzungen_aufraeumen', 'S-1'), N)
        self.assertEqual(k('datei_schreiben', 'docs/notiz.md', weg='sitzung'), H)                # Sitzungs-Erlaubnis
        self.assertEqual(k('gibt_es_nicht'), H)
        self.assertEqual(klasse('harness_aufgabe', 'erlauben', {}), H)

    def test_g2_und_g6(self):
        self.assertEqual(klasse('harness_oberflaeche', 'uebernehmen', {}), H)
        self.assertEqual(klasse('harness_oberflaeche', 'zuruecksetzen', {}), N)
        self.assertEqual(klasse('harness_oberflaeche', 'einmal', {}), H)
        self.assertEqual(klasse('startbericht', 'zur_kenntnis', {}), N)


if __name__ == '__main__':
    unittest.main()
