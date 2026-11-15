"""Delegation im Gespräch, der Ablauf (harness/team_lauf.py, SPEC_DELEGATION_IM_GESPRAECH_v1 T3/T5) – mit einem Schein-Server:
echte Sitzungen, Ströme und Karten in einem Temp-Ordner, das „Modell“ je Helfer ist eine kleine Funktion in einem Faden."""
import tempfile
import threading
import time
import unittest
from pathlib import Path

from sedra_runtime.harness import team
from sedra_runtime.harness.freigabe import Karten
from sedra_runtime.harness.sitzung import Sitzungen
from sedra_runtime.harness.strom import Stroeme
from sedra_runtime.harness.team_lauf import TeamLauf


class ScheinApi:
    """Was team_lauf vom Server braucht. `verhalten[rolle](api, sid, antwort)` spielt den Helfer."""

    def __init__(self, ordner, slots=3):
        self.sitzungen, self.stroeme, self.karten = Sitzungen(ordner / 's'), Stroeme(), Karten(ordner / 'k')
        self.slots, self.verhalten, self.gemeldet, self.audit, self.zeiten = slots, {}, [], [], {}
        self.kein_modell = False
        self.faeden = []

    def slots_gesamt(self):
        return self.slots

    def belegte_slots(self, _eigene):
        return []

    def _melden(self, name, daten):
        self.gemeldet.append((name, daten))

    def _audit(self, event, payload):
        self.audit.append((event, payload))

    def helfer_sitzung(self, haupt, delegation, rolle, titel, slot):
        kopf = self.sitzungen.anlegen(haupt['kopf']['projekt'], f'{rolle}: {titel}', eltern=haupt['kopf']['id'], delegation=delegation, rolle=rolle)
        if slot is not None:
            self.sitzungen.slot_waehlen(kopf['id'], slot)
        return kopf

    def nachricht(self, sid, payload):
        if self.kein_modell:
            return {'status': 'kein_modell', 'grund': 'Kein Modell geladen – Modell wählen.'}
        self.sitzungen.anhaengen(sid, {'typ': 'captain', 'text': payload['text'], 'anhaenge': []})
        return self.fortsetzen(sid)

    def fortsetzen(self, sid, teil=0):
        antwort = self.stroeme.anlegen(sid)
        rolle = self.sitzungen.laden(sid)['kopf']['rolle']
        self.zeiten.setdefault(rolle, []).append(time.monotonic())

        def lauf():
            try:
                self.verhalten[rolle](self, sid, antwort, teil)
            finally:
                antwort.beenden()
                self.zeiten[rolle].append(time.monotonic())
        f = threading.Thread(target=lauf, daemon=True); self.faeden.append(f); f.start()
        return {'status': 'laeuft', 'antwort_id': antwort.id}

    def ende(self, sid, antwort, ende, text='', **extra):
        if ende != 'wartet':
            self.sitzungen.anhaengen(sid, {'typ': 'modell', 'antwort_id': antwort.id, 'text': text, 'ende': ende, 'zuege': 2})
        antwort.senden('ende', {'ende': ende, 'zuege': 2, 'token': {'ein': 10, 'aus': 5}, **extra})


def antwortet(text, dauer=0.15):
    def f(api, sid, antwort, _teil):
        ende = time.monotonic() + dauer
        while time.monotonic() < ende:
            if antwort.abbruch.is_set():
                return api.ende(sid, antwort, 'abgebrochen', 'halb')
            time.sleep(0.01)
        api.ende(sid, antwort, 'antwort', text)
    return f


def scheitert(api, sid, antwort, _teil):
    antwort.senden('ende', {'ende': 'fehler', 'zuege': 0, 'token': {'ein': 0, 'aus': 0}, 'grund': 'ModelRuntimeError: kaputt'})


def will_schreiben(api, sid, antwort, teil):
    if teil == 0:                                   # erster Teil: legt eine Karte vor und wartet
        k = api.karten.anlegen({'sitzung_id': sid, 'antwort_id': antwort.id, 'werkzeug': 'datei_schreiben', 'ziel': 'a.txt'})
        api.letzte_karte = k['karte_id']
        return api.ende(sid, antwort, 'wartet', karte_id=k['karte_id'])
    api.ende(sid, antwort, 'antwort', 'geschrieben')


class TeamLaufTest(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup)
        self.api = ScheinApi(Path(t.name))
        self.haupt = self.api.sitzungen.anlegen('p', 'Haupt')['id']
        self.addCleanup(lambda: [f.join(3) for f in self.api.faeden])        # erst wenn kein Faden mehr schreibt, räumt Windows den Ordner
        self.lauf = TeamLauf(self.api, takt_s=0.01)

    def auftraege(self, *rollen):
        return [{'rolle': r, 'text': 'Auftrag für ' + r} for r in rollen]

    def test_drei_helfer_arbeiten_gleichzeitig_und_liefern_ihren_text(self):          # DG-01, DG-02, DG-07
        self.api.slots = 4                                # Platz 0 behält die Hauptsitzung: drei Helfer zugleich brauchen vier Plätze
        self.api.verhalten = {r: antwortet('Text ' + r, 1.0) for r in 'ABC'}          # lang genug, dass der Vergleich auch unter Last trägt
        text = self.lauf.verteilen(self.haupt, None, self.auftraege('A', 'B', 'C'))
        for r in 'ABC':
            self.assertIn('Text ' + r, text)
        z = self.api.zeiten
        self.assertLess(max(z[r][0] for r in 'ABC'), min(z[r][1] for r in 'ABC'), 'alle drei haben begonnen, bevor der erste fertig war')
        helfer = [s for s in self.api.sitzungen.liste('p') if s.get('eltern') == self.haupt]
        self.assertEqual(sorted(s['rolle'] for s in helfer), ['A', 'B', 'C'])
        self.assertEqual(sorted(self.api.sitzungen.laden(s['id'])['slot'] for s in helfer), [1, 2, 3], 'drei feste Plätze neben dem der Hauptsitzung')
        self.assertEqual([e for e, _ in self.api.audit], ['HARNESS_TEAM_START', 'HARNESS_TEAM_ENDE'])                # DG-06
        auftrag = next(e['text'] for e in self.api.sitzungen.laden(helfer[0]['id'])['eintraege'] if e['typ'] == 'captain')
        self.assertIn('Du kannst selbst nicht delegieren', auftrag)

    def test_zwei_freie_plaetze_der_dritte_wartet_und_kommt_dran(self):                # DG-03
        self.api.verhalten = {r: antwortet('Text ' + r, 0.12) for r in 'ABC'}
        text = self.lauf.verteilen(self.haupt, None, self.auftraege('A', 'B', 'C'))
        z = self.api.zeiten
        self.assertGreaterEqual(z['C'][0], min(z['A'][1], z['B'][1]) - 0.02, 'C startet erst, wenn ein Platz frei ist')
        self.assertEqual(text.count('fertig'), 3)
        slots = sorted(self.api.sitzungen.laden(s['id'])['slot'] for s in self.api.sitzungen.liste('p') if s.get('eltern'))
        self.assertEqual(set(slots), {1, 2}, 'Platz 0 bleibt der Hauptsitzung')

    def test_ein_platz_dann_nacheinander_und_keiner_faellt_weg(self):                  # DG-03
        self.api.slots = 1
        self.api.verhalten = {r: antwortet('Text ' + r, 0.08) for r in 'ABC'}
        text = self.lauf.verteilen(self.haupt, None, self.auftraege('A', 'B', 'C'))
        z = self.api.zeiten
        self.assertGreaterEqual(z['B'][0], z['A'][1] - 0.02); self.assertGreaterEqual(z['C'][0], z['B'][1] - 0.02)
        self.assertEqual(text.count('fertig'), 3)

    def test_ein_gescheiterter_helfer_stoppt_die_anderen_nicht(self):                  # DG-08
        self.api.verhalten = {'A': scheitert, 'B': antwortet('Text B')}
        text = self.lauf.verteilen(self.haupt, None, self.auftraege('A', 'B'))
        self.assertIn('gescheitert – Grund: ModelRuntimeError: kaputt', text)
        self.assertIn('Text B', text)

    def test_ohne_modell_scheitern_die_helfer_mit_grund(self):
        self.api.kein_modell = True
        text = self.lauf.verteilen(self.haupt, None, self.auftraege('A'))
        self.assertIn('Kein Modell geladen', text)

    def test_zeitlimit_haelt_einen_helfer_an(self):                                     # DG-13
        self.lauf = TeamLauf(self.api, takt_s=0.01, zeitlimit_s=0.1)
        self.api.verhalten = {'A': antwortet('nie', 5), 'B': antwortet('Text B', 0.02)}
        t0 = time.monotonic()
        text = self.lauf.verteilen(self.haupt, None, self.auftraege('A', 'B'))
        self.assertLess(time.monotonic() - t0, 2)
        self.assertIn('Zeitlimit von 0 s erreicht', text)
        self.assertIn('Text B', text)

    def test_captain_haelt_einen_helfer_an_und_dann_alle(self):                         # DG-09
        self.api.verhalten = {'A': antwortet('nie', 5), 'B': antwortet('nie', 5)}
        aus = {}
        t = threading.Thread(target=lambda: aus.update(text=self.lauf.verteilen(self.haupt, None, self.auftraege('A', 'B'))))
        t.start()
        for _ in range(200):
            lauf = self.lauf.laufende()
            if lauf and all(h['zustand'] == 'laeuft' for h in lauf[0]['helfer']):
                break
            time.sleep(0.01)
        tid = lauf[0]['delegation']
        erster = lauf[0]['helfer'][0]['sitzung_id']
        self.assertEqual(self.lauf.stopp(tid, erster)['angehalten'], [1])
        self.assertEqual(self.lauf.stand(tid)['helfer'][0]['zustand'], 'angehalten')
        self.assertEqual(self.lauf.stand(tid)['helfer'][1]['zustand'], 'laeuft')
        self.assertEqual(self.lauf.stopp(tid)['angehalten'], [2])
        t.join(3)
        self.assertFalse(t.is_alive())
        self.assertEqual(aus['text'].count('angehalten – Grund: vom Captain angehalten'), 2)
        with self.assertRaises(KeyError):
            self.lauf.stopp('T-00000000')
        with self.assertRaises(KeyError):
            self.lauf.stopp(tid, 'S-FFFFFFFF')

    def test_gestoppte_hauptantwort_haelt_alle_helfer_an(self):
        self.api.verhalten = {'A': antwortet('nie', 5)}
        haupt_antwort = self.api.stroeme.anlegen(self.haupt)
        threading.Timer(0.1, haupt_antwort.stoppen).start()
        text = self.lauf.verteilen(self.haupt, haupt_antwort.id, self.auftraege('A'))
        self.assertIn('angehalten', text)

    def test_helfer_wartet_auf_freigabe_die_zeit_zaehlt_nicht_dann_geht_es_weiter(self):   # DG-04, DG-11, DG-13
        self.lauf = TeamLauf(self.api, takt_s=0.01, zeitlimit_s=0.3)
        self.api.verhalten = {'A': will_schreiben}
        aus = {}
        t = threading.Thread(target=lambda: aus.update(text=self.lauf.verteilen(self.haupt, None, self.auftraege('A'))))
        t.start()
        for _ in range(300):
            lauf = self.lauf.laufende()
            if lauf and lauf[0]['helfer'][0]['zustand'] == 'freigabe':
                break
            time.sleep(0.01)
        h = lauf[0]['helfer'][0]
        self.assertEqual(h['zustand'], 'freigabe')
        self.assertEqual(h['karte_id'], self.api.letzte_karte)
        self.assertEqual(self.api.karten.laden(h['karte_id'])['sitzung_id'], h['sitzung_id'], 'die Karte gehört dem Helfer')
        time.sleep(0.5)                                                  # länger als das Zeitlimit: Warten zählt nicht
        self.assertEqual(self.lauf.stand(lauf[0]['delegation'])['helfer'][0]['zustand'], 'freigabe')
        k = self.api.karten.laden(h['karte_id']); k['status'] = 'erlaubt'; self.api.karten.speichern(k)     # der Captain gibt frei …
        self.api.fortsetzen(h['sitzung_id'], teil=1)                                                       # … und die Antwort wird fortgesetzt
        t.join(3)
        self.assertFalse(t.is_alive())
        self.assertIn('geschrieben', aus['text'])
        self.assertIn('4 Züge', aus['text'], 'Züge beider Antworten des Helfers zusammen')

    def test_helfer_delegiert_nicht_und_nur_eine_delegation_je_sitzung(self):          # DG-05, DG-13
        helfer = self.api.sitzungen.anlegen('p', 'x', eltern=self.haupt, delegation='T-00000001', rolle='A')['id']
        with self.assertRaises(team.TeamFehler):
            self.lauf.verteilen(helfer, None, self.auftraege('A'))
        self.api.verhalten = {'A': antwortet('nie', 5)}
        t = threading.Thread(target=lambda: self.lauf.verteilen(self.haupt, None, self.auftraege('A')))
        t.start()
        for _ in range(200):
            if self.lauf.laufende():
                break
            time.sleep(0.01)
        with self.assertRaises(team.TeamFehler):
            self.lauf.verteilen(self.haupt, None, self.auftraege('A'))
        self.lauf.stopp(self.lauf.laufende()[0]['delegation'])
        t.join(3)

    def test_meldungen_an_die_oberflaeche_und_hinweis_bei_doppelter_datei(self):        # §3.3, DG-15
        self.api.verhalten = {'A': antwortet('nie', 5), 'B': antwortet('nie', 5)}
        t = threading.Thread(target=lambda: self.lauf.verteilen(self.haupt, None, self.auftraege('A', 'B')))
        t.start()
        for _ in range(200):
            lauf = self.lauf.laufende()
            if lauf and all(h['sitzung_id'] for h in lauf[0]['helfer']):
                break
            time.sleep(0.01)
        a, b = (h['sitzung_id'] for h in lauf[0]['helfer'])
        self.assertIsNone(self.lauf.datei_hinweis(a, 'src/x.py'))
        self.assertIn('auch der Helfer „A“', self.lauf.datei_hinweis(b, 'src/x.py'))
        self.assertIsNone(self.lauf.datei_hinweis('S-FFFFFFFF', 'src/x.py'))
        self.lauf.stopp(lauf[0]['delegation'])
        t.join(3)
        namen = {n for n, _ in self.api.gemeldet}
        self.assertEqual(namen, {'harness.team'})
        letzte = self.api.gemeldet[-1][1]
        self.assertTrue(letzte['fertig'])
        self.assertEqual(letzte['eltern'], self.haupt)
        self.assertNotIn('text', letzte['helfer'][0])


if __name__ == '__main__':
    unittest.main()
