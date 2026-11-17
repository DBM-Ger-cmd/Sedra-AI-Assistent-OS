"""Der Drache in der Taskleiste (leben.js): der Zustand kommt nur aus echten Tatsachen, Bewegung ist abschaltbar,
und die Skripte sind richtig eingehängt. Die Zustandsregel läuft über node (wie test_uix_avatar)."""
import json
import subprocess
import unittest
from pathlib import Path

from sedra_runtime.desk import gateway

SHELL = Path(gateway.__file__).resolve().parents[1] / 'uix' / 'shells' / 'harness'
SKRIPT = SHELL / 'leben.js'


def stimmung(z):
    code = "const L = require(process.argv[1]); console.log(JSON.stringify(L.stimmung(JSON.parse(process.argv[2]))));"
    aus = subprocess.run(['node', '-e', code, str(SKRIPT), json.dumps(z)], capture_output=True, text=True, timeout=60, encoding='utf-8')
    if aus.returncode:
        raise AssertionError(aus.stderr)
    return json.loads(aus.stdout)


JETZT = 1_000_000


class StimmungAusTatsachen(unittest.TestCase):
    def test_ruhe_ohne_lauf_und_ohne_freigabe(self):
        self.assertEqual(stimmung({'laeuft': False, 'phase': None, 'wartet': False, 'flash': None, 'jetzt': JETZT}), 'ruhe')

    def test_warten_wenn_anfrage_laeuft_ohne_erste_regung(self):
        self.assertEqual(stimmung({'laeuft': True, 'phase': None, 'wartet': False, 'flash': None, 'jetzt': JETZT}), 'warten')

    def test_denken_nur_in_der_phase_denkt(self):
        self.assertEqual(stimmung({'laeuft': True, 'phase': 'denkt', 'wartet': False, 'flash': None, 'jetzt': JETZT}), 'denken')

    def test_schreiben_bei_antwort_und_werkzeug(self):
        for phase in ['schreibt', 'Werkzeug dateiliste']:
            with self.subTest(phase=phase):
                self.assertEqual(stimmung({'laeuft': True, 'phase': phase, 'wartet': False, 'flash': None, 'jetzt': JETZT}), 'schreiben')

    def test_freigabe_wartet_auch_ohne_laufende_antwort(self):
        self.assertEqual(stimmung({'laeuft': False, 'phase': None, 'wartet': True, 'flash': None, 'jetzt': JETZT}), 'warten')

    def test_freigabe_hat_vorrang_vor_denken(self):
        self.assertEqual(stimmung({'laeuft': True, 'phase': 'denkt', 'wartet': True, 'flash': None, 'jetzt': JETZT}), 'warten')

    def test_fertig_und_fehler_klingen_kurz_nach(self):
        frisch = {'art': 'fertig', 'bis': JETZT + 1800}
        self.assertEqual(stimmung({'laeuft': False, 'phase': None, 'wartet': False, 'flash': frisch, 'jetzt': JETZT}), 'fertig')
        self.assertEqual(stimmung({'laeuft': False, 'phase': None, 'wartet': False, 'flash': {'art': 'fehler', 'bis': JETZT + 1800}, 'jetzt': JETZT}), 'fehler')

    def test_abgelaufener_blitz_faellt_in_die_ruhe_zurueck(self):
        abgelaufen = {'art': 'fertig', 'bis': JETZT - 1}
        self.assertEqual(stimmung({'laeuft': False, 'phase': None, 'wartet': False, 'flash': abgelaufen, 'jetzt': JETZT}), 'ruhe')

    def test_fehler_blitz_gewinnt_gegen_laufende_anfrage(self):
        self.assertEqual(stimmung({'laeuft': True, 'phase': 'denkt', 'wartet': False, 'flash': {'art': 'fehler', 'bis': JETZT + 1800}, 'jetzt': JETZT}), 'fehler')


class Einbau(unittest.TestCase):
    def test_skript_und_stil_stehen_in_der_shell(self):
        yaml = (SHELL / 'shell.yaml').read_text(encoding='utf-8')
        self.assertIn('leben.js', yaml)
        self.assertIn('leben.css', yaml)
        self.assertLess(yaml.index(' avatar.js,'), yaml.index(' leben.js,'))
        self.assertLess(yaml.index(' leben.js,'), yaml.index(' shell.js]'))

    def test_shell_und_taskleiste_rufen_den_drachen_auf(self):
        self.assertIn('H.leben.mount(this)', (SHELL / 'shell.js').read_text(encoding='utf-8'))
        tl = (SHELL / 'taskleiste.js').read_text(encoding='utf-8')
        self.assertIn('root.sedraHarness.leben.knopf(S)', tl)
        self.assertIn('root.sedraHarness.leben.zeichnen(S)', tl)

    def test_begleiter_zeichnet_das_3d_modell_nur_auf_anfrage(self):
        buehne = (SHELL / 'buehne3d.js').read_text(encoding='utf-8')
        self.assertIn('function standbild(', buehne)
        self.assertIn('standbild,', buehne)                                  # exportiert
        self.assertNotIn('requestAnimationFrame', buehne[buehne.index('function standbild('):buehne.index('root.sedraHarness.buehne3d = {')])
        self.assertIn('bild3d(el, s)', SKRIPT.read_text(encoding='utf-8'))

    def test_keine_dauerschleife_in_der_zustandsanzeige(self):
        self.assertNotIn('setInterval', SKRIPT.read_text(encoding='utf-8'))

    def test_rechtsklick_menue_steuert_begleiter_und_bewegung(self):
        js = SKRIPT.read_text(encoding='utf-8')
        self.assertIn("addEventListener('contextmenu'", js)                  # Rechtsklick öffnet das Menü
        self.assertIn('sedra.harness.begleiter', js)                         # immer | arbeit | aus
        self.assertIn('sedra.harness.bewegung', js)                          # an | aus
        self.assertIn("'Escape'", js)                                        # Esc schließt
        self.assertIn("'hs-still'", js)                                      # Bewegung aus = Klasse auf der Shell
        css = (SHELL / 'leben.css').read_text(encoding='utf-8')
        self.assertIn('.hs.hs-still', css)
        self.assertIn('.hs-leben-menu', css)

    def test_reduzierte_bewegung_und_abschalten(self):
        css = (SHELL / 'leben.css').read_text(encoding='utf-8')
        self.assertIn('prefers-reduced-motion: reduce', css)
        self.assertIn('sedra.harness.lebendig', SKRIPT.read_text(encoding='utf-8'))

    def test_texte_in_beiden_sprachen(self):
        text = (SHELL / 'strings_avatar.js').read_text(encoding='utf-8')
        for schluessel in ['lb_ruhe', 'lb_warten', 'lb_denken', 'lb_schreiben', 'lb_fertig', 'lb_fehler', 'lw_denken', 'lw_schreiben', 'lw_warten', 'lw_fertig', 'lw_fehler',
                          'lm_titel', 'lm_begleiter', 'lm_immer', 'lm_arbeit', 'lm_aus', 'lm_bewegung_an', 'lm_bewegung_aus']:
            self.assertEqual(text.count(schluessel + ':'), 2, schluessel)


if __name__ == '__main__':
    unittest.main()
