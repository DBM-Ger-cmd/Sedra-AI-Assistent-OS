"""Belohnungssystem (05.11.2026): Lobwoerter nach einer Antwort merken die gute Antwort – Erkennung, Bezug auf die richtige Antwort, Loesung bei Code, Tagesdatei und Index fuer die Wissensdatenbank,
Uebersicht, Eintrag in der Sitzung; nichts davon darf die Nachricht aufhalten."""
import json
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.core.guard import Guard
from sedra_runtime.harness import belohnung as bl
from sedra_runtime.harness import katalog, schleife, vorlagen
from sedra_runtime.harness.freigabe import Karten, Kiste
from sedra_runtime.harness.werkzeuge import Werkzeuge
from sedra_runtime.uix_server import UIXHub

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'SEDRA_Architecture_v1.20_SELF_DEVELOPMENT'
EINST = bl.einstellungen()


def antwort(i='A-1', text='Hier ist die Lösung.', ende='antwort'):
    return {'typ': 'modell', 'antwort_id': i, 'text': text, 'ende': ende}


def captain(text='Mach das bitte.'):
    return {'typ': 'captain', 'text': text}


class Erkennen(unittest.TestCase):
    def test_lob_und_stufe(self):
        for text, erwartet in (('Danke!', ('danke', 1)), ('das hast du gut gemacht', ('das hast du gut gemacht', 1)), ('Vielen Dank, super', ('vielen dank', 1)),
                               ('Perfekt, danke', ('perfekt', 2)), ('genau so, danke dir', ('genau so', 2)), ('SUPER.', ('super', 1))):
            self.assertEqual(bl.erkennen(text, EINST), erwartet, text)

    def test_kein_lob(self):
        for text in ('nicht gut gemacht', 'kein danke nötig', 'das war nicht perfekt', 'dankbar', 'Superman', 'ok', '', '   ', 'Danke, jetzt mach noch X. ' * 30):
            self.assertIsNone(bl.erkennen(text, EINST), text[:40])
        self.assertIsNone(bl.erkennen(None, EINST))

    def test_eigene_woerter_aus_local_config(self):
        p = Path(tempfile.mkdtemp())
        (p / 'local_config').mkdir()
        (p / 'local_config' / 'belohnung.yaml').write_text('belohnung:\n  lob_zusaetzlich: [bravo]\n  besonders_zusaetzlich: [meisterhaft]\n', encoding='utf-8')
        e = bl.einstellungen(p)
        self.assertEqual(bl.erkennen('Bravo!', e), ('bravo', 1))
        self.assertEqual(bl.erkennen('meisterhaft', e), ('meisterhaft', 2), 'ein besonders-Wort ist auch ein Lobwort')
        (p / 'local_config' / 'belohnung.yaml').write_text('belohnung:\n  lob: [klasse]\n', encoding='utf-8')
        e = bl.einstellungen(p)
        self.assertIsNone(bl.erkennen('danke', e), '`lob` ersetzt die Liste des Pakets')
        self.assertEqual(bl.erkennen('Klasse', e), ('klasse', 1))


class Bezug(unittest.TestCase):
    def test_nur_die_antwort_direkt_vor_der_nachricht(self):
        a, f = bl.gelobte_antwort([captain('Frage 1'), antwort('A-1', 'Antwort 1')])
        self.assertEqual((a['antwort_id'], f['text']), ('A-1', 'Frage 1'))
        self.assertEqual(bl.gelobte_antwort([antwort('A-1'), captain('noch eine Frage')]), (None, None), 'eine Frage dazwischen: kein Lob für die ältere Antwort')
        self.assertEqual(bl.gelobte_antwort([captain('x')]), (None, None))
        self.assertEqual(bl.gelobte_antwort([]), (None, None))

    def test_nicht_zu_ende_gekommene_und_schon_gelobte_antworten(self):
        for ende in bl.KEIN_LOB_ENDE:
            self.assertEqual(bl.gelobte_antwort([captain(), antwort(ende=ende)]), (None, None), ende)
        self.assertEqual(bl.gelobte_antwort([captain(), antwort('A-1'), {'typ': 'belohnung', 'antwort_id': 'A-1'}]), (None, None), 'jede Antwort höchstens einmal')
        self.assertEqual(bl.gelobte_antwort([captain(), antwort('A-1', text='')]), (None, None), 'eine leere Antwort gibt es nicht zu loben')

    def test_loesung_nennt_dateien_befehle_und_nur_was_gelang(self):
        eintraege = [{'typ': 'werkzeug', 'antwort_id': 'A-1', 'name': 'datei_aendern', 'args': {'pfad': 'src/a.py'}, 'status': 'ok'},
                     {'typ': 'werkzeug', 'antwort_id': 'A-1', 'name': 'datei_aendern', 'args': {'pfad': 'src/a.py'}, 'status': 'ok'},
                     {'typ': 'werkzeug', 'antwort_id': 'A-1', 'name': 'datei_schreiben', 'args': {'pfad': 'tests/t.py'}, 'status': 'ok'},
                     {'typ': 'werkzeug', 'antwort_id': 'A-1', 'name': 'befehl', 'args': {'befehl': 'python -m pytest tests'}, 'status': 'ok'},
                     {'typ': 'werkzeug', 'antwort_id': 'A-1', 'name': 'datei_aendern', 'args': {'pfad': 'nie.py'}, 'status': 'fehler'},
                     {'typ': 'werkzeug', 'antwort_id': 'A-2', 'name': 'datei_aendern', 'args': {'pfad': 'andere.py'}, 'status': 'ok'}]
        t = bl.loesung(eintraege, 'A-1')
        self.assertEqual((t['dateien'], t['befehle'], t['code']), (['src/a.py', 'tests/t.py'], ['python -m pytest tests'], True))
        self.assertEqual(t['werkzeuge'], {'datei_aendern': 2, 'datei_schreiben': 1, 'befehl': 1})
        self.assertFalse(bl.loesung([], 'A-1')['code'])


class Ablage(unittest.TestCase):
    def test_tagesdatei_index_und_uebersicht(self):
        p = tempfile.mkdtemp()
        a = antwort('A-1', 'Die Lösung steht in a.py.')
        satz = bl.vermerken(p, 'perfekt', a, captain('Wie löse ich das?'), sitzung_id='S-1', titel='Fehler beheben', vorlage='bauagent', modell='qwen', stufe=2,
                            tat={'dateien': ['src/a.py'], 'befehle': ['pytest'], 'werkzeuge': {'datei_aendern': 1}, 'code': True}, zeit='2026-11-05T08:30:00')
        bl.vermerken(p, 'danke', antwort('A-2', 'Erklärung.'), captain('Was ist X?'), sitzung_id='S-2', vorlage=None, modell='qwen', zeit='2026-11-05T09:00:00')
        self.assertEqual((satz['stufe'], satz['art']), (2, 'code'))
        text = (bl.ordner(p) / '2026-11-05.md').read_text(encoding='utf-8')
        self.assertEqual(text.count('# Gute und korrigierte Antworten'), 1)
        for teil in ('## 08:30 Besonders gute Antwort „perfekt“', 'Frage: Wie löse ich das?', 'Gelöst in Dateien: src/a.py', 'Befehle und Läufe: pytest', 'datei_aendern×1', '## 09:00 Gute Antwort „danke“'):
            self.assertIn(teil, text)
        u = bl.uebersicht(p)
        self.assertEqual((u['anzahl'], u['besonders'], u['code']), (2, 1, 1))
        self.assertEqual(u['je_modell'], [{'name': 'qwen', 'anzahl': 2}])
        self.assertEqual([x['name'] for x in u['je_vorlage']], ['bauagent', '–'])
        self.assertEqual(u['letzte'][0]['antwort_id'], 'A-2', 'die neueste zuerst')
        self.assertEqual(bl.uebersicht(tempfile.mkdtemp())['anzahl'], 0)

    def test_lange_texte_werden_gekuerzt(self):
        p = tempfile.mkdtemp()
        s = bl.vermerken(p, 'danke', antwort('A-1', 'x ' * 2000), captain('y ' * 500), sitzung_id='S-1')
        self.assertLessEqual((len(s['frage']), len(s['antwort'])), (bl.FRAGE_MAX, bl.ANTWORT_MAX))


class Korrektur(unittest.TestCase):
    """L2: die Korrektur als Gegenstueck zum Lob – gleiche Regeln, die Worte des Captains sind die Lehre."""

    def test_erkennen_und_vorrang_vor_dem_lob(self):
        for text, erwartet in (('das stimmt nicht', ('korrektur', 'das stimmt nicht', 0)), ('Danke, aber das ist falsch', ('korrektur', 'das ist falsch', 0)),
                               ('so nicht bitte', ('korrektur', 'so nicht', 0)), ('nicht gut gemacht', ('korrektur', 'nicht gut gemacht', 0)), ('Danke!', ('lob', 'danke', 1)),
                               ('Perfekt', ('lob', 'perfekt', 2))):
            self.assertEqual(bl.urteil(text, EINST), erwartet, text)
        for text in ('nicht falsch', 'ok', 'Warum ist das falsch? ' * 20, 'Fehler beheben bitte'):
            self.assertIsNone(bl.urteil(text, EINST), text[:30])

    def test_eigene_korrekturwoerter(self):
        p = Path(tempfile.mkdtemp())
        (p / 'local_config').mkdir()
        (p / 'local_config' / 'belohnung.yaml').write_text('belohnung:\n  korrektur_zusaetzlich: [mist]\n', encoding='utf-8')
        self.assertEqual(bl.urteil('Das ist Mist', bl.einstellungen(p)), ('korrektur', 'mist', 0))

    def test_eine_korrektur_trifft_auch_eine_fehlerhafte_antwort_ein_lob_nicht(self):
        fehlerhaft = [captain('Frage'), antwort('A-1', 'halb fertig', ende='fehler')]
        self.assertEqual(bl.gelobte_antwort(fehlerhaft), (None, None))
        a, f = bl.gelobte_antwort(fehlerhaft, streng=False)
        self.assertEqual(a['antwort_id'], 'A-1')

    def test_ablage_mit_den_worten_des_captains(self):
        p = tempfile.mkdtemp()
        satz = bl.vermerken(p, 'das stimmt nicht', antwort('A-1', 'Falsche Lösung in a.py.'), captain('Behebe den Fehler.'), sitzung_id='S-1', vorlage='bauagent', modell='qwen',
                            art_urteil='korrektur', korrektur_text='Das stimmt nicht, der Fehler liegt in b.py.', tat={'dateien': ['a.py'], 'code': True}, zeit='2026-11-05T10:00:00')
        self.assertEqual((satz['urteil'], satz['stufe'], satz['korrektur']), ('korrektur', 0, 'Das stimmt nicht, der Fehler liegt in b.py.'))
        text = (bl.ordner(p) / '2026-11-05.md').read_text(encoding='utf-8')
        for teil in ('## 10:00 Korrigierte Antwort „das stimmt nicht“', 'Korrektur des Captains: Das stimmt nicht, der Fehler liegt in b.py.', 'Betroffen in Dateien: a.py'):
            self.assertIn(teil, text)
        bl.vermerken(p, 'danke', antwort('A-2'), captain(), sitzung_id='S-1')
        u = bl.uebersicht(p)
        self.assertEqual((u['anzahl'], u['korrekturen'], len(u['letzte_korrekturen'])), (1, 1, 1), 'Lob und Korrektur werden getrennt gezaehlt')


class Lesen(unittest.TestCase):
    """L3: der Rueckblick liest die Fakten – gefiltert nach Zeit, Art und Stichworten."""

    def setUp(self):
        self.p = tempfile.mkdtemp()
        jetzt = bl.time.strftime('%Y-%m-%dT%H:%M:%S', bl.time.gmtime())
        alt = bl.time.strftime('%Y-%m-%dT%H:%M:%S', bl.time.gmtime(bl.time.time() - 30 * 86400))
        bl.vermerken(self.p, 'danke', antwort('A-1', 'Loesung fuer den Parser'), captain('Parser reparieren'), sitzung_id='S-1', zeit=alt)
        bl.vermerken(self.p, 'perfekt', antwort('A-2', 'Test geschrieben'), captain('Tests fuer den Login'), sitzung_id='S-2', stufe=2, tat={'dateien': ['tests/test_login.py'], 'code': True}, zeit=jetzt)
        bl.vermerken(self.p, 'falsch', antwort('A-3', 'Falsch geraten'), captain('Login Fehler'), sitzung_id='S-3', art_urteil='korrektur', korrektur_text='Nein, der Fehler liegt im Cache.', zeit=jetzt)

    def test_filter(self):
        self.assertEqual([x['antwort_id'] for x in bl.lesen(self.p, tage=7)], ['A-3', 'A-2'], 'die neuesten zuerst, Aelteres faellt weg')
        self.assertEqual([x['antwort_id'] for x in bl.lesen(self.p, tage=365)], ['A-3', 'A-2', 'A-1'])
        self.assertEqual([x['antwort_id'] for x in bl.lesen(self.p, tage=365, art='korrektur')], ['A-3'])
        self.assertEqual([x['antwort_id'] for x in bl.lesen(self.p, tage=365, art='lob')], ['A-2', 'A-1'])
        self.assertEqual([x['antwort_id'] for x in bl.lesen(self.p, tage=365, suche='login test')], ['A-2'], 'alle Stichworte muessen vorkommen (auch Dateien zaehlen)')
        self.assertEqual([x['antwort_id'] for x in bl.lesen(self.p, tage=365, suche='cache')], ['A-3'], 'auch die Worte des Captains')
        self.assertEqual(len(bl.lesen(self.p, tage=365, limit=1)), 1)
        self.assertEqual(bl.lesen(tempfile.mkdtemp()), [])

    def test_zeile_fuer_das_modell(self):
        z = bl.zeile(bl.lesen(self.p, art='korrektur')[0])
        for teil in ('⚑ korrigiert', 'Frage: Login Fehler', 'Korrektur des Captains: Nein, der Fehler liegt im Cache.'):
            self.assertIn(teil, z)
        self.assertIn('★★ besonders gut', bl.zeile(bl.lesen(self.p, art='lob')[0]))
        self.assertIn('Dateien: tests/test_login.py', bl.zeile(bl.lesen(self.p, art='lob')[0]))

    def kiste(self, lesen):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        root = Path(t.name) / 'p'
        root.mkdir()
        guard = Guard(ARCH / 'core' / 'guard' / 'guard_rules.yaml', None, Path(t.name) / 'tokens.json')
        regeln = katalog.laden(Path('gibt-es-nicht'))['regeln']
        w = Werkzeuge({'id': 'p', 'name': 'P', 'wurzel': str(root), 'schreibbereich': []}, guard=guard, mission_id='M-L', regeln=regeln, lernen_lesen=lesen)
        return Kiste(w, regeln=regeln, guard=guard, audit=None, karten=Karten(Path(t.name) / 'k'), sitzung_id='S-00000001')

    def test_chat_werkzeug_ohne_karte_nur_lesen(self):
        gesehen = []

        def lesen(tage, art, suche, limit):
            gesehen.append((tage, art, suche, limit))
            return 'Treffer'
        k = self.kiste(lesen)
        r = k.aufruf('belohnungen_lesen', {'tage': 30, 'art': 'korrektur', 'suche': 'login', 'limit': 5})
        self.assertEqual((r['status'], r['ergebnis'], r['wirkung']), ('ok', 'Treffer', False))
        k.aufruf('belohnungen_lesen', {'art': 'quatsch'})
        self.assertEqual(gesehen, [(30, 'korrektur', 'login', 5), (7, 'alle', '', 20)], 'Vorgaben und ungueltige Art werden aufgefangen')
        self.assertIn('nicht_verfuegbar', self.kiste(None).aufruf('belohnungen_lesen', {})['ergebnis'])
        self.assertIn('belohnungen_lesen', katalog.OHNE_KARTE)


class Regeln(unittest.TestCase):
    """L4: die gelernten Regeln (docs/AAR/LESSONS.md) stehen im Systemprompt – kurz und nur, wenn es sie gibt."""

    def projekt(self, text):
        p = Path(tempfile.mkdtemp())
        if text is not None:
            (p / 'docs' / 'AAR').mkdir(parents=True)
            (p / 'docs' / 'AAR' / 'LESSONS.md').write_text(text, encoding='utf-8')
        return p

    def test_lessons_lesen_und_begrenzen(self):
        self.assertEqual(bl.lessons(self.projekt(None)), '')
        self.assertEqual(bl.lessons(None), '')
        zeilen = '\n'.join('- 2026-11-05: Regel %d (Quelle: AAR-1)' % i for i in range(40))
        t = bl.lessons(self.projekt('# Gelernte Regeln\n\n' + zeilen + '\n'))
        self.assertEqual((len(t.splitlines()), t.splitlines()[0], t.splitlines()[-1][:25]), (25, '- 2026-11-05: Regel 15 (Quelle: AAR-1)', '- 2026-11-05: Regel 39 (Q'), 'die neuesten 25, ohne Ueberschrift')
        self.assertLessEqual(len(bl.lessons(self.projekt('- ' + 'x' * 5000))), bl.LESSONS_ZEICHEN)

    def test_system_prompt_mit_und_ohne_regeln(self):
        ohne = schleife.system_prompt('P', [], None, None, '2026-11-05')
        mit = schleife.system_prompt('P', [], None, None, '2026-11-05', '- Regel eins\n- Regel zwei')
        self.assertNotIn('Gelernte Regeln', ohne)
        self.assertTrue(mit.startswith(ohne), 'die Regeln kommen dazu, der Rest bleibt wie er war')
        self.assertIn('Gelernte Regeln dieses Projekts', mit)
        self.assertIn('- Regel zwei', mit)
        vorlage = schleife.system_prompt('P', [], 'Du bist X.', 'Fruehere Notiz', None, '- Regel eins')
        self.assertLess(vorlage.index('Gelernte Regeln'), vorlage.index('Fruehere Notiz'), 'die Zusammenfassung steht weiter ganz am Ende')
        self.assertEqual(schleife.system_prompt('P', [], None, None, None, '   '), schleife.system_prompt('P', [], None, None, None), 'leere Regeln aendern nichts')

    def test_vorlage_rueckblick_nach_dem_hermes_muster(self):
        v = vorlagen.laden(Path(tempfile.mkdtemp()), 'rueckblick')
        self.assertEqual(v['rechte'], {'vorarbeiter_freigabe': False, 'aufgaben_vorschlagen': False})
        self.assertIn('belohnungen_lesen', v['werkzeuge'])
        for satz in ('vier Fragen', 'Fakten sammeln, nicht erinnern', 'höchstens 30 Zeilen', 'docs/AAR/LESSONS.md', 'wartest auf sein Ja', 'höchstens 25 Zeilen', 'Erfinde nichts'):
            self.assertIn(satz, v['system'])
        for vid in ('bauagent', 'desktop-designer', 'masterchat'):
            self.assertIn('belohnungen_lesen', vorlagen.laden(Path(tempfile.mkdtemp()), vid)['werkzeuge'], vid)


class Vorschlaege(unittest.TestCase):
    """Vorhersagen beim Tippen (05.11.2026): Vorschlaege aus gelobten Fragen, Warnung aus korrigierten, nur lokal und nur wenn es passt."""

    def setUp(self):
        self.p = tempfile.mkdtemp()
        bl.vermerken(self.p, 'perfekt', antwort('A-1'), captain('Tests für den Login schreiben'), sitzung_id='S1', vorlage='bauagent', stufe=2, tat={'dateien': ['tests/test_login.py', 'src/login.py'], 'code': True}, zeit='2026-11-01T10:00:00')
        bl.vermerken(self.p, 'danke', antwort('A-2'), captain('Tests für den Parser schreiben'), sitzung_id='S1', vorlage='modellierer', zeit='2026-11-02T10:00:00')
        bl.vermerken(self.p, 'danke', antwort('A-3'), captain('Dokumentation zum Start schreiben'), sitzung_id='S1', zeit='2026-11-03T10:00:00')
        bl.vermerken(self.p, 'falsch', antwort('A-4'), captain('Login Cache leeren und testen'), sitzung_id='S1', art_urteil='korrektur', korrektur_text='Nein, nicht den Cache, die Session.', zeit='2026-11-04T10:00:00')

    def fragen(self, text, vorlage=None):
        return [v['frage'] for v in bl.vorschlaege(self.p, text, vorlage)['vorschlaege']]

    def test_anfang_und_stichworte_passen(self):
        self.assertEqual(self.fragen('Tests f', 'bauagent')[0], 'Tests für den Login schreiben', 'Anfang, ★★ und die gleiche Vorlage gewinnen')
        self.assertEqual(self.fragen('Tests f', 'modellierer')[0], 'Tests für den Parser schreiben', 'die Vorlage des Captains zaehlt')
        self.assertEqual(self.fragen('Dokumentation'), ['Dokumentation zum Start schreiben'])
        self.assertEqual(self.fragen('schreiben Login'), ['Tests für den Login schreiben'], 'Stichworte in beliebiger Reihenfolge')
        r = bl.vorschlaege(self.p, 'Tests für den Login schreiben')['vorschlaege']
        self.assertEqual([v['frage'] for v in r], [], 'was schon voll getippt ist, wird nicht noch einmal vorgeschlagen, und ein Auftrag, der nur zwei von drei Stichworten teilt, passt nicht')

    def test_dateien_und_stufe_gehen_mit(self):
        v = bl.vorschlaege(self.p, 'Login Tests')['vorschlaege'][0]
        self.assertEqual((v['stufe'], v['dateien'], v['vorlage']), (2, ['tests/test_login.py', 'src/login.py'], 'bauagent'))

    def test_kein_vorschlag_bei_zu_wenig_befehlen_mehrzeilig_oder_unpassend(self):
        for text in ('Te', '/neu', 'Tests\nfür', 'Kuchen backen', '   ', ''):
            self.assertEqual(self.fragen(text), [], repr(text))
        self.assertEqual(bl.vorschlaege(self.p, 'Tests', None, {'vorschlaege': {'an': False, 'min_zeichen': 3, 'max': 5}}), {'an': False, 'vorschlaege': [], 'warnungen': []})

    def test_korrigierte_fragen_werden_zur_warnung_nie_zum_vorschlag(self):
        r = bl.vorschlaege(self.p, 'Login Cache leeren')
        self.assertEqual([w['korrektur'] for w in r['warnungen']], ['Nein, nicht den Cache, die Session.'])
        self.assertNotIn('Login Cache leeren und testen', [v['frage'] for v in r['vorschlaege']])
        self.assertEqual(bl.vorschlaege(self.p, 'Cache')['warnungen'], [], 'ein einzelnes Stichwort reicht nicht fuer eine Warnung')

    def test_begrenzung_und_einstellung(self):
        for i in range(12):
            bl.vermerken(self.p, 'danke', antwort('B-%d' % i), captain('Aufgabe Nummer %d bearbeiten' % i), sitzung_id='S2')
        self.assertEqual(len(self.fragen('Aufgabe')), 5)
        q = Path(tempfile.mkdtemp())
        (q / 'local_config').mkdir()
        (q / 'local_config' / 'belohnung.yaml').write_text('belohnung:\n  vorschlaege: {an: false}\n', encoding='utf-8')
        self.assertFalse(bl.einstellungen(q)['vorschlaege']['an'])
        self.assertTrue(bl.einstellungen()['vorschlaege']['an'])
        self.assertEqual(bl.einstellungen()['vorschlaege']['max'], 5)

    def test_weg_und_route(self):
        from sedra_runtime.harness.api import GESCHUETZT, WEG
        self.assertIn('vorschlaege', WEG.fullmatch('/api/harness/vorschlaege').groups())
        self.assertFalse(GESCHUETZT.match('/api/harness/vorschlaege'), 'nur lesen: keine Herkunftspruefung noetig')


class AmHub(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='belohnung-')
        self.addCleanup(tmp.cleanup)
        self.projekt = Path(tmp.name) / 'project'
        (self.projekt / 'local_config').mkdir(parents=True)
        self.hub = UIXHub(self.projekt, ARCH)
        self.addCleanup(self.hub.close)
        self.api = self.hub.harness
        kopf = self.api.sitzungen.anlegen('p', titel='Fehler beheben', modell='qwen', vorlage='bauagent')
        self.sid = kopf['id']
        for e in (captain('Behebe den Fehler.'), {'typ': 'werkzeug', 'antwort_id': 'A-9', 'name': 'datei_aendern', 'args': {'pfad': 'src/a.py'}, 'status': 'ok'}, antwort('A-9', 'Erledigt.')):
            self.api.sitzungen.anhaengen(self.sid, e)

    def test_danke_nach_einer_antwort_wird_zur_guten_antwort(self):
        s = self.api.sitzungen.laden(self.sid)
        satz = self.api._belohnung_pruefen(self.sid, s, 'Perfekt, danke!')
        self.assertIsNotNone(satz)
        self.assertEqual((satz['stufe'], satz['art'], satz['vorlage'], satz['modell'], satz['tat']['dateien']), (2, 'code', 'bauagent', 'qwen', ['src/a.py']))
        eintraege = self.api.sitzungen.laden(self.sid)['eintraege']
        self.assertEqual([e['ausloeser'] for e in eintraege if e['typ'] == 'belohnung'], ['perfekt'])
        self.assertTrue((bl.ordner(self.projekt) / bl.INDEX).exists())
        self.assertIn('"HARNESS_BELOHNUNG"', self.hub.runtime.audit.path.read_text(encoding='utf-8'))
        self.assertIsNone(self.api._belohnung_pruefen(self.sid, self.api.sitzungen.laden(self.sid), 'danke nochmal'), 'dieselbe Antwort wird nicht zweimal gelobt')

    def test_kein_lob_ohne_lobwort_oder_ohne_vorherige_antwort(self):
        s = self.api.sitzungen.laden(self.sid)
        self.assertIsNone(self.api._belohnung_pruefen(self.sid, s, 'Mach bitte noch etwas'))
        kopf = self.api.sitzungen.anlegen('p', titel='leer')
        self.assertIsNone(self.api._belohnung_pruefen(kopf['id'], self.api.sitzungen.laden(kopf['id']), 'danke'))
        self.assertEqual(bl.uebersicht(self.projekt)['anzahl'], 0)

    def test_ein_fehler_beim_merken_haelt_nie_die_nachricht_auf(self):
        self.assertIsNone(self.api._belohnung_pruefen(self.sid, None, 'danke'))               # kaputte Sitzung: der Zugriff scheitert, die Methode schluckt es
        s = self.api.sitzungen.laden(self.sid)
        s['eintraege'] = [{'typ': 'modell', 'antwort_id': 'A-9', 'text': 'x', 'ende': 'antwort', 'args': 5}, 5]                 # kaputte Eintraege
        self.assertIsNone(self.api._belohnung_pruefen(self.sid, s, 'danke'))

    def test_korrektur_nach_einer_antwort_wird_gemerkt_mit_den_worten_des_captains(self):
        s = self.api.sitzungen.laden(self.sid)
        satz = self.api._belohnung_pruefen(self.sid, s, 'Das stimmt nicht, der Fehler liegt in b.py.')
        self.assertEqual((satz['urteil'], satz['korrektur'], satz['tat']['dateien']), ('korrektur', 'Das stimmt nicht, der Fehler liegt in b.py.', ['src/a.py']))
        e = [x for x in self.api.sitzungen.laden(self.sid)['eintraege'] if x['typ'] == 'belohnung']
        self.assertEqual((e[0]['urteil'], e[0]['stufe']), ('korrektur', 0))
        self.assertEqual(bl.uebersicht(self.projekt)['korrekturen'], 1)
        text = self.api.lernen_lesen(7, 'korrektur', 'b.py', 5)
        self.assertIn('⚑ korrigiert', text)
        self.assertIn('1 Korrekturen', text)
        self.assertIn('Nichts gefunden', self.api.lernen_lesen(7, 'lob', '', 5))

    def test_die_gelernten_regeln_kommen_in_den_systemprompt(self):
        wurzel = Path(tempfile.mkdtemp())
        (wurzel / 'docs' / 'AAR').mkdir(parents=True)
        (wurzel / 'docs' / 'AAR' / 'LESSONS.md').write_text('- 2026-11-05: Tests vor dem Commit laufen lassen (Quelle: AAR-1)\n', encoding='utf-8')
        self.assertIn('Tests vor dem Commit', schleife.system_prompt('P', [], None, None, None, bl.lessons(wurzel)))

    def test_route_vorschlaege_am_hub(self):
        self.api._belohnung_pruefen(self.sid, self.api.sitzungen.laden(self.sid), 'Perfekt!')
        out = self.api.handle('GET', '/api/harness/vorschlaege', 'q=Behebe+den&vorlage=bauagent')[1]
        self.assertEqual([v['frage'] for v in out['vorschlaege']], ['Behebe den Fehler.'])
        self.assertEqual(self.api.handle('GET', '/api/harness/vorschlaege', 'q=ab')[1]['vorschlaege'], [])

    def test_info_route_nennt_die_guten_antworten(self):
        self.api._belohnung_pruefen(self.sid, self.api.sitzungen.laden(self.sid), 'danke')
        out = self.api.handle('GET', '/api/harness/info', '')[1]
        self.assertEqual(out['belohnungen']['anzahl'], 1)
        self.assertIn(out['belohnungen']['wissen'], ('nicht', 'aus'))
        with self.assertRaises(ValueError):
            self.api.handle('POST', '/api/harness/info/wissen', '', {'quelle': 'unbekannt'})


if __name__ == '__main__':
    unittest.main()
