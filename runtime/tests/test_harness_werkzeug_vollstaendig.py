"""W1 (docs/ROADMAP_ONE_SEDRA_UIX_WERKZEUGE_2026-11-05.md §3, Unterchat U10): jedes Chat-Werkzeug der Harness ist vollständig eingeordnet.

Geprüft wird gegen die Listen im Code, nie gegen eine Namensliste in diesem Test – ein neues Werkzeug in `werkzeuge.NAMEN` (z. B. aus einem
parallelen Bau) wird automatisch mitgeprüft:
  1. Schema: jedes Werkzeug in NAMEN hat genau ein Schema in SCHEMAS mit demselben Namen.
  2. Einordnung: im Katalog (`katalog.WERKZEUGE`, mit oder ohne Karte) oder in der kurzen Ausnahmeliste unten (mit Grund).
  3. Zweige: `Werkzeuge.vorbereiten` und `Werkzeuge.ausfuehren` nennen jedes Werkzeug (AST) – Default-Zweige stehen mit Grund in einer
     Ausnahmeliste; zusätzlich ein Aufruf, der zeigt, dass kein Werkzeug still im Zweig eines anderen landet.
  4. Freigabeklasse: jedes Werkzeug, das eine Karte bekommen kann, steht in `desk/freigabeklasse.py` – oder in der Liste „implizit H“.
  5. Kiste (harness/freigabe.py): Wirkungsliste und Audit-Zuordnung der Werkzeuge ohne Karte passen zu den Listen in werkzeuge/katalog.
  6. Vorlagen (runtime/config/harness_vorlagen): jede genannte Werkzeug-ID gibt es in der Harness wirklich.
  7. Texte (Vorlagen-Anweisungen, Arbeitsplatz-Wissen der Harness-Shell): kein unbekanntes Werkzeug.
Nur lesen, kein Netz, kein Modell."""
import ast
import inspect
import re
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

from sedra_runtime import chat_tools
from sedra_runtime.core.guard import Guard
from sedra_runtime.desk import freigabeklasse as fk
from sedra_runtime.harness import api as harness_api
from sedra_runtime.harness import freigabe as harness_freigabe
from sedra_runtime.harness import katalog
from sedra_runtime.harness import vorarbeiter as harness_vorarbeiter
from sedra_runtime.harness import vorlagen as harness_vorlagen
from sedra_runtime.harness import werkzeuge as wz

RUNTIME = Path(__file__).resolve().parents[1]
ARCH = RUNTIME.parent / 'architecture' / 'SEDRA_Architecture_v1.20_SELF_DEVELOPMENT'
VORLAGEN = RUNTIME / 'config' / 'harness_vorlagen'
ARBEITSPLATZ = RUNTIME / 'src' / 'sedra_runtime' / 'uix' / 'shells' / 'harness' / 'arbeitsplatz.yaml'
LAEUFE = RUNTIME / 'config' / 'harness_laeufe.yaml'

# ---------------------------------------------------------------- Ausnahmelisten (jeder Eintrag mit Grund; ein veralteter Eintrag lässt den Test fehlschlagen)
# 2. Ohne Katalog-Regel: Werkzeuge, die der Katalog nicht kennt (katalog.WERKZEUGE), und warum das richtig ist.
OHNE_KATALOG_REGEL = {
    'lauf_status': 'liest nur; Kiste.aufruf führt es immer frei aus, vor jeder Einstufung (harness/freigabe.py, `if name == \'lauf_status\'`)',
    'sitzungen_aufraeumen': 'fester Vorbehalt: immer eine Karte mit der Liste (harness/vorbehalte.py); eine Katalog-Regel könnte nichts lockern',
}
# 3. Default-Zweige: Werkzeuge, die `vorbereiten` (samt Helfern) nicht beim Namen nennt, weil sie im letzten Zweig landen.
VORBEREITEN_DEFAULT = {
    'app_oeffnen': 'else-Zweig im Block FREI_OHNE_KATALOG (werkzeuge.py, Kommentar „# app_oeffnen, auch mit Verknüpfung“)',
    'datei_aendern': 'Schreibpfad am Ende von vorbereiten und else-Zweig in _fsargs',
}
AUSFUEHREN_DEFAULT = {}          # heute nennt `ausfuehren` jedes Werkzeug (direkt oder über die Gruppe LAUF)
# Gruppen, die nur den Block wählen und keinen eigenen Zweig bilden (zählen nicht als Zweig für ihre Mitglieder)
NUR_WAHL = {'NAMEN', 'FREI_OHNE_KATALOG', 'OHNE_KARTE'}
# 4. Werkzeuge mit Karte ohne eigenen Eintrag in freigabeklasse.py: sie fallen in `_harness` auf den Rest „H“.
IMPLIZIT_H = {
    'datei_lesen': 'Lesen mit Karte (Katalog: captain/vorarbeiter) – Klasse H nur durch den Rest von freigabeklasse._harness, nicht entschieden (Bericht U10, L2)',
    'dateien_auflisten': 'wie datei_lesen (L2)',
    'suchen': 'wie datei_lesen (L2)',
}
# 7. Wörter in `…` oder nach „Werkzeug“, die wie Werkzeugnamen aussehen, aber keine sind
KEIN_WERKZEUG = {
    'local_config': 'Ordner des Captains',
    'role_routing': 'Konfiguration (masterchat.md)',
    'pfad_fehlt': 'Fehlercode von datei_lesen (vorarbeiter.md)',
}


def _alle_harness_werkzeuge():
    """Was eine Harness-Sitzung je aufrufen kann: die eigenen, die des Vorarbeiters, die lesenden Zustandswerkzeuge und das Bündel `zustand`."""
    return set(wz.NAMEN) | set(harness_vorarbeiter.SCHEMAS) | set(harness_api.LESEN) | {'zustand'}


def _methode(cls, name):
    quelle = textwrap.dedent(inspect.getsource(getattr(cls, name)))
    return ast.parse(quelle)


def _genannt(baeume, modul):
    """Namen, die in `name == '…'` / `name in (…)` / `name in GRUPPE` vorkommen (GRUPPE aus `modul` aufgelöst, außer NUR_WAHL)."""
    out = set()
    for baum in baeume:
        for knoten in ast.walk(baum):
            if not (isinstance(knoten, ast.Compare) and isinstance(knoten.left, ast.Name) and knoten.left.id == 'name'):
                continue
            for op, rechts in zip(knoten.ops, knoten.comparators):
                if not isinstance(op, (ast.Eq, ast.In)):
                    continue
                if isinstance(rechts, ast.Constant) and isinstance(rechts.value, str):
                    out.add(rechts.value)
                elif isinstance(rechts, (ast.Tuple, ast.List, ast.Set)):
                    out |= {e.value for e in rechts.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)}
                elif isinstance(rechts, ast.Name) and rechts.id not in NUR_WAHL and isinstance(getattr(modul, rechts.id, None), (tuple, list, set, frozenset)):
                    out |= set(getattr(modul, rechts.id))
    return out


class SchemaTests(unittest.TestCase):
    def test_jedes_werkzeug_hat_genau_ein_schema(self):
        self.assertEqual(len(wz.NAMEN), len(set(wz.NAMEN)), 'ein Werkzeug steht doppelt in NAMEN')
        self.assertEqual(sorted(set(wz.NAMEN) - set(wz.SCHEMAS)), [], 'Werkzeug ohne Schema')
        self.assertEqual(sorted(set(wz.SCHEMAS) - set(wz.NAMEN)), [], 'Schema ohne Werkzeug in NAMEN (das Modell sähe es nie)')
        for n, s in wz.SCHEMAS.items():
            with self.subTest(werkzeug=n):
                self.assertEqual(s['type'], 'function')
                self.assertEqual(s['function']['name'], n)
                self.assertTrue(s['function']['description'].strip())
                p = s['function']['parameters']
                self.assertEqual(p['type'], 'object')
                self.assertEqual(sorted(set(p['required']) - set(p['properties'])), [], 'Pflichtfeld ohne Eigenschaft')

    def test_vorarbeiter_werkzeuge_haben_schema_und_zweig(self):
        quelle = inspect.getsource(harness_vorarbeiter.Werkzeuge.call)
        for n, s in harness_vorarbeiter.SCHEMAS.items():
            with self.subTest(werkzeug=n):
                self.assertEqual(s['function']['name'], n)
                self.assertIn(n, harness_vorarbeiter.ENTSCHEIDEN + harness_vorarbeiter.VORSCHLAGEN)
        genannt = set(re.findall(r"name == '([a-z_]+)'", quelle))
        rest = set(harness_vorarbeiter.SCHEMAS) - genannt
        self.assertLessEqual(len(rest), 1, f'höchstens ein Default-Zweig in vorarbeiter.Werkzeuge.call, nicht {sorted(rest)}')
        self.assertEqual(set(wz.NAMEN) & set(harness_vorarbeiter.SCHEMAS), set(), 'Name doppelt vergeben (Kiste fragt extra zuerst)')

    def test_zustandswerkzeuge_gibt_es(self):
        self.assertEqual(sorted(set(harness_api.LESEN) - set(chat_tools.SCHEMAS)), [], 'Zustandswerkzeug ohne Schema in chat_tools')
        self.assertEqual(set(wz.NAMEN) & set(harness_api.LESEN), set(), 'Name doppelt: Harness-Werkzeug und Zustandswerkzeug')


class EinordnungTests(unittest.TestCase):
    def test_im_katalog_oder_begruendet_ohne_regel(self):
        fehlt = sorted(set(wz.NAMEN) - set(katalog.WERKZEUGE) - set(OHNE_KATALOG_REGEL))
        self.assertEqual(fehlt, [], 'neues Werkzeug: in katalog.WERKZEUGE (oder OHNE_KARTE) eintragen – oder hier mit Grund in OHNE_KATALOG_REGEL')
        self.assertEqual(sorted(set(katalog.WERKZEUGE) - set(wz.NAMEN)), [], 'Katalog kennt ein Werkzeug, das es nicht gibt')
        self.assertEqual(sorted(set(OHNE_KATALOG_REGEL) & set(katalog.WERKZEUGE)), [], 'veraltete Ausnahme: steht inzwischen im Katalog')
        self.assertEqual(sorted(set(OHNE_KATALOG_REGEL) - set(wz.NAMEN)), [], 'veraltete Ausnahme: Werkzeug gibt es nicht mehr')

    def test_ohne_karte_sind_werkzeuge_und_frei_ohne_katalog(self):
        self.assertEqual(sorted(set(katalog.OHNE_KARTE) - set(wz.NAMEN)), [])
        self.assertEqual(tuple(wz.FREI_OHNE_KATALOG), tuple(katalog.OHNE_KARTE))
        self.assertEqual(set(katalog.OHNE_KARTE) & (set(wz.LESEN) | set(wz.WIRKUNG) | set(wz.LAUF) | set(wz.SITZUNGEN)), set(),
                         'ein Werkzeug ohne Karte steht zugleich in einer Gruppe mit Karte')

    def test_katalog_vorlage_laedt(self):
        regeln = katalog.laden(Path('fehlt'))['regeln']          # prüft jede Regel gegen katalog.WERKZEUGE
        self.assertTrue(regeln)


class ZweigTests(unittest.TestCase):
    def test_vorbereiten_nennt_jedes_werkzeug(self):
        baeume = [_methode(wz.Werkzeuge, m) for m in ('vorbereiten', '_vorbereiten_sitzungen', '_vorbereiten_lauf', '_fsargs')]
        genannt = _genannt(baeume, wz)
        fehlt = sorted(set(wz.NAMEN) - genannt - set(VORBEREITEN_DEFAULT))
        self.assertEqual(fehlt, [], 'Werkzeug ohne Zweig in vorbereiten – es fiele in den Default-Zweig eines anderen Werkzeugs')
        self.assertEqual(sorted(set(VORBEREITEN_DEFAULT) & genannt), [], 'veraltete Ausnahme: Werkzeug hat inzwischen einen eigenen Zweig')
        self.assertEqual(sorted(set(VORBEREITEN_DEFAULT) - set(wz.NAMEN)), [])

    def test_ausfuehren_nennt_jedes_werkzeug(self):
        baeume = [_methode(wz.Werkzeuge, m) for m in ('ausfuehren', '_lauf_ausfuehren')]
        genannt = _genannt(baeume, wz)
        fehlt = sorted(set(wz.NAMEN) - genannt - set(AUSFUEHREN_DEFAULT))
        self.assertEqual(fehlt, [], 'Werkzeug ohne Zweig in ausfuehren – es endet in „werkzeug_unbekannt“')
        self.assertIn('werkzeug_unbekannt', inspect.getsource(wz.Werkzeuge.ausfuehren), 'ausfuehren braucht einen Fehler als letzten Zweig')

    def test_kein_werkzeug_landet_still_im_zweig_eines_anderen(self):
        """Aufruf statt AST: mit Argumenten, die für den Schreibpfad passen, und ohne Dienste des Servers. Ein Werkzeug ohne eigenen Zweig
        landete in `app_oeffnen` (Fehler „ort“) oder im Schreibpfad (Plan mit `fsargs`) – beides gilt hier als Lücke."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'projekt'
            (root / 'docs').mkdir(parents=True)
            (root / 'docs' / 'da.md').write_text('a\n', encoding='utf-8')
            guard = Guard(ARCH / 'core' / 'guard' / 'guard_rules.yaml', None, Path(tmp) / 'tokens.json')
            w = wz.Werkzeuge({'id': 'p', 'name': 'P', 'wurzel': str(root), 'schreibbereich': ['docs/**']}, guard=guard, mission_id='M-W1',
                             regeln=katalog.laden(Path('fehlt'))['regeln'])
            args = {'pfad': 'docs/da.md', 'inhalt': 'b\n', 'alt': 'a', 'neu': 'b'}
            for n in wz.NAMEN:
                with self.subTest(werkzeug=n):
                    try:
                        plan, fehler = w.vorbereiten(n, dict(args)), ''
                    except Exception as exc:                          # WerkzeugFehler, BefehlFehler … – nur der Text zählt
                        plan, fehler = None, str(exc)
                    if n != 'app_oeffnen':
                        self.assertNotEqual(fehler, 'argument_fehlt: ort', f'{n} landet im Zweig von app_oeffnen')
                        self.assertFalse(fehler.startswith('ort_unbekannt'), f'{n} landet im Zweig von app_oeffnen: {fehler}')
                    if n not in ('datei_schreiben', 'datei_aendern'):
                        self.assertFalse(plan and 'fsargs' in plan, f'{n} landet im Schreibpfad')
                        self.assertNotIn('datei_aendern ändert nur', fehler, f'{n} landet im Schreibpfad')
                    else:
                        self.assertIn('fsargs', plan)


class FreigabeklasseTests(unittest.TestCase):
    def test_werkzeuge_mit_karte_sind_eingeordnet(self):
        """Eine Karte (harness_freigabe) entsteht für alles außer OHNE_KARTE und lauf_status (Kiste.aufruf). Jedes solche Werkzeug steht in
        einer Menge von freigabeklasse.py – oder bewusst in IMPLIZIT_H (der Rest von `_harness` ist H)."""
        mit_karte = set(wz.NAMEN) - set(katalog.OHNE_KARTE) - {'lauf_status'}
        eingeordnet = set(fk.HARNESS_AUSFUEHREN) | set(fk.HARNESS_SCHREIBEN) | set(fk.HARNESS_N)
        fehlt = sorted(mit_karte - eingeordnet - set(IMPLIZIT_H))
        self.assertEqual(fehlt, [], 'Werkzeug mit Karte ohne Klasse – in desk/freigabeklasse.py einordnen (H oder N, mit Captain)')
        self.assertEqual(sorted(eingeordnet - set(wz.NAMEN)), [], 'freigabeklasse.py nennt ein Werkzeug, das es nicht gibt')
        self.assertEqual(sorted(eingeordnet & set(katalog.OHNE_KARTE)), [], 'ohne Karte gibt es keine Freigabe, also keine Klasse')
        self.assertEqual(sorted(set(IMPLIZIT_H) & eingeordnet), [], 'veraltete Ausnahme: inzwischen eingeordnet')
        self.assertEqual(sorted(set(IMPLIZIT_H) - mit_karte), [])
        for n in IMPLIZIT_H:
            self.assertEqual(fk.klasse('harness_freigabe', 'erlauben', {'werkzeug': n, 'ziel': 'docs/a.md'}), fk.H)

    def test_sitzungs_erlaubnis_nur_fuer_werkzeuge_mit_karte(self):
        self.assertEqual(sorted(set(harness_vorlagen.ERLAUBNIS_WERKZEUGE) - set(wz.NAMEN)), [])
        self.assertEqual(sorted(set(harness_vorlagen.ERLAUBNIS_WERKZEUGE) & set(katalog.OHNE_KARTE)), [])


class KisteTests(unittest.TestCase):
    """Zwei Listen in harness/freigabe.py stehen als Literal im Code – sie müssen zu werkzeuge/katalog passen."""

    def _baum(self):
        return ast.parse(textwrap.dedent(inspect.getsource(harness_freigabe.Kiste)))

    def test_wirkung_sind_die_werkzeuge_mit_karte_ausser_lesen(self):
        wirkung = None
        for k in ast.walk(self._baum()):
            if isinstance(k, ast.Assign) and any(isinstance(t, ast.Attribute) and t.attr == 'wirkung' for t in k.targets):
                wirkung = {e.value for e in k.value.elts}
        self.assertIsNotNone(wirkung, 'Kiste.wirkung nicht gefunden')
        erwartet = set(wz.NAMEN) - set(katalog.OHNE_KARTE) - {'lauf_status'} - set(wz.LESEN)
        self.assertEqual(sorted(wirkung ^ erwartet), [], 'Kiste.wirkung (harness/freigabe.py) passt nicht zu den Werkzeugen mit Wirkung')

    def test_audit_der_werkzeuge_ohne_karte(self):
        """Kiste.aufruf schreibt für OHNE_KARTE-Werkzeuge außerhalb einer Literal-Liste HARNESS_APP_OEFFNEN oder HARNESS_PROJEKT_BEANTRAGT.
        Ein neues Werkzeug ohne Karte, das dort fehlt, hinterließe ein falsches Audit („Projekt beantragt“)."""
        ohne_audit = None
        for k in ast.walk(self._baum()):
            if isinstance(k, ast.Compare) and isinstance(k.left, ast.Name) and k.left.id == 'name' and isinstance(k.ops[0], ast.NotIn) \
                    and isinstance(k.comparators[0], ast.Tuple) and 'erinnern' in {getattr(e, 'value', None) for e in k.comparators[0].elts}:
                ohne_audit = {e.value for e in k.comparators[0].elts}
        self.assertIsNotNone(ohne_audit, 'Audit-Liste in Kiste.aufruf nicht gefunden')
        mit_audit = {'app_oeffnen', 'projekt_beantragen'}            # HARNESS_APP_OEFFNEN bzw. HARNESS_PROJEKT_BEANTRAGT
        self.assertEqual(sorted(set(katalog.OHNE_KARTE) - ohne_audit - mit_audit), [],
                         'Werkzeug ohne Karte bekäme das Audit HARNESS_PROJEKT_BEANTRAGT – in die Liste in Kiste.aufruf aufnehmen')
        self.assertEqual(sorted(ohne_audit - set(katalog.OHNE_KARTE)), [])


class VorlagenTests(unittest.TestCase):
    def _vorlagen(self):
        for f in sorted(VORLAGEN.glob('*.yaml')):
            yield f, yaml.safe_load(f.read_text(encoding='utf-8'))['harness_vorlage']

    def test_vorlagen_nennen_nur_vorhandene_werkzeuge(self):
        alle = _alle_harness_werkzeuge()
        n = 0
        for f, v in self._vorlagen():
            n += 1
            with self.subTest(vorlage=f.name):
                self.assertEqual(sorted(set(v['werkzeuge']) - alle), [], 'Vorlage nennt ein Werkzeug, das die Harness nicht anbietet')
                for e in v.get('erlaubnisse') or []:
                    self.assertIn(e['werkzeug'], v['werkzeuge'])
        self.assertGreaterEqual(n, 1)

    def test_vorgesehen_gibt_es_inzwischen(self):
        """vorlagen.VORGESEHEN waren Platzhalter für Stufe 3; heute muss es jedes geben (sonst ließe eine Vorlage ein Phantom zu)."""
        self.assertEqual(sorted(set(harness_vorlagen.VORGESEHEN) - _alle_harness_werkzeuge()), [])

    def test_bekannte_werkzeuge_der_vorlagen(self):
        """Was vorlagen.bekannte_werkzeuge() erlaubt, aber die Harness nie anbietet (chat_tools außerhalb von api.LESEN): nur melden, wenn eine Vorlage es nennt."""
        phantom = set(harness_vorlagen.bekannte_werkzeuge()) - _alle_harness_werkzeuge()
        for f, v in self._vorlagen():
            with self.subTest(vorlage=f.name):
                self.assertEqual(sorted(set(v['werkzeuge']) & phantom), [])


TOKEN = re.compile(r'`([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\b[^`]*`|[Ww]erkzeug(?:e|s)?\s+`?([a-z][a-z0-9]*(?:_[a-z0-9]+)+)')


class TexteTests(unittest.TestCase):
    """Anweisungen der Vorlagen und Arbeitsplatz-Wissen: Wörter in `…` oder nach „Werkzeug“, die wie Werkzeugnamen aussehen."""

    def _erlaubt(self):
        props = set()
        for s in list(wz.SCHEMAS.values()) + list(harness_vorarbeiter.SCHEMAS.values()) + list(chat_tools.SCHEMAS.values()):
            props |= set(s['function']['parameters'].get('properties', {}))
        laeufe = {l['id'] for l in yaml.safe_load(LAEUFE.read_text(encoding='utf-8'))['harness_laeufe']['laeufe']}
        return _alle_harness_werkzeuge() | props | laeufe | set(KEIN_WERKZEUG)

    def _pruefen(self, pfad):
        erlaubt = self._erlaubt()
        woerter = {a or b for a, b in TOKEN.findall(pfad.read_text(encoding='utf-8'))}
        return sorted(w for w in woerter - erlaubt if not w.startswith('test_'))      # Testdateien nennt desktop-designer.md als Nachweis

    def test_vorlagen_anweisungen(self):
        for f in sorted(VORLAGEN.glob('*.md')):
            with self.subTest(datei=f.name):
                self.assertEqual(self._pruefen(f), [], 'unbekanntes Werkzeug im Text – oder in KEIN_WERKZEUG mit Grund eintragen')

    def test_arbeitsplatz_wissen_der_harness(self):
        self.assertTrue(ARBEITSPLATZ.is_file())
        self.assertEqual(self._pruefen(ARBEITSPLATZ), [])

    def test_ausnahmen_werden_gebraucht(self):
        texte = ''.join(p.read_text(encoding='utf-8') for p in list(VORLAGEN.glob('*.md')) + [ARBEITSPLATZ])
        self.assertEqual(sorted(w for w in KEIN_WERKZEUG if w not in texte), [], 'veraltete Ausnahme in KEIN_WERKZEUG')


if __name__ == '__main__':
    unittest.main()
