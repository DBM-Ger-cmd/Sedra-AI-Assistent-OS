"""KI GateWay von Anfang bis Ende über den Hub (dieselben Wege wie die HTTP-Routen /api/gateway/*):
Vorgang anlegen → Eingabe prüfen → Freigabe (Gate) → Freigeben und anwenden → Entwurf → Prüfung.

Synthetische Testdaten, keine echten Personen. Zwei Wege zum Modell:
- lokal: ein Stub-Modell im Router (auf diesem PC ist kein GGUF-Modell hinterlegt)
- Cloud: ein Stub-Anbieter mit route=cloud. Er ist nur bereit, wenn sein Schlüssel gesetzt ist, und geht durch den Inhaltsschutz.
Ohne eingeschalteten Anbieter bleibt der Cloudweg die Simulation – und das steht im Entwurf.
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from guppi_runtime.models.base import BaseModelAdapter, ModelAdapterError
from guppi_runtime.uix_server import UIXHub
from host_isolation import setUpModule, tearDownModule  # noqa: F401

ARCH = sorted((Path(__file__).resolve().parents[2] / 'architecture').glob('GUPPI_Architecture_v*'))[-1]
KEY_ENV = 'GUPPI_SECRET_TESTANBIETER_API_KEY'
SK0_TEXT = 'Bitte eine kurze Übersicht für die nächste Projektabstimmung vorbereiten. Nenne offene Punkte, ohne Termine zu erfinden.'
SK1_TEXT = ('Bereite eine Antwort vor: Max Muster (max.muster@beispiel.test) fragt nach dem Stand von NORD-42. '
            'Kundennummer K-1042. Nenne offene Punkte, ohne Termine zu erfinden.')
SK3_TEXT = 'Unsere Kalkulation: Einkaufspreis 120 EUR, Marge 30 %, Verkaufspreis 170 EUR. Bitte eine Übersicht für den Kunden.'


class StubLokal(BaseModelAdapter):
    id = 'stub-lokal'

    def __init__(self, reply='Entwurf (lokal): offene Punkte sind offen.'):
        self.reply, self.calls = reply, []

    def health(self):
        return True

    def chat(self, messages, model=None, **kwargs):
        self.calls.append(messages)
        return {'provider': self.id, 'model': 'stub-lokal-1', 'content': self.reply, 'usage': {}}


class StubCloud(BaseModelAdapter):
    """Ein Cloud-Anbieter wie in models/cloud_api.py: route=cloud, bereit nur mit Schlüssel (health liest nur die Umgebung)."""
    id = 'testanbieter'
    route = 'cloud'
    default_model = 'test-modell-1'

    def __init__(self, reply='Entwurf (Cloud): offene Punkte sind offen.', fail=None):
        self.reply, self.fail, self.calls = reply, fail, []

    def health(self):
        return bool(os.environ.get(KEY_ENV))

    def chat(self, messages, model=None, **kwargs):
        self.calls.append(messages)
        if self.fail:
            raise ModelAdapterError(self.fail)
        return {'provider': self.id, 'model': model or self.default_model, 'content': self.reply, 'usage': {}}


class KIGateWayEndeZuEnde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='gw-e2e-')
        self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / 'project', ARCH)
        self.addCleanup(self.hub.close)
        self.lokal = StubLokal()
        self.hub.runtime.model_router.register(self.lokal)
        self.env = mock.patch.dict(os.environ, {}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)
        os.environ.pop(KEY_ENV, None)

    # --- kleine Helfer: genau die Schritte der Oberfläche
    def anlegen(self, wunsch='local'):
        return self.hub.gateway_new({'titel': 'Projektabstimmung (Test)', 'wunsch': wunsch})['id']

    def pruefen(self, vid, text):
        return self.hub.gateway_pruefen({'id': vid, 'anfrage': text, 'zweck': 'antwortentwurf', 'verantwortlich': 'Nutzer'})

    def freigeben_und_anwenden(self, vid, weg):
        gate = self.hub.gateway_freigabe({'id': vid, 'weg': weg})
        did = 'request:' + gate['mission_id']
        return did, self.hub.decide({'id': did, 'way': 'freigeben_und_anwenden'})

    def gehe_bis_zum_entwurf(self, text, wunsch, weg, vid=None):
        vid = vid or self.anlegen(wunsch)
        self.pruefen(vid, text)
        return vid, self.freigeben_und_anwenden(vid, weg)

    # ------------------------------------------------------------ Lokal (Regression)
    def test_lokal_von_anfang_bis_zur_pruefung(self):
        vid, (did, out) = self.gehe_bis_zum_entwurf(SK0_TEXT, 'local', 'LOCAL_ONLY')
        self.assertEqual(out['status'], 'answered')
        v = self.hub.gateway_get(vid)
        self.assertEqual(v['zustand'], 'ENTWURF')
        self.assertEqual(v['entwurf']['modell'], 'stub-lokal-1')
        self.assertIn('KI-Entwurf (stub-lokal-1) – menschlich geprüft: nein', v['entwurf']['kennzeichnung'])
        self.assertEqual(len(self.lokal.calls), 1)
        self.assertEqual([m['role'] for m in self.lokal.calls[0]], ['system', 'user'])
        done = self.hub.gateway_pruefung({'id': vid, 'urteil': 'geprueft'})
        self.assertEqual(done['zustand'], 'ABGESCHLOSSEN')
        self.assertEqual(done['entwurf']['pruefung'], 'geprueft')
        self.assertIn('menschlich geprüft: ja', self.hub.gateway_get(vid)['entwurf']['kennzeichnung'])

    def test_personenbezug_bleibt_lokal_und_ist_nicht_in_die_cloud_freigabefaehig(self):
        vid = self.anlegen('local')
        v = self.hub.gateway_pruefen({'id': vid, 'anfrage': SK1_TEXT, 'zweck': 'antwortentwurf', 'verantwortlich': 'Nutzer'})
        self.assertEqual(v['einstufung']['wege'], ['LOCAL_ONLY'])
        with self.assertRaises(ValueError):
            self.hub.gateway_freigabe({'id': vid, 'weg': 'CLOUD_ALLOWED'})

    def test_gesperrte_kategorie_erreicht_kein_modell(self):
        vid = self.anlegen('local')
        v = self.pruefen(vid, 'Hier mein Token ghp_' + 'a' * 36 + ' bitte prüfen.')
        self.assertEqual(v['zustand'], 'GESPERRT')
        with self.assertRaises(ValueError):
            self.hub.gateway_freigabe({'id': vid, 'weg': 'LOCAL_ONLY'})
        self.assertEqual(self.lokal.calls, [])

    def test_systemprompt_hat_kein_beispiel_platzhalter_zum_nachplappern(self):
        # Real (2026-10-19, qwen3.5-9b): das Modell übernahm „<Typ>“ und „<Nummer>“ aus dem Prompt in den Entwurf, die Prüfung
        # sah einen fehlerhaften Platzhalter (B6_PSEUDO_MALFORMED_PLACEHOLDER). Darum steht im Prompt kein Platzhalter in spitzen Klammern.
        from guppi_runtime.gateway import vorgang
        self.assertNotIn('<', vorgang.SYSTEM)
        self.assertNotIn('>', vorgang.SYSTEM)
        self.assertIn('dreistelligen Nummer', vorgang.SYSTEM)

    def test_nutzernachricht_trennt_anfrage_und_quelle(self):
        # Die Abgrenzung kommt vor den Text (Modellqualität: das 9B-Modell fand die Aufgabe nicht im Fließtext)
        from guppi_runtime.gateway import vorgang
        nur_anfrage = vorgang.nutzernachricht({'text': 'Frage A', 'dokument': ''})
        self.assertEqual(nur_anfrage, 'Anfrage:\nFrage A')
        mit_quelle = vorgang.nutzernachricht({'text': 'Frage A', 'dokument': 'Fakt B'})
        self.assertTrue(mit_quelle.startswith('Anfrage:\nFrage A'))
        self.assertIn('Quelle (Dokument', mit_quelle)
        self.assertTrue(mit_quelle.endswith('Fakt B'))
        self.assertNotIn('<', vorgang.nutzernachricht({'text': 'x', 'dokument': 'y'}))

    def test_docx_wird_als_text_gelesen_und_txt_bleibt_utf8(self):
        import zipfile
        from guppi_runtime.gateway import dokumente
        ordner = Path(self.tmp.name)
        docx = ordner / 'anfrage.docx'
        xml = ('<?xml version="1.0" encoding="UTF-8"?>'
               '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
               '<w:p><w:r><w:t>Auftrag AUF-778 ist offen.</w:t></w:r></w:p>'
               '<w:p><w:r><w:t>Betrag</w:t><w:tab/><w:t>120 EUR</w:t></w:r></w:p>'
               '</w:body></w:document>')
        with zipfile.ZipFile(docx, 'w') as z:
            z.writestr('word/document.xml', xml)
        self.assertEqual(dokumente.lies_datei(docx), 'Auftrag AUF-778 ist offen.\nBetrag\t120 EUR')
        txt = ordner / 'notiz.txt'
        txt.write_text('Ein Satz über Ärger.', encoding='utf-8')
        self.assertEqual(dokumente.lies_datei(txt), 'Ein Satz über Ärger.')

    def test_kaputtes_docx_ist_ein_fehler_und_kein_leerer_text(self):
        from guppi_runtime.gateway import dokumente
        ordner = Path(self.tmp.name)
        kaputt = ordner / 'kaputt.docx'
        kaputt.write_bytes(b'das ist kein zip-archiv')
        with self.assertRaisesRegex(ValueError, 'dokument_nicht_lesbar'):
            dokumente.lies_datei(kaputt)
        pdf = ordner / 'brief.pdf'
        pdf.write_bytes(b'%PDF-1.4')
        with self.assertRaisesRegex(ValueError, 'dokument_nicht_lesbar'):
            dokumente.lies_datei(pdf)

    # ------------------------------------------------------------ Cloud ohne Anbieter: Simulation, ehrlich beschriftet
    def test_cloud_ohne_anbieter_bleibt_simulation_und_sagt_es(self):
        self.assertEqual(self.hub.gateway_list()['cloud'], {'modus': 'simuliert', 'anbieter': [], 'bereit': [], 'fehler': None})
        vid, (did, out) = self.gehe_bis_zum_entwurf(SK0_TEXT, 'cloud', 'CLOUD_ALLOWED')
        v = self.hub.gateway_get(vid)
        self.assertEqual(v['zustand'], 'ENTWURF')
        self.assertEqual(v['entwurf']['modell'], 'Cloud (simuliert)')
        self.assertTrue(v['entwurf']['text'].startswith('[Cloud simuliert'))
        self.assertEqual(self.lokal.calls, [], 'die Simulation ruft kein Modell')

    # ------------------------------------------------------------ Cloud mit eingeschaltetem Anbieter
    def test_cloud_mit_anbieter_geht_ueber_den_router_und_ist_so_beschriftet(self):
        cloud = StubCloud()
        self.hub.runtime.model_router.register(cloud)
        self.hub.content_guard.cloud_enabled = True
        os.environ[KEY_ENV] = 'test-schluessel-nicht-echt'
        self.assertEqual(self.hub.gateway_list()['cloud']['modus'], 'anbieter')
        self.assertEqual(self.hub.gateway_list()['cloud']['bereit'], ['testanbieter'])

        vid = self.anlegen('cloud')
        self.pruefen(vid, SK0_TEXT)
        gate = self.hub.gateway_freigabe({'id': vid, 'weg': 'CLOUD_ALLOWED'})
        self.assertIn('Cloud-Anbieter testanbieter', gate['gate']['request']['risks'][-1])
        self.hub.decide({'id': 'request:' + gate['mission_id'], 'way': 'freigeben_und_anwenden'})

        self.assertEqual(len(cloud.calls), 1, 'genau ein Aufruf an den Anbieter')
        self.assertEqual([m['role'] for m in cloud.calls[0]], ['system', 'user'])
        self.assertEqual(set(cloud.calls[0][0]), {'role', 'content'}, 'keine Zusatzfelder ins Anbieter-Schema')
        self.assertEqual(self.lokal.calls, [], 'der Cloudweg fragt nicht das lokale Modell')
        v = self.hub.gateway_get(vid)
        self.assertEqual(v['zustand'], 'ENTWURF')
        self.assertEqual(v['entwurf']['modell'], 'Cloud · testanbieter · test-modell-1')
        self.assertEqual(v['entwurf']['weg'], 'CLOUD_ALLOWED')

    def test_cloud_anbieter_ohne_schluessel_wird_gar_nicht_erst_freigegeben(self):
        self.hub.runtime.model_router.register(StubCloud())
        self.hub.content_guard.cloud_enabled = True
        os.environ.pop(KEY_ENV, None)
        vid = self.anlegen('cloud')
        self.pruefen(vid, SK0_TEXT)
        with self.assertRaisesRegex(ValueError, 'cloud_anbieter_nicht_bereit'):
            self.hub.gateway_freigabe({'id': vid, 'weg': 'CLOUD_ALLOWED'})
        self.assertEqual(self.hub.gateway_get(vid)['zustand'], 'GEPRUEFT', 'nichts ist vorgemerkt')

    def test_ein_fehler_des_anbieters_wird_sichtbar_und_gibt_keinen_entwurf(self):
        self.hub.runtime.model_router.register(StubCloud(fail='cloud_api_error:URLError'))
        self.hub.content_guard.cloud_enabled = True
        os.environ[KEY_ENV] = 'test-schluessel-nicht-echt'
        vid = self.anlegen('cloud')
        self.pruefen(vid, SK0_TEXT)
        gate = self.hub.gateway_freigabe({'id': vid, 'weg': 'CLOUD_ALLOWED'})
        with self.assertRaisesRegex(ValueError, 'gateway_fehler:cloud_api_error'):
            self.hub.decide({'id': 'request:' + gate['mission_id'], 'way': 'freigeben_und_anwenden'})
        v = self.hub.gateway_get(vid)
        self.assertEqual(v['zustand'], 'FEHLER')
        self.assertIsNone(v['entwurf'])
        self.assertIn('cloud_api_error', v['fehler'])

    def test_die_antwort_der_cloud_durchlaeuft_die_pruefung_vor_dem_nutzer(self):
        # Eine Cloud-Antwort mit einem Schlüssel darin wird zurückgehalten (Recheck 3), genau wie bei der lokalen Antwort
        self.hub.runtime.model_router.register(StubCloud(reply='Hier der Schlüssel ghp_' + 'b' * 36))
        self.hub.content_guard.cloud_enabled = True
        os.environ[KEY_ENV] = 'test-schluessel-nicht-echt'
        vid = self.anlegen('cloud')
        self.pruefen(vid, SK0_TEXT)
        gate = self.hub.gateway_freigabe({'id': vid, 'weg': 'CLOUD_ALLOWED'})
        with self.assertRaisesRegex(ValueError, 'gateway_fehler:WITHHELD:SG_OUTPUT_KEY_FORMAT'):
            self.hub.decide({'id': 'request:' + gate['mission_id'], 'way': 'freigeben_und_anwenden'})
        v = self.hub.gateway_get(vid)
        self.assertEqual(v['zustand'], 'FEHLER')
        self.assertIsNone(v['entwurf'])


if __name__ == '__main__':
    unittest.main()
