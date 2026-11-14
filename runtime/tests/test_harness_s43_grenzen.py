"""S4.3 (Spec Freigaben S4, FS-11 bis FS-14, Entscheidung E5): gleiche Grenzen beim Erteilen, enges Muster, Ende der Sitzungs-Erlaubnis nach
24 Stunden, keine Sitzungs-Erlaubnis bei einem Cloud-Modell. Mit Gegenproben (jede Grenze entfernt → Test rot)."""
import itertools
import unittest
from datetime import datetime, timedelta, timezone

from sedra_runtime.harness import deckung, erlaubnis
from test_harness_deckung_vergleich import ablagen, alt, neu

JETZT = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)


def eintrag(alter_h=None, **kw):
    e = {'karte_id': 'K-1', 'werkzeug': 'datei_schreiben', 'muster': 'docs/**', 'aktiv': True}
    if alter_h is not None:
        e['zeit'] = (JETZT - timedelta(hours=alter_h)).isoformat()
    return dict(e, **kw)


class MusterTests(unittest.TestCase):                       # FS-12
    def test_datei_in_der_wurzel_nur_genau_diese_datei(self):
        self.assertEqual(erlaubnis.muster_fuer('datei_aendern', 'x.py'), 'x.py')
        self.assertEqual(erlaubnis.muster_fuer('datei_schreiben', 'README.md'), 'readme.md')      # pfad_normal: Kleinschreibung (Windows)

    def test_datei_im_ordner_der_ordner(self):
        self.assertEqual(erlaubnis.muster_fuer('datei_schreiben', 'docs/a.md'), 'docs/**')

    def test_gegenprobe_nie_das_weite_muster_fuer_dateien(self):
        for ziel in ('x.py', 'docs/a.md', 'a/b/c.txt'):
            self.assertNotIn(erlaubnis.muster_fuer('datei_schreiben', ziel), ('*', '**'))

    def test_wurzel_muster_deckt_andere_datei_nicht(self):
        m = erlaubnis.muster_fuer('datei_schreiben', 'x.py')
        self.assertIsNotNone(erlaubnis.deckt([eintrag(muster=m)], 'datei_schreiben', 'x.py'))
        self.assertIsNone(erlaubnis.deckt([eintrag(muster=m)], 'datei_schreiben', 'y.py'))


class GrenzenBeimErteilenTests(unittest.TestCase):          # FS-11
    def karte(self, ziel, werkzeug='datei_schreiben'):
        return {'art': 'werkzeug', 'werkzeug': werkzeug, 'ziel': ziel}

    def test_normale_ziele_gehen(self):
        self.assertTrue(erlaubnis.erlaubt_fuer_karte(self.karte('docs/a.md')))
        self.assertTrue(erlaubnis.erlaubt_fuer_karte(self.karte('python -m unittest', 'befehl')))

    def test_gegenprobe_pfad_mit_punkt_punkt_oder_absolut_nie(self):
        for ziel in ('../x.md', 'docs/../../x.md', '/etc/x', 'C:/x.md', 'C:' + chr(92) + 'x.md', 'a' + chr(92) + '..' + chr(92) + 'b'):
            self.assertFalse(erlaubnis.erlaubt_fuer_karte(self.karte(ziel)), ziel)

    def test_vorbehalt_warnung_verboten_bleiben_gesperrt(self):
        for extra in ({'vorbehalt': 'x'}, {'warnung': {'a': 1}}, {'stufe': 'verboten'}):
            self.assertFalse(erlaubnis.erlaubt_fuer_karte(dict(self.karte('docs/a.md'), **extra)))


class EndeTests(unittest.TestCase):                         # FS-14
    def test_vor_ablauf_gilt_sie(self):
        self.assertIsNotNone(erlaubnis.deckt([eintrag(alter_h=23)], 'datei_schreiben', 'docs/a.md', JETZT))

    def test_nach_24_stunden_gilt_sie_nicht_mehr(self):
        self.assertIsNone(erlaubnis.deckt([eintrag(alter_h=25)], 'datei_schreiben', 'docs/a.md', JETZT))

    def test_alte_eintraege_ohne_zeit_und_ohne_uhr_gelten_wie_zuvor(self):
        self.assertIsNotNone(erlaubnis.deckt([eintrag()], 'datei_schreiben', 'docs/a.md', JETZT))
        self.assertIsNotNone(erlaubnis.deckt([eintrag(alter_h=100)], 'datei_schreiben', 'docs/a.md'))

    def test_gegenprobe_kaputte_zeit_laesst_nicht_abstuerzen(self):
        self.assertIsNotNone(erlaubnis.deckt([eintrag(zeit='gestern')], 'datei_schreiben', 'docs/a.md', JETZT))

    def test_naechste_erlaubnis_deckt_wenn_die_erste_abgelaufen_ist(self):
        liste = [eintrag(alter_h=30, karte_id='K-alt'), eintrag(alter_h=1, karte_id='K-neu')]
        self.assertEqual(erlaubnis.deckt(liste, 'datei_schreiben', 'docs/a.md', JETZT)['karte_id'], 'K-neu')


class CloudTests(unittest.TestCase):                        # FS-13, E5 = nein
    def test_lokal_wie_zuvor_cloud_ohne_sitzungs_erlaubnis(self):
        for wirkt, vorb, warn, aktiv, weich_w, weich_p, a, z, s in itertools.product(
                ('frei', 'captain'), (None, 'V'), (False, True), (False, True), (None, {'w': 1}), (None, {'p': 1}), (False, True), (False, True), (False, True)):
            aufg, zaehlt, sitz = ablagen(a, z, s)
            referenz = alt(wirkt, vorb, warn, aktiv, weich_w, weich_p, aufg, zaehlt, sitz, [])
            cloud = deckung.deckt(
                wirkt_als=wirkt, vorbehalt=vorb, warnkarte=warn, aufgaben_aktiv=aktiv, weich_werkzeug=lambda: weich_w, weich_plan=weich_p,
                aufgabe_treffer=lambda w: aufg(w, []), aufgabe_zaehlen=lambda i: zaehlt(i, []), sitzung_treffer=lambda: sitz([]), lokal=False)
            self.assertIsNone(cloud['via_sitzung'])
            self.assertEqual(cloud['via_aufgabe'], referenz['via_aufgabe'])           # Aufgaben bleiben, wie sie waren (sie sind schon lokal-gebunden)
            self.assertEqual(neu(wirkt, vorb, warn, aktiv, weich_w, weich_p, aufg, zaehlt, sitz, []), referenz)      # lokal=True ist unverändert

    def test_gegenprobe_cloud_mit_treffer_bleibt_karte(self):
        aufg, zaehlt, sitz = ablagen(False, False, True)
        r = deckung.deckt(wirkt_als='captain', vorbehalt=None, warnkarte=False, aufgaben_aktiv=False, weich_werkzeug=lambda: None, weich_plan=None,
                          aufgabe_treffer=lambda w: aufg(w, []), aufgabe_zaehlen=lambda i: zaehlt(i, []), sitzung_treffer=lambda: sitz([]), lokal=False)
        self.assertEqual(r, {'via_aufgabe': None, 'via_sitzung': None})


if __name__ == '__main__':
    unittest.main()
