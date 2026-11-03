"""G11 (SPEC_APPS_v1_O3PLUS_G9_G2 §2.9): Vollständigkeit der Freigabe-Wege.

Jede Stelle mit `approve`, jede schreibende Route des Servers und der Harness und jede Entscheidungsart muss in
`desk/freigabeklasse.py` eingeordnet sein. Eine neue Stelle, Route oder Art ohne Eintrag lässt diesen Test fehlschlagen – so kann kein
neuer Freigabe-Weg an der Klasse H vorbei entstehen. G11-05 (Verhalten: Klasse H über die Seite erteilt nichts ohne Bestätigung) kommt
mit der Tür aus G9; bis dahin steht in APPROVE_STELLEN bei jeder offenen Stelle „OFFEN bis G9“."""
import ast
import re
import unittest
from pathlib import Path

from guppi_runtime.desk import decisions as desk_decisions
from guppi_runtime.desk import freigabeklasse as fk
from guppi_runtime.harness import api as harness_api

PAKET = Path(__file__).resolve().parents[1] / 'src' / 'guppi_runtime'


def _quellen():
    for p in sorted(PAKET.rglob('*.py')):
        if '__pycache__' not in p.parts:
            yield p, ast.parse(p.read_text(encoding='utf-8'))


def _aufrufe(attr_namen):
    """[(datei, funktion, aufruf, zeile)] für jeden Aufruf `x.<attr>(…)` mit attr in attr_namen; funktion = die innerste Funktion."""
    out = []
    for p, tree in _quellen():
        stapel = []

        class Besucher(ast.NodeVisitor):
            def visit_FunctionDef(self, n):
                stapel.append(n.name)
                self.generic_visit(n)
                stapel.pop()
            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Call(self, n):
                f = n.func
                if isinstance(f, ast.Attribute) and f.attr in attr_namen:
                    out.append((p.relative_to(PAKET).as_posix(), stapel[-1] if stapel else '<modul>', ast.unparse(f), n.lineno))
                self.generic_visit(n)
        Besucher().visit(tree)
    return out


class ApproveStellen(unittest.TestCase):
    """G11-01: jede Stelle, die `.approve(` ruft, steht in APPROVE_STELLEN – mit Kanal und ob sie hinter der Tür liegt."""

    def test_jede_stelle_ist_eingeordnet(self):
        gefunden = {f'{d}:{fn}:{a}': z for d, fn, a, z in _aufrufe({'approve'})}
        neu = sorted(set(gefunden) - set(fk.APPROVE_STELLEN))
        weg = sorted(set(fk.APPROVE_STELLEN) - set(gefunden))
        self.assertEqual(neu, [], 'neue approve-Stelle(n) – in desk/freigabeklasse.APPROVE_STELLEN mit Kanal und Tür eintragen: '
                                  + ', '.join(f'{k} (Zeile {gefunden[k]})' for k in neu))
        self.assertEqual(weg, [], 'Eintrag ohne Stelle im Code – entfernen oder anpassen')

    def test_guard_angabe_stimmt(self):
        for schluessel, e in fk.APPROVE_STELLEN.items():
            aufruf = schluessel.rsplit(':', 1)[1]
            self.assertEqual(e['guard'], 'guard' in aufruf, schluessel)
            self.assertTrue(e['kanal'] and e['grund'], schluessel)

    def test_stellen_aus_der_seite_liegen_hinter_der_tuer(self):
        """G9: jede Stelle, die aus der Seite erteilt, liegt hinter der Tür; keine ist mehr „OFFEN“."""
        self.assertEqual(sorted(k for k, e in fk.APPROVE_STELLEN.items() if e['tuer']),
                         ['desk/gated.py:decide:rt.guard.approve', 'harness/freigabe.py:beantworten:guard.approve',
                          'uix_server.py:approve_gate:self.runtime.guard.approve'])
        self.assertEqual([k for k, e in fk.APPROVE_STELLEN.items() if 'OFFEN' in e['grund']], [])
        for k, e in fk.APPROVE_STELLEN.items():
            if 'seite' in e['kanal']:
                self.assertTrue(e['tuer'], k)

    def test_routen_hinter_der_tuer_rufen_sie(self):
        quelle = (PAKET / 'uix_server.py').read_text(encoding='utf-8')
        for route in fk.HINTER_DER_TUER:
            m = re.search(rf"'{re.escape(route)}':\s*hub\.(\w+)", quelle)
            self.assertIsNotNone(m, route)
            self.assertTrue(m.group(1).endswith('_seite'), f'{route} → {m.group(1)}')


class Routen(unittest.TestCase):
    """G11-02: jede POST-Route des Servers und jeder Weg der Harness ist eingeordnet."""

    @classmethod
    def setUpClass(cls):
        tree = ast.parse((PAKET / 'uix_server.py').read_text(encoding='utf-8'))
        cls.post = set()
        for fn in ast.walk(tree):
            if isinstance(fn, ast.FunctionDef) and fn.name == 'do_POST':
                for n in ast.walk(fn):
                    if isinstance(n, ast.Dict):
                        cls.post |= {k.value for k in n.keys if isinstance(k, ast.Constant) and isinstance(k.value, str) and k.value.startswith('/api/')}
        from guppi_runtime import uix_server
        cls.herkunft = uix_server.HERKUNFT_WEGE

    def test_post_routen_des_servers(self):
        self.assertGreater(len(self.post), 100, 'die Routentabelle in do_POST wurde nicht gefunden')
        neu = sorted(self.post - set(fk.ROUTEN_SERVER))
        weg = sorted(set(fk.ROUTEN_SERVER) - self.post)
        self.assertEqual(neu, [], 'neue POST-Route(n) – in desk/freigabeklasse.ROUTEN_SERVER einordnen: ' + ', '.join(neu))
        self.assertEqual(weg, [], 'Eintrag ohne Route')

    def test_eintraege_haben_gueltige_form(self):
        arten = {'liest', 'antrag', 'freigabe', 'anwenden', 'zurueck', 'handlung'}
        for tabelle in (fk.ROUTEN_SERVER, fk.ROUTEN_HARNESS):
            for route, (art, kl, notiz) in tabelle.items():
                self.assertIn(art, arten, route)
                if art == 'handlung':
                    self.assertIn(kl, (fk.H, fk.N), f'{route}: eine Handlung braucht eine Klasse')
                self.assertIsInstance(notiz, str, route)

    def test_freigabe_routen_pruefen_die_herkunft(self):
        """S7: Routen, die eine Freigabe erteilen oder umsetzen, nimmt der Server aus einem Harness-Prozess nicht an."""
        for route, (art, _kl, _n) in fk.ROUTEN_SERVER.items():
            if art in ('freigabe', 'anwenden') and route != '/api/mission/run':
                self.assertTrue(self.herkunft.fullmatch(route), f'{route} fehlt in HERKUNFT_WEGE')

    def test_mission_run_braucht_den_browser_token(self):
        """/api/mission/run setzt eine Freigabe um, steht aber nicht in HERKUNFT_WEGE: Ein Harness-Prozess hat den Browser-Token nicht,
        und die externen Clients dürfen nur ihre eigenen Routen."""
        from guppi_runtime import uix_clients
        self.assertNotIn('/api/mission/run', uix_clients.ROUTES)

    def test_harness_wege(self):
        worte = set(re.findall(r'[a-z_]{3,}', harness_api.WEG.pattern)) - {'api', 'harness'}
        self.assertEqual(sorted(worte - fk.HARNESS_WEGE - fk.HARNESS_UNTERWEGE), [],
                         'neuer Harness-Weg – in HARNESS_WEGE eintragen und, wenn er schreibt, in ROUTEN_HARNESS einordnen')
        self.assertEqual(sorted((fk.HARNESS_WEGE | fk.HARNESS_UNTERWEGE) - worte), [], 'Eintrag ohne Weg')

    def test_geschuetzte_harness_wege_sind_eingeordnet(self):
        """Jeder Weg, den S7 schützt (GESCHUETZT), hat einen Eintrag in ROUTEN_HARNESS – oder schreibt heute nicht."""
        geschuetzt = set(re.findall(r'[a-z_]{3,}', harness_api.GESCHUETZT.pattern)) - {'api', 'harness'} - fk.HARNESS_UNTERWEGE
        eingeordnet = {k.split(' ', 1)[1].split('/')[0] for k in fk.ROUTEN_HARNESS}
        fehlend = sorted(geschuetzt - eingeordnet - set(fk.HARNESS_GESCHUETZT_OHNE_SCHREIBEN))
        self.assertEqual(fehlend, [])

    def test_externe_clients_erreichen_keine_freigabe(self):
        from guppi_runtime import uix_clients
        for route in uix_clients.ROUTEN_JE_CLIENT['mcp']:               # MCP = Zugang der Modelle: nie eine Freigabe
            self.assertNotIn(fk.ROUTEN_SERVER[route][0], ('freigabe', 'anwenden'), route)
        self.assertEqual(set(uix_clients.ROUTEN_JE_CLIENT['cli']) - set(uix_clients.ROUTES), set(uix_clients.NUR_KONSOLE))

    def test_befund_n6_handlungen_ohne_gate_mit_klasse_h(self):
        """Befund N6 (G11): diese Routen tun ohne Gate etwas mit Wirkungen der Klasse H. G9 deckt sie nicht (es kennt nur Entscheidungen);
        der Captain entscheidet, ob sie eine Tür bekommen. Ändert sich die Liste, ist das eine bewusste Änderung dieses Tests."""
        self.assertEqual(list(fk.BEFUNDE_OHNE_GATE), [])                 # E12: alle vier liegen seit G9 hinter der Tür


class Entscheidungsarten(unittest.TestCase):
    """G11-03: jede Entscheidungsart und jeder Weg hat eine Klasse."""

    def test_antragsarten(self):
        for art in desk_decisions.REQUEST_TITLE:
            self.assertIn('request:' + art, fk.ARTEN, art)
        for art in desk_decisions.APPLY:
            self.assertIn('request:' + art, fk.ARTEN, art)

    def test_antragsarten_aus_dem_code(self):
        """Arten, die der Server (`_remember('…')`) und die Desk-Gates (`KIND… = '…'`, register_applier) anlegen."""
        server = re.findall(r"_remember\('([a-z_]+)'", (PAKET / 'uix_server.py').read_text(encoding='utf-8'))
        self.assertGreater(len(server), 5)
        kinds = []
        for datei in ('desk/orchestra_kinds.py', 'wissen/desk_wissen.py', 'harness/antraege.py'):
            text = (PAKET / datei).read_text(encoding='utf-8')
            for name in re.findall(r'register_applier\((\w+)', text):
                m = re.search(rf'^{name}\s*=\s*["\']([a-z_]+)["\']', text, re.M)
                self.assertIsNotNone(m, f'{datei}: {name}')
                kinds.append(m.group(1))
        self.assertGreater(len(kinds), 5)
        for art in set(server) | set(kinds):
            self.assertIn('request:' + art, fk.ARTEN, art)

    def test_weitere_arten(self):
        quelle = (PAKET / 'desk' / 'decisions.py').read_text(encoding='utf-8')
        feste = set(re.findall(r"'kind':\s*'([a-z_]+)'", quelle)) | set(desk_decisions.SCHEDULER_NOTE)
        feste |= set(re.findall(r"'(harness_[a-z]+)'\s+if", quelle)) | set(re.findall(r"else\s+'(harness_[a-z]+)'", quelle))
        for art in feste:
            self.assertIn(art, fk.ARTEN, art)
        for art in ('gate', 'boundary', 'content', 'cloud_offload', 'slot_server', 'harness_freigabe', 'harness_aufgabe'):
            self.assertIn(art, feste | {'gate'}, art)

    def test_wege(self):
        for weg in desk_decisions.WAYS:
            self.assertIn(weg, fk.WEGE, weg)
        for weg in ('erlauben', 'sitzung', 'ablehnen'):                 # Harness-Karte (harness/freigabe.beantworten)
            self.assertIn(weg, fk.WEGE, weg)


class AntwortOhneGuard(unittest.TestCase):
    """G11-04: Grenzüberschreitung, Scheduler und Inhaltsschutz erteilen ohne guard.approve – erreichbar nur aus decide."""

    def test_nur_aus_decide(self):
        aufrufe = _aufrufe({'_answer_crossing', '_answer_scheduler', 'answer'})
        for datei, fn, aufruf, zeile in aufrufe:
            if aufruf.endswith('_answer_crossing') or aufruf.endswith('_answer_scheduler') or 'content_guard' in aufruf:
                self.assertEqual((datei, fn), ('uix_server.py', '_decide_jetzt'), f'{datei}:{zeile} {aufruf} in {fn}')
        gesehen = {a.rsplit('.', 1)[-1] if 'content_guard' not in a else 'content_guard.answer' for d, f, a, z in aufrufe if f == '_decide_jetzt'}
        # G9: _decide_jetzt wird nur aus decide gerufen – hinter der Tür oder für die Harness, die ihre eigene Tür hat
        rufer = {(d, fn) for d, fn, a, z in _aufrufe({'_decide_jetzt'})}
        self.assertEqual(rufer, {('uix_server.py', 'decide')})
        self.assertTrue({'_answer_crossing', '_answer_scheduler', 'content_guard.answer'} <= gesehen)
        self.assertEqual(set(fk.ANTWORT_OHNE_GUARD), {'_answer_crossing', '_answer_scheduler', 'content_guard.answer'})


if __name__ == '__main__':
    unittest.main()
