"""AM5 (SPEC_APPS_v1_AM5_LANGDOCK_MODELL): Langdock als Modellquelle – nur mit Attrappe, kein Netz, keine echten Schlüssel.
Geprüft: Region (AM5-03), Modellliste des Betreibers (AM5-04), gesendete Felder (AM5-05), Fehlersätze (AM5-06), kein stilles Umschalten (AM5-07),
Empfängerverzeichnis (AM5-08), Inhaltsschutz (AM5-09), Kosten (AM5-11), Konfiguration (AM5-02).
NICHT geprüft (ohne Zugang): das echte Verhalten der Langdock-Schnittstelle, die Richtigkeit der Suchauszüge in Spec §1, Limits, Modellliste."""
import datetime
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError

import yaml

from sedra_runtime import cloud_settings
from sedra_runtime.core.content_guard import ContentGuard, ContentGuardStop
from sedra_runtime.models import cloud_api, langdock
from sedra_runtime.models.base import ModelAdapterError
from sedra_runtime.models.cloud_api import build_cloud_adapters, provider_adapter
from sedra_runtime.models.router import ModelRouter

URL = "https://api.langdock.com/openai/eu/v1"
KEY = {"SEDRA_SECRET_LANGDOCK_API_KEY": "test-key-not-real"}
HEUTE = datetime.date(2026, 11, 12)
MODELL = {"attrappe-eu": {"aufbewahrung": "keine", "geprueft_am": "2026-11-01", "quelle": "Attrappe"},
          "attrappe-lang": {"aufbewahrung": 30, "geprueft_am": "2026-11-01", "quelle": "Attrappe"},
          "attrappe-lang-ok": {"aufbewahrung": 30, "erlaubt_trotz_aufbewahrung": True, "geprueft_am": "2026-11-01", "quelle": "Attrappe"},
          "attrappe-preis": {"aufbewahrung": "keine", "preis_eur_je_million_token": {"eingabe": 2.0, "ausgabe": 10.0}}}
EMPFAENGER = {"empfaenger": {"langdock": {
    "name": "Langdock", "rolle": "Auftragsverarbeiter", "region": "eu", "aufbewahrung": "Attrappe", "zweck": "Test", "gepflegt_von": "Test",
    "geprueft_am": "2026-11-01", "vertrag": {"fassung": "Attrappe", "datum": "2026-11-01", "fundstelle": "Attrappe"},
    "unterauftragsverarbeiter": {"datum": "2026-11-01", "liste": ["Attrappe GmbH"]}}}}


def adapter(modell="attrappe-eu", url=URL, modelle=MODELL, environ=KEY):
    return langdock.LangdockAdapter("langdock", url, "secret://langdock/api-key", modell, timeout=100, environ=environ, modelle=modelle)


class Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


def antwort(inhalt="pong", usage=None):
    return Resp(json.dumps({"choices": [{"message": {"content": inhalt}, "finish_reason": "stop"}], "usage": usage or {"prompt_tokens": 3, "completion_tokens": 1}}).encode())


class Wurzel(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="am5-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def schreibe(self, name, daten):
        p = self.root / "local_config" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(yaml.safe_dump(daten, allow_unicode=True), encoding="utf-8")


class Konfiguration(unittest.TestCase):
    def test_paketeintrag_ist_aus_mit_fester_eu_adresse(self):
        cfg = yaml.safe_load(Path(cloud_settings.DEFAULT_CONFIG).read_text(encoding="utf-8"))["cloud_providers"]["providers"]["langdock"]
        self.assertFalse(cfg["enabled"])
        self.assertEqual((cfg["kind"], cfg["base_url"], cfg["api_key"], cfg["default_model"], cfg["timeout_s"]),
                         ("openai_compatible", URL, "secret://langdock/api-key", None, 100))

    def test_vorlagen_enthalten_nur_platzhalter(self):
        for name in ("cloud_modelle.beispiel.yaml", "empfaenger.beispiel.yaml"):
            text = (Path(cloud_settings.DEFAULT_CONFIG).parent / name).read_text(encoding="utf-8")
            self.assertIn("<", text)
            self.assertNotIn("secret", text.lower().replace("secret://", ""))


class Region(Wurzel):
    def test_nur_die_feste_eu_adresse(self):
        self.assertTrue(langdock.url_erlaubt(URL))
        self.assertTrue(langdock.url_erlaubt(URL + "/"))
        for schlecht in ("https://api.langdock.com/openai/us/v1", "https://api.langdock.com/openai/global/v1", "https://example.test/openai/eu/v1",
                         "http://api.langdock.com/openai/eu/v1", "https://api.langdock.com/openai/eu/v1/x", None):
            self.assertFalse(langdock.url_erlaubt(schlecht), schlecht)
        with self.assertRaises(ValueError) as ctx:
            adapter(url="https://api.langdock.com/openai/us/v1")
        self.assertEqual(str(ctx.exception), "langdock_region_nicht_erlaubt")

    def test_der_kern_prueft_beim_speichern_und_beim_antrag(self):
        self.schreibe("cloud_providers.yaml", yaml.safe_load(Path(cloud_settings.DEFAULT_CONFIG).read_text(encoding="utf-8")))
        for fn in (cloud_settings.save, cloud_settings.base_url_aenderungen):
            with self.assertRaises(ValueError) as ctx:
                fn(self.root, {"enabled": True, "providers": {"langdock": {"base_url": "https://api.langdock.com/openai/global/v1"}}})
            self.assertTrue(str(ctx.exception).startswith("langdock_region_nicht_erlaubt"))
        cloud_settings.save(self.root, {"enabled": True, "providers": {"langdock": {"base_url": URL}}})      # die feste Adresse geht
        # andere Anbieter bleiben unberührt
        self.assertTrue(cloud_settings.anbieter_url_erlaubt("nvidia", "https://beliebig.example.test/v1"))


class Modellliste(Wurzel):
    def test_nur_eingetragene_modelle_und_aufbewahrung(self):
        self.assertEqual(langdock.modell_pruefen(MODELL, "attrappe-eu"), (True, None))
        self.assertEqual(langdock.modell_pruefen(MODELL, "unbekannt"), (False, "langdock_modell_nicht_geprueft"))
        self.assertEqual(langdock.modell_pruefen(MODELL, "attrappe-lang"), (False, "langdock_modell_aufbewahrung"))
        self.assertEqual(langdock.modell_pruefen(MODELL, "attrappe-lang-ok"), (True, None))
        self.assertEqual(langdock.modell_pruefen({"x": {}}, "x"), (False, "langdock_modell_aufbewahrung"), "ohne Angabe gilt Aufbewahrung als unbekannt")

    def test_ohne_datei_ist_kein_modell_waehlbar(self):
        self.assertEqual(langdock.modelle_laden(self.root), {})
        self.assertEqual(langdock.modelle_laden(None), {})
        self.schreibe("cloud_modelle.yaml", {"langdock": MODELL})
        self.assertIn("attrappe-eu", langdock.modelle_laden(self.root))
        (self.root / "local_config" / "cloud_modelle.yaml").write_text("{ kaputt", encoding="utf-8")
        self.assertEqual(langdock.modelle_laden(self.root), {})

    def test_der_adapter_sendet_kein_nicht_eingetragenes_modell(self):
        with mock.patch.object(cloud_api._OPENER, "open", side_effect=AssertionError("kein Netz")):
            for modell, grund in (("unbekannt", "langdock_modell_nicht_geprueft"), ("attrappe-lang", "langdock_modell_aufbewahrung")):
                with self.assertRaises(ModelAdapterError) as ctx:
                    adapter().chat([{"role": "user", "content": "x"}], model=modell)
                self.assertEqual(str(ctx.exception), f"{grund}:{modell}")
            with self.assertRaises(ModelAdapterError):
                adapter(modell="unbekannt").chat([{"role": "user", "content": "x"}])
        self.assertFalse(adapter(modell="unbekannt").health())
        self.assertTrue(adapter().health())
        self.assertEqual(adapter(modelle={}).list_models(), [])

    def test_abgleich_zeigt_ungeprueftes(self):
        a = langdock.abgleich(MODELL, ["attrappe-eu", "neu-bei-langdock", "attrappe-lang"])
        self.assertEqual(a["geprueft"], ["attrappe-eu"])
        self.assertEqual(a["nicht_geprueft"], ["attrappe-lang", "neu-bei-langdock"])
        self.assertIn("attrappe-preis", a["nicht_angeboten"])


class Gesendet(unittest.TestCase):
    def test_nur_bekannte_felder_und_der_bearer_schluessel(self):
        gesehen = {}

        def fake(req, timeout):
            gesehen.update(url=req.full_url, auth=req.get_header("Authorization"), body=json.loads(req.data.decode()), timeout=timeout)
            return antwort()

        with mock.patch.object(cloud_api._OPENER, "open", side_effect=fake):
            out = adapter().chat([{"role": "user", "content": "ping"}], temperature=0.2, max_tokens=50, top_p=0.9,
                                 n=2, service_tier="x", parallel_tool_calls=True, stream_options={"include_usage": True})
        self.assertEqual(gesehen["url"], URL + "/chat/completions")
        self.assertEqual(gesehen["auth"], "Bearer test-key-not-real")
        self.assertLessEqual(set(gesehen["body"]), langdock.GESENDET, "AM5-05: n, service_tier, parallel_tool_calls, stream_options gehen nie hinaus")
        self.assertFalse(gesehen["body"]["stream"])
        self.assertEqual(gesehen["timeout"], 100)
        self.assertEqual(out["provider"], "langdock")
        self.assertEqual(out["usage"], {"input_tokens": 3, "output_tokens": 1})

    def test_optionen_nur_fuer_lokale_modelle_werden_laut_abgelehnt(self):
        with self.assertRaises(ModelAdapterError) as ctx:
            adapter().chat([{"role": "user", "content": "x"}], tools=[{"type": "function"}])
        self.assertEqual(str(ctx.exception), "cloud_option_unsupported:tools")


class Fehler(unittest.TestCase):
    def fehler(self, code, body=b"test-key-not-real echoed"):
        err = HTTPError(URL + "/chat/completions", code, "x", None, io.BytesIO(body))
        zaehler = mock.Mock(side_effect=err)
        with mock.patch.object(cloud_api._OPENER, "open", zaehler):
            with self.assertRaises(ModelAdapterError) as ctx:
                adapter().chat([{"role": "user", "content": "x"}])
        return str(ctx.exception), zaehler.call_count

    def test_saetze_ohne_wiederholung(self):
        for code, teil in ((429, "Limit erreicht"), (504, "nach 105 s abgebrochen"), (401, "Completion API"), (403, "Completion API")):
            text, aufrufe = self.fehler(code)
            self.assertTrue(text.startswith(f"cloud_api_http_{code}:"), text)
            self.assertIn(teil, text)
            self.assertEqual(aufrufe, 1, "AM5-06: kein automatisches Wiederholen mit Inhalt")
            self.assertNotIn("test-key-not-real", text)

    def test_andere_codes_bleiben_wie_bei_anderen_anbietern(self):
        text, _ = self.fehler(500, b"boom")
        self.assertTrue(text.startswith("cloud_api_http_500:"))
        self.assertIn("boom", text)

    def test_kein_stilles_umschalten(self):
        router = ModelRouter()
        router.register(adapter())
        ersatz = mock.Mock()
        ersatz.id, ersatz.route = "nvidia", "cloud"
        router.register(ersatz)
        with mock.patch.object(cloud_api._OPENER, "open", side_effect=HTTPError(URL, 504, "x", None, io.BytesIO(b""))):
            with self.assertRaises(ModelAdapterError):
                router.choose("langdock").chat([{"role": "user", "content": "x"}])
        ersatz.chat.assert_not_called()


class Empfaenger(Wurzel):
    def test_ohne_eintrag_nicht_einschaltbar_und_der_rest_laeuft_weiter(self):
        cfg = {"enabled": True, "providers": {
            "langdock": {"enabled": True, "kind": "openai_compatible", "base_url": URL, "api_key": "secret://langdock/api-key", "default_model": "attrappe-eu"},
            "nvidia": {"enabled": True, "kind": "openai_compatible", "base_url": "https://x.test/v1", "api_key": "secret://nvidia/api-key", "default_model": "m"}}}
        aus = []
        adapters = build_cloud_adapters(cfg, environ=KEY, project_root=self.root, ausgelassen=aus)
        self.assertEqual([a.id for a in adapters], ["nvidia"])
        self.assertEqual(aus, [("langdock", "empfaenger_fehlt")])
        # ohne project_root gilt es genauso
        self.assertEqual([a.id for a in build_cloud_adapters(cfg, environ=KEY)], ["nvidia"])

    def test_vollstaendig_wird_gebaut_unvollstaendig_nicht(self):
        cfg = {"enabled": True, "providers": {"langdock": {"enabled": True, "kind": "openai_compatible", "base_url": URL,
                                                          "api_key": "secret://langdock/api-key", "default_model": "attrappe-eu"}}}
        self.schreibe("cloud_modelle.yaml", {"langdock": MODELL})
        self.schreibe("empfaenger.yaml", EMPFAENGER)
        adapters = build_cloud_adapters(cfg, environ=KEY, project_root=self.root)
        self.assertEqual([type(a).__name__ for a in adapters], ["LangdockAdapter"])
        self.assertTrue(adapters[0].health())
        kaputt = json.loads(json.dumps(EMPFAENGER))
        del kaputt["empfaenger"]["langdock"]["vertrag"]["fundstelle"]
        kaputt["empfaenger"]["langdock"]["unterauftragsverarbeiter"]["liste"] = []
        self.schreibe("empfaenger.yaml", kaputt)
        aus = []
        self.assertEqual(build_cloud_adapters(cfg, environ=KEY, project_root=self.root, ausgelassen=aus), [])
        self.assertEqual(aus[0][0], "langdock")
        self.assertIn("vertrag.fundstelle", aus[0][1])
        self.assertIn("unterauftragsverarbeiter", aus[0][1])

    def test_region_im_verzeichnis_und_alter(self):
        self.schreibe("empfaenger.yaml", EMPFAENGER)
        self.assertEqual(langdock.empfaenger_status(self.root, HEUTE)["status"], "ok")
        alt = langdock.empfaenger_status(self.root, datetime.date(2027, 12, 1))
        self.assertEqual(alt["status"], "alt")
        self.assertIn("Angaben prüfen", alt["hinweis"])
        self.assertEqual(langdock.einschaltpruefung(self.root, URL, datetime.date(2027, 12, 1)), [], "alt ist nur ein Hinweis")
        us = json.loads(json.dumps(EMPFAENGER))
        us["empfaenger"]["langdock"]["region"] = "us"
        self.schreibe("empfaenger.yaml", us)
        self.assertEqual(langdock.empfaenger_status(self.root, HEUTE)["status"], "unvollstaendig")

    def test_der_zustand_nennt_die_gruende(self):
        self.schreibe("cloud_providers.yaml", {"cloud_providers": {"enabled": True, "providers": {"langdock": {
            "enabled": True, "kind": "openai_compatible", "base_url": URL, "api_key": "secret://langdock/api-key", "default_model": "attrappe-eu"}}}})
        store = cloud_settings.CloudKeyStore(cloud_settings.key_store_path(self.root))
        p = cloud_settings.view(self.root, store, KEY)["providers"][0]
        self.assertEqual(p["status"], "nicht bereit")
        self.assertTrue(any("Empfängerverzeichnis" in r for r in p["reasons"]), p["reasons"])
        self.assertEqual(p["empfaenger"]["status"], "fehlt")
        self.schreibe("empfaenger.yaml", EMPFAENGER)
        p = cloud_settings.view(self.root, store, KEY)["providers"][0]
        self.assertEqual((p["status"], p["reasons"]), ("bereit", []))


class Inhaltsschutz(unittest.TestCase):
    def test_personenbezug_geht_nie_an_langdock(self):
        guard = ContentGuard(cloud_enabled=True)
        a = adapter()
        with mock.patch.object(cloud_api._OPENER, "open", side_effect=AssertionError("kein Netzaufruf")) as netz:
            with self.assertRaises(ContentGuardStop) as ctx:
                guard.call([{"role": "user", "content": "Kontakt: max.mustermann@example.com bitte antworten."}], model="attrappe-eu", route=a.route,
                           complete=lambda msgs: a.chat(msgs, model="attrappe-eu"))
        self.assertEqual(ctx.exception.result.status, "BLOCKED")
        netz.assert_not_called()
        self.assertEqual(a.route, "cloud")

    def test_ohne_personenbezug_geht_es_durch_den_schutz_zur_attrappe(self):
        eintraege = []
        audit = mock.Mock()
        audit.append.side_effect = lambda *a, **k: eintraege.append(a[0]) or {}
        guard = ContentGuard(audit=audit, cloud_enabled=True)
        a = adapter()
        with mock.patch.object(cloud_api._OPENER, "open", return_value=antwort("ok")):
            out = guard.call([{"role": "user", "content": "Schreibe ein Gedicht."}], model="attrappe-eu", route=a.route,
                             complete=lambda msgs: a.chat(msgs, model="attrappe-eu")["content"])
        self.assertEqual(out.status, "OK")

    def test_klassen_bleiben_unveraendert(self):
        from sedra_runtime.gateway import klassen
        self.assertFalse(klassen.RECHTSGRUNDLAGE_CLOUD)


class Kosten(unittest.TestCase):
    def test_euro_nur_mit_preis(self):
        usage = {"input_tokens": 1000, "output_tokens": 500}
        self.assertEqual(langdock.kosten_eur(MODELL, "attrappe-preis", usage), 0.007)
        self.assertIsNone(langdock.kosten_eur(MODELL, "attrappe-eu", usage), "ohne Preis nur Token")
        self.assertIsNone(langdock.kosten_eur(MODELL, "attrappe-preis", None))
        self.assertIsNone(langdock.kosten_eur({"m": {"preis_eur_je_million_token": {"eingabe": 1}}}, "m", usage))


class AdapterWahl(unittest.TestCase):
    def test_provider_adapter_nimmt_langdock_und_laesst_andere_unberuehrt(self):
        cfg = {"providers": {"langdock": {"kind": "openai_compatible", "base_url": URL, "api_key": "secret://langdock/api-key"},
                             "nvidia": {"kind": "openai_compatible", "base_url": "https://x.test/v1", "api_key": "secret://nvidia/api-key"}}}
        self.assertIsInstance(provider_adapter(cfg, "langdock"), langdock.LangdockAdapter)
        self.assertIs(type(provider_adapter(cfg, "nvidia")), cloud_api.CloudOpenAICompatibleAdapter)
        schlecht = {"providers": {"langdock": {"kind": "openai_compatible", "base_url": "https://api.langdock.com/openai/us/v1", "api_key": "secret://langdock/api-key"}}}
        with self.assertRaises(ValueError) as ctx:
            provider_adapter(schlecht, "langdock")
        self.assertIn("langdock_region_nicht_erlaubt", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
