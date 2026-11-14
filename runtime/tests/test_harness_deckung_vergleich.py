"""S4.2 (FS-10, Spec Freigaben S4): `deckung.deckt` und die Zeilen, die vorher in `Kiste.aufruf` standen, geben für jede Kombination
dieselbe Antwort und rufen die Ablagen gleich oft auf (Wahrheitstabelle alt gegen neu, ohne Abweichung). Gegenproben: eine vertauschte
Reihenfolge, eine Deckung trotz Vorbehalt oder Warnkarte und ein Sitzungs-Treffer trotz weichem Vorbehalt fallen auf."""
import itertools
import unittest

from sedra_runtime.harness import deckung


def alt(wirkt_als, vorbehalt, warnkarte, aufgaben_aktiv, weich_w, weich_p, aufg, zaehlt, sitz, log):
    """Der Wortlaut von `Kiste.aufruf` vor S4.2 (freigabe.py), mit denselben Ablagen als Funktionen."""
    via_aufgabe, via_sitzung = None, None
    if wirkt_als != 'frei' and aufgaben_aktiv and not vorbehalt and not warnkarte:
        weich = (log.append('weich') or weich_w) or weich_p
        treffer = aufg(weich, log)
        if treffer and zaehlt(treffer['aufgabe_id'], log):
            via_aufgabe = treffer['aufgabe_id']
    if wirkt_als != 'frei' and not via_aufgabe and not vorbehalt and not warnkarte and not (log.append('weich') or weich_w):
        treffer = sitz(log)
        if treffer:
            via_sitzung = treffer['karte_id']
    return {'via_aufgabe': via_aufgabe, 'via_sitzung': via_sitzung}


def neu(wirkt_als, vorbehalt, warnkarte, aufgaben_aktiv, weich_w, weich_p, aufg, zaehlt, sitz, log):
    return deckung.deckt(
        wirkt_als=wirkt_als, vorbehalt=vorbehalt, warnkarte=warnkarte, aufgaben_aktiv=aufgaben_aktiv,
        weich_werkzeug=lambda: log.append('weich') or weich_w, weich_plan=weich_p,
        aufgabe_treffer=lambda weich: aufg(weich, log), aufgabe_zaehlen=lambda i: zaehlt(i, log), sitzung_treffer=lambda: sitz(log))


def ablagen(aufgabe_trifft, zaehlbar, sitzung_trifft):
    def aufg(weich, log):
        log.append(('aufgabe', weich))
        return {'aufgabe_id': 'A-1'} if aufgabe_trifft else None

    def zaehlt(i, log):
        log.append(('zaehlen', i))
        return zaehlbar

    def sitz(log):
        log.append('sitzung')
        return {'karte_id': 'K-1'} if sitzung_trifft else None
    return aufg, zaehlt, sitz


class WahrheitstabelleTest(unittest.TestCase):
    def test_alt_gleich_neu_fuer_jede_kombination(self):
        n = 0
        for wirkt, vorb, warn, aktiv, weich_w, weich_p, a, z, s in itertools.product(
                ('frei', 'captain'), (None, 'Vorbehalt'), (False, True), (False, True), (None, {'weich': 1}), (None, {'p': 1}),
                (False, True), (False, True), (False, True)):
            aufg, zaehlt, sitz = ablagen(a, z, s)
            la, ln = [], []
            ra = alt(wirkt, vorb, warn, aktiv, weich_w, weich_p, aufg, zaehlt, sitz, la)
            rn = neu(wirkt, vorb, warn, aktiv, weich_w, weich_p, aufg, zaehlt, sitz, ln)
            self.assertEqual(ra, rn, (wirkt, vorb, warn, aktiv, weich_w, weich_p, a, z, s))
            self.assertEqual(la, ln, ('Aufrufe der Ablagen', wirkt, vorb, warn, aktiv, weich_w, weich_p, a, z, s))
            n += 1
        self.assertEqual(n, 2 * 2 * 2 * 2 * 2 * 2 * 2 * 2 * 2)

    def test_gegenprobe_vorbehalt_und_warnkarte_decken_nie(self):
        aufg, zaehlt, sitz = ablagen(True, True, True)
        for vorb, warn in (('V', False), (None, True), ('V', True)):
            r = neu('captain', vorb, warn, True, None, None, aufg, zaehlt, sitz, [])
            self.assertEqual(r, {'via_aufgabe': None, 'via_sitzung': None})

    def test_gegenprobe_frei_verbraucht_nichts(self):
        log = []
        aufg, zaehlt, sitz = ablagen(True, True, True)
        r = neu('frei', None, False, True, None, None, aufg, zaehlt, sitz, log)
        self.assertEqual(r, {'via_aufgabe': None, 'via_sitzung': None})
        self.assertEqual(log, [])

    def test_gegenprobe_weicher_vorbehalt_laesst_keine_sitzungserlaubnis_durch(self):
        aufg, zaehlt, sitz = ablagen(False, False, True)
        r = neu('captain', None, False, True, {'weich': 1}, None, aufg, zaehlt, sitz, [])
        self.assertEqual(r['via_sitzung'], None)

    def test_aufgabe_geht_vor_sitzung_und_zaehlt_genau_einmal(self):
        log = []
        aufg, zaehlt, sitz = ablagen(True, True, True)
        r = neu('captain', None, False, True, None, None, aufg, zaehlt, sitz, log)
        self.assertEqual(r, {'via_aufgabe': 'A-1', 'via_sitzung': None})
        self.assertEqual([x for x in log if isinstance(x, tuple) and x[0] == 'zaehlen'], [('zaehlen', 'A-1')])
        self.assertNotIn('sitzung', log)

    def test_aufgabe_nicht_zaehlbar_faellt_auf_sitzung_zurueck(self):
        aufg, zaehlt, sitz = ablagen(True, False, True)
        r = neu('captain', None, False, True, None, None, aufg, zaehlt, sitz, [])
        self.assertEqual(r, {'via_aufgabe': None, 'via_sitzung': 'K-1'})


if __name__ == '__main__':
    unittest.main()
