import json
import tempfile
import unittest
from pathlib import Path

from sedra_runtime.workflows import lokal
from sedra_runtime.workflows.lokal_daten import Eingaben, Tabellen

WF = json.loads((Path(__file__).with_name('rechnungspruefung.json')).read_text(encoding='utf-8'))
BS = chr(92)
QM = chr(178)          # Hochgestelltes 2 (WinAnsi 0xB2)


def pdf(zeilen):
    """Ein einseitiges PDF aus Textzeilen (von Hand geschrieben, WinAnsi, damit der Quadratmeter-Index ankommt)."""
    def esc(s):
        return ''.join(BS + '%03o' % ord(c) if ord(c) > 127 or c in '()' + BS else c for c in s)
    inhalt = 'BT /F1 10 Tf 12 TL 40 800 Td ' + ' '.join('(%s) Tj T*' % esc(z) for z in zeilen) + ' ET'
    objekte = ['<< /Type /Catalog /Pages 2 0 R >>', '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>',
               '<< /Length %d >>\nstream\n%s\nendstream' % (len(inhalt), inhalt),
               '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>']
    out, pos = b'%PDF-1.4\n', []
    for i, o in enumerate(objekte, 1):
        pos.append(len(out))
        out += ('%d 0 obj\n%s\nendobj\n' % (i, o)).encode('latin-1')
    x = len(out)
    out += ('xref\n0 %d\n0000000000 65535 f \n' % (len(objekte) + 1) + ''.join('%010d 00000 n \n' % p for p in pos)).encode()
    return out + ('trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF' % (len(objekte) + 1, x)).encode()


RECHNUNG = ['Rechnung Nr. RE-ST-2026-0042', 'Auftrag: AUF-2026-ST-17', 'Rechnungsdatum: 12.11.2026', 'Pos. Menge Einheit Einzelpreis Gesamt',
            '01.01.0010 Baustelleneinrichtung', '1 psch. 1.200,00 1.200,00', '01.01.0020 Fliesen verlegen', '20 m' + QM + ' 45,50 910,00',
            'Gesamt netto: 2.110,00', 'Gesamt brutto: 2.510,90']


class Lokal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Path(self.tmp.name)
        t = Tabellen(self.p)
        t.importieren('Auftraege', json.dumps([{'auftragsnummer': 'AUF-2026-ST-17', 'gesamt_brutto': 2510.90}]))
        pos = [{'auftragsnummer': 'AUF-2026-ST-17', 'lv_position': '01.01.0010', 'menge': 1, 'einzelpreis_netto': 1200, 'gesamtpreis_netto': 1200},
               {'auftragsnummer': 'AUF-2026-ST-17', 'lv_position': '01.01.0020', 'menge': 20, 'einzelpreis_netto': 45.5, 'gesamtpreis_netto': 910}]
        t.importieren('Auftragspositionen', json.dumps(pos))

    def lauf(self, zeilen=RECHNUNG):
        summe = Eingaben(self.p).speichern(pdf(zeilen))
        return lokal.ausfuehren(WF, {'Rechnung': {'datei': summe, 'name': 'r.pdf'}}, self.p)

    def test_bewertung(self):
        b = lokal.bewerten(WF)
        self.assertTrue(b['executable'], b)
        self.assertEqual(b['schreibt'], ['Kosten bersicht'])
        self.assertEqual(b['dateifelder'], ['Rechnung'])
        self.assertEqual(sorted(b['uebersprungen']), ['Anthropic Chat Model', 'Information Extractor'])

    def test_stimmt_ueberein(self):
        r = self.lauf()
        self.assertEqual(r['status'], 'completed', r)
        zeile = Tabellen(self.p).lesen('Kostenübersicht')['zeilen'][0]
        self.assertEqual((zeile['rechnungsnummer'], zeile['rechnungsbetrag'], zeile['auftragsbetrag']), ('RE-ST-2026-0042', 2510.9, 2510.9))
        self.assertEqual(zeile['pruefstatus'], 'ALLE POSITIONEN STIMMEN ÜBEREIN')
        self.assertEqual(r['tabellen_geschrieben'], ['Kosten bersicht'])

    def test_abweichung(self):
        r = self.lauf([z.replace('910,00', '900,00') for z in RECHNUNG])
        self.assertEqual(r['status'], 'completed', r)
        self.assertIn('Klärung erforderlich', r['output'])
        self.assertEqual(r['output']['Klärung erforderlich'][0]['Prüfstatus'], 'MANUELLE PRÜFUNG ERFORDERLICH')
        with self.assertRaises(ValueError):
            Tabellen(self.p).lesen('Kostenübersicht')

    def test_kein_pdf_ist_fehler(self):
        summe = Eingaben(self.p).speichern(b'kein pdf')
        r = lokal.ausfuehren(WF, {'Rechnung': {'datei': summe, 'name': 'x.pdf'}}, self.p)
        self.assertEqual(r['status'], 'failed')
        self.assertEqual(r['fehler_knoten'], 'Extract from File')

    def test_unbekannter_knoten_wird_abgelehnt(self):
        wf = json.loads(json.dumps(WF))
        wf['nodes'][0]['type'] = 'n8n-nodes-base.httpRequest'
        self.assertFalse(lokal.bewerten(wf)['executable'])

    def test_sandbox(self):
        for quelle in ('typeof process !== "undefined"', 'this.constructor.constructor("return process")()', '(()=>{}).constructor("return 1")()'):
            try:
                self.assertFalse(lokal._js([{'json': {}}], {}, [{'kind': 'expr', 'source': quelle, 'index': 0}])[0])
            except lokal.LokalFehler:
                pass


ARCH = Path(__file__).resolve().parents[2] / 'architecture/SEDRA_Architecture_v1.20_SELF_DEVELOPMENT'


class Freigabe(unittest.TestCase):
    def setUp(self):
        from sedra_runtime.uix_server import UIXHub
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / 'project', ARCH)
        self.addCleanup(self.hub.close)
        t = Tabellen(self.hub.project_root)
        t.importieren('Auftraege', json.dumps([{'auftragsnummer': 'AUF-2026-ST-17', 'gesamt_brutto': 2510.90}]))
        t.importieren('Auftragspositionen', json.dumps([
            {'auftragsnummer': 'AUF-2026-ST-17', 'lv_position': '01.01.0010', 'menge': 1, 'einzelpreis_netto': 1200, 'gesamtpreis_netto': 1200},
            {'auftragsnummer': 'AUF-2026-ST-17', 'lv_position': '01.01.0020', 'menge': 20, 'einzelpreis_netto': 45.5, 'gesamtpreis_netto': 910}]))

    def test_start_gate_freigabe_lauf(self):
        import base64
        from sedra_runtime.workflows.desk import _save, _start, _run_read, _eingabe_hochladen
        rec = _save(self.hub, None, {'workflow': WF})
        self.assertEqual(rec['execution']['profile'], lokal.PROFILE)
        up = _eingabe_hochladen(self.hub, None, {'name': 'r.pdf', 'data': base64.b64encode(pdf(RECHNUNG)).decode()})
        run = _start(self.hub, rec['id'], {'revision': 1, 'inputs': {'Rechnung': {'datei': up['datei'], 'name': 'r.pdf'}}})
        self.assertEqual(run['state'], 'CAPTAIN_REVIEW')
        m = self.hub.runtime.missions.load(run['id'])
        gate = m['human_gates']['pending'][0]
        self.assertEqual(gate['request']['exact_action'], 'run_sedra_workflow')
        eintrag = [d for d in self.hub.decisions_view()['items'] if d.get('mission_id') == run['id']]        # die Freigabe liegt im Posteingang
        self.assertEqual([(d['gate_id'], d['ways']) for d in eintrag], [(gate['gate_id'], ['einmal', 'ablehnen'])])
        self.assertIn('Rechnungsprüfung', eintrag[0]['title'])
        self.assertFalse(Tabellen(self.hub.project_root)._finden('Kostenübersicht'))      # vor dem Ja ist nichts passiert
        m['execution']['approval_token'] = self.hub.runtime.guard.approve(gate)
        m['human_gates']['pending'] = []
        self.hub.runtime.missions.save(m)
        self.hub.run_mission({'mission_id': run['id']})
        out = _run_read(self.hub, run['id'])
        self.assertEqual(out['state'], 'COMPLETE', out)
        self.assertEqual(out['result']['tabellen_geschrieben'], ['Kosten bersicht'])
        self.assertEqual(Tabellen(self.hub.project_root).lesen('Kostenübersicht')['anzahl'], 1)

    def _vorgelegt(self):
        import base64
        from sedra_runtime.desk import systemdialog
        from sedra_runtime.workflows.desk import _save, _start, _eingabe_hochladen
        systemdialog.setzen(lambda titel, text: None)           # kein echtes Windows-Fenster im Test
        self.addCleanup(systemdialog.setzen, None)
        rec = _save(self.hub, None, {'workflow': WF})
        up = _eingabe_hochladen(self.hub, None, {'name': 'r.pdf', 'data': base64.b64encode(pdf(RECHNUNG)).decode()})
        run = _start(self.hub, rec['id'], {'revision': 1, 'inputs': {'Rechnung': {'datei': up['datei'], 'name': 'r.pdf'}}})
        [eintrag] = [d for d in self.hub.decisions_view()['items'] if d.get('mission_id') == run['id']]
        return run, eintrag

    def test_freigabe_im_fenster_der_seite_genuegt(self):
        """Klasse N (12.11.2026): "einmal" aus der Seite gibt den Lauf frei, ohne zweites Windows-Fenster; danach läuft er bis zum Ergebnis."""
        from sedra_runtime.workflows.desk import _run_read
        run, eintrag = self._vorgelegt()
        self.hub.decide({'id': eintrag['id'], 'way': 'einmal'})
        self.assertEqual(self.hub.bestaetigungen.offen(), [])
        self.assertEqual(self.hub.runtime.missions.load(run['id'])['human_gates']['pending'], [])
        self.hub.run_mission({'mission_id': run['id']})
        self.assertEqual(_run_read(self.hub, run['id'])['state'], 'COMPLETE')

    def test_live_wartet_laeuft_fertig(self):
        """Reiter Live: der Lauf meldet "wartet auf Freigabe" (nie veraltet), dann jeden Knoten, am Ende fertig - mit den Knoten des gespeicherten Workflows."""
        from datetime import datetime, timedelta, timezone
        from sedra_runtime.workflows import live
        from sedra_runtime.workflows.desk import _live
        run, eintrag = self._vorgelegt()
        [p] = _live(self.hub, None, {})['prozesse']
        self.assertEqual((p['zustand'], p['schritt_name'], p['titel']), ('wartet', 'Rechnungsprüfung', 'Rechnungsprüfung'))
        spaet = datetime.now(timezone.utc) + timedelta(hours=1)
        self.assertFalse(live.lesen(self.hub.project_root, jetzt=spaet)[0]['veraltet'])          # wartet auf den Captain: nicht "ohne Meldung"
        self.hub.decide({'id': eintrag['id'], 'way': 'einmal'})
        self.hub.run_mission({'mission_id': run['id']})
        [p] = _live(self.hub, None, {})['prozesse']
        self.assertEqual(p['zustand'], 'fertig')
        ids = {n['name']: n['id'] for n in WF['nodes']}
        self.assertEqual(p['knoten'][ids['Kostenübersicht']], 'fertig')
        self.assertEqual(p['knoten'][ids['Rechnungspositionen auslesen']], 'fertig')
        self.assertNotIn(ids['Klärung erforderlich'], p['knoten'])                                # der Nein-Zweig lief nicht
        self.assertEqual([e['schritt_name'] for e in p['verlauf']][:3], ['Rechnungsprüfung', 'Rechnungsprüfung', 'Extract from File'])

    def test_live_abgelehnte_freigabe_ist_ein_fehler(self):
        from sedra_runtime.workflows.desk import _live
        run, eintrag = self._vorgelegt()
        self.hub.decide({'id': eintrag['id'], 'way': 'ablehnen'})
        [p] = _live(self.hub, None, {})['prozesse']
        self.assertEqual(p['zustand'], 'fehler')
        self.assertIn('abgelehnt', p['text'])

    def test_klasse_h_bestaetigung_gilt_nicht_als_hinfaellig(self):
        """Der Weg außerhalb des Browsers (Klasse H, hier erzwungen): ohne Bindung am Gate hielt SEDRA jede Bestätigung für hinfällig
        (FREIGABE_DIALOG_FEHLER bestaetigung_hinfaellig), und das Gate blieb ewig offen."""
        from unittest.mock import patch
        from sedra_runtime.desk import freigabeklasse
        from sedra_runtime.workflows.desk import _run_read
        with patch.object(freigabeklasse, 'KLASSE_N_GATES', frozenset()):
            run, eintrag = self._vorgelegt()
            self.assertTrue(eintrag['binding'])
            with self.assertRaisesRegex(Exception, 'wartet_auf_bestaetigung'):
                self.hub.decide({'id': eintrag['id'], 'way': 'einmal'})
            [offen] = self.hub.bestaetigungen.offen()
            self.hub.freigabe_bestaetigen(offen['bid'], True, 'konsole')                 # darf nicht bestaetigung_hinfaellig werfen
        self.assertEqual(self.hub.runtime.missions.load(run['id'])['human_gates']['pending'], [])
        self.hub.run_mission({'mission_id': run['id']})
        self.assertEqual(_run_read(self.hub, run['id'])['state'], 'COMPLETE')

    def test_fehlende_datei_wird_vor_dem_gate_abgelehnt(self):
        from sedra_runtime.workflows.desk import _save, _start
        rec = _save(self.hub, None, {'workflow': WF})
        with self.assertRaises(ValueError):
            _start(self.hub, rec['id'], {'revision': 1, 'inputs': {}})


if __name__ == '__main__':
    unittest.main()
