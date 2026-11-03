# SPEC Apps v1 – AM5: Langdock als Modellquelle (Richtung 1) (03.11.2026)

Status: **G1** (Anforderungen mit Entwurf), nichts gebaut. Teil von `docs/KONZEPT_APPS_UND_ERWEITERUNGEN_v1.md` §11. Captain 03.11.2026: Langdock in beiden Richtungen, **zuerst als Modellquelle**.
Ziel: SEDRA kann Modelle über Langdock aufrufen – über den vorhandenen Cloud-Zugang, mit fester EU-Region, durch den Inhaltsschutz, mit Empfängerangaben, die der Betreiber pflegt. **Langdock ist dabei keine App**, sondern ein Anbieter im Kern (Konzept §9: Apps haben kein Netz).
Pfade relativ zu `runtime/src/guppi_runtime/`, Zeilen für c364081.

## 1. Quellenlage zu Langdock (ehrlich)

Die Seiten von Langdock (`docs.langdock.com`, `langdock.com`) waren in dieser Sitzung **nicht abrufbar**. Alle Angaben unten stammen aus **Auszügen einer Websuche** zu den offiziellen Seiten (Chat-Completions, API-Einführung, Workspace-Einstellungen, DPA, Security, Terms; Stand 03.11.2026). Sie sind Anhaltspunkte, kein Beleg. **Vor G2 müssen sie im Volltext gelesen und die vertraglichen Punkte schriftlich bestätigt werden** (AM5-01).

| Thema | Laut Suchauszug |
|---|---|
| Schnittstelle | OpenAI-kompatibel: `https://api.langdock.com/openai/{region}/v1/chat/completions`, Modellliste `GET /openai/{region}/v1/models`, Bearer-Schlüssel; Region `eu`, `us`, `global`, muss zur Region des Modells passen |
| Nicht unterstützt | u. a. `n`, `service_tier`, `parallel_tool_calls`, `stream_options` |
| Zeiten/Fehler | 429 bei Überschreiten von Limits; nicht gestreamte Anfrage über 105 s → 504 |
| Schlüssel | persönlich oder Workspace-Schlüssel mit Scope „Completion API“ |
| Limits/Kosten | uneinheitlich: 500 Anfragen/min und 150.000 oder 60.000 Token/min; Standard-Monatslimit für Workspace-Schlüssel 100 € |
| Vertrag | DPA Teil der Nutzungsbedingungen, Langdock als Auftragsverarbeiter (Art. 28 DSGVO); Fassung 2.1 (September 2026) genannt; Löschung binnen 30 Tagen nach Vertragsende |
| Unterauftragsverarbeiter | Azure, AWS, Google Cloud, OpenAI, Mistral (EU-Region); Sentry, Cloudflare (US-Unternehmen, Verarbeitung in der EU); eigene Liste bei „global deployment“ (Verarbeitung auch in den USA möglich) |
| Training/Aufbewahrung | laut Langdock kein Training mit Kundendaten; Zero Data Retention mit OpenAI und Mistral; AWS Bedrock „none“; **Ausnahme**: Modelle mit „Extended data retention“ (Anthropic bis 30 Tage, unabhängig von Einstellungen) |
| Chatverläufe bei Langdock | Admin wählt 7 Tage bis „für immer“; ob **API-Anfragen** dort gespeichert werden: **nicht geklärt** |
| Audit-Log bei Langdock | 90 Tage, dann weg |
| Zertifizierungen | SOC 2 Typ II, ISO 27001 – nur Aussage von Langdock |

## 2. Befund im Code

| Nr | Befund | Beleg |
|---|---|---|
| B1 | Cloud-Zugang besteht: Adapter `openai_compatible` (`POST {base}/chat/completions`, `GET {base}/models`, `stream: false`) und `anthropic`. Nur https, keine Weiterleitung (Schlüssel würde sonst mitgenommen), Schlüssel nur als `secret://…` oder im Schlüsselspeicher. | `models/cloud_api.py:1–60, 153–170` |
| B2 | Nicht weitergereichte Optionen werden **laut abgelehnt**: `response_format`, `tools`, `stream_guard`. Weitergereicht: `temperature`, `max_tokens`, `top_p`. | `cloud_api.py:35–36` |
| B3 | Konfiguration `runtime/config/cloud_providers.yaml` (Standard alles aus; Hauptschalter + je Anbieter), überschrieben durch `local_config/cloud_providers.yaml`. Anbieter heute: `nvidia`, `openai`, `anthropic`. Zeitlimit Vorgabe 60 s. | `runtime/config/cloud_providers.yaml:13–40`; `cloud_settings.py:1–4` |
| B4 | Eine Änderung der `base_url` ist ein **Antrag mit Gate** („der API-Schlüssel dieses Anbieters geht danach an diesen Host“, wirkt nach Neustart). | `uix_server.py:2673–2703` |
| B5 | Module können einem Anbieter und Modell zugeordnet werden (`module_models`); ein unbekannter Anbieter zählt nicht, kein stilles Umschalten. | `cloud_settings.py:137–145` |
| B6 | Jeder Cloud-Aufruf geht durch den Inhaltsschutz (`route = "cloud"`); Personenbezug verlässt den Rechner nicht, weil `RECHTSGRUNDLAGE_CLOUD = False` fest im Code steht. | `cloud_api.py:4`; `gateway/klassen.py:19, 47–50` |
| B7 | Der **Gateway-Vorgang** (KMU-Ablauf) kennt nur den Weg `simuliert`; „ein echter Cloudweg ist ein eigener Beschluss (KLA-O6) und ein eigener Build (S6)“. | `gateway/vorgang.py:43, 49`; `docs/SPEC_EIN_SICHERER_WEG_v1.md` (S6 „PROPOSED“) |
| B8 | Ob `cloud_settings.save` neue Anbieter-IDs (z. B. `langdock`) annimmt oder nur bekannte, wurde nicht gelesen (`cloud_settings.py:205`). | – |

## 3. Anforderungen

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| AM5-01 | **Vorbedingung G2**: Volltexte der Langdock-Seiten gelesen; schriftliche Bestätigung von Langdock zu: Speicherung von API-Anfragen (Ort, Dauer), Liste der EU-Modelle mit Zero Data Retention, gültige Rate-Limits, gültige DPA-Fassung und Unterauftragsverarbeiter. Ergebnis als Anhang dieser Spec. | Dokument |
| AM5-02 | Anbieter-Eintrag `langdock` im Paket (`runtime/config/cloud_providers.yaml`), **aus**: `kind: openai_compatible`, `base_url: https://api.langdock.com/openai/eu/v1`, `api_key: secret://langdock/api-key`, `default_model: null`, `timeout_s: 100`. | Konfig-Test |
| AM5-03 | **Region fest**: Für `langdock` lässt der Kern nur `base_url` aus einer festen Liste zu: `https://api.langdock.com/openai/eu/v1` und – nach eigener Entscheidung AM5-E3 – eine dedizierte Adresse des Betreibers mit Pfad `…/api/public/openai/eu/v1`. `…/us/…` und `…/global/…` → `langdock_region_nicht_erlaubt`. Die Prüfung sitzt im Kern, nicht in der Oberfläche; der bestehende Gate-Weg für `base_url` (B4) bleibt zusätzlich. | Test |
| AM5-04 | **Modellliste des Betreibers**: `local_config/cloud_modelle.yaml` mit `langdock: {<modell>: {aufbewahrung: keine|<tage>, geprueft_am, quelle}}`. Nur dort eingetragene Modelle sind wählbar; Modelle mit `aufbewahrung` ≠ `keine` brauchen zusätzlich `erlaubt_trotz_aufbewahrung: true`. Der Abgleich mit `GET /models` zeigt Modelle, die Langdock anbietet, aber nicht eingetragen sind, als „nicht geprüft“. | Test |
| AM5-05 | **Nicht unterstützte Optionen** (laut Auszug `n`, `service_tier`, `parallel_tool_calls`, `stream_options`) werden nie gesendet; der Adapter sendet ohnehin nur `model`, `messages`, `stream`, `temperature`, `max_tokens`, `top_p` (B2). Test hält das fest. | Test |
| AM5-06 | **Fehler**: 429 → Satz „Langdock: Limit erreicht (Anfragen oder Token je Minute) – später erneut versuchen“, kein automatisches Wiederholen mit Inhalt; 504 → „Langdock hat nach 105 s abgebrochen – kürzere Anfrage oder anderes Modell“; 401/403 → „Schlüssel ungültig oder ohne Scope ‚Completion API‘“. | Test mit Fake-Server |
| AM5-07 | **Kein stilles Umschalten**: Fällt Langdock aus, wechselt SEDRA weder auf einen anderen Anbieter noch auf ein lokales Modell; der Aufruf scheitert mit Satz (bestehendes Verhalten B5 festhalten). | Test |
| AM5-08 | **Empfängerverzeichnis**: `local_config/empfaenger.yaml` mit je Anbieter: Name, Rolle (Auftragsverarbeiter), Vertrag (Fassung, Datum, Fundstelle), Unterauftragsverarbeiter (Liste, Datum), Region, Aufbewahrung, Zweck, gepflegt von, geprüft am. Ohne Eintrag lässt sich ein Anbieter nicht einschalten (`empfaenger_fehlt`). Älter als 12 Monate → Hinweis „Angaben prüfen“. Sichtbar in der Grundfunktion „Einstellungen und Zustand“ und im Verzeichnis (AM8). | Test |
| AM5-09 | **Inhaltsschutz unverändert**: Personenbezug (R-01) und alle `nie`-Kategorien verlassen den Rechner nicht; `RECHTSGRUNDLAGE_CLOUD` bleibt `False`. Diese Spec ändert `gateway/klassen.py` nicht. | Test: Anfrage mit Name/E-Mail an Langdock wird lokal gesperrt, kein Netzaufruf |
| AM5-10 | **Gateway-Vorgang**: Der Weg `cloud` im KMU-Ablauf bleibt `simuliert`, bis KLA-O6/S6 beschlossen und gebaut ist. Langdock wird dort erst danach wählbar. Bis dahin ist Langdock nur für Aufrufe außerhalb des Gateway-Vorgangs nutzbar (z. B. `module_models`, KI-Labor). | Test |
| AM5-11 | **Kosten**: SEDRA zählt Token je Anbieter und Modell aus der Antwort (`usage`, `normalize_usage`, `cloud_api.py:17`) und zeigt sie im Meter. Ein Monatsbudget in Euro ist nur möglich, wenn der Betreiber Preise je Modell einträgt (`cloud_modelle.yaml`); ohne Preise zeigt SEDRA nur Token. | Test |
| AM5-12 | **Schlüssel**: ein Workspace-Schlüssel des Betreibers mit Scope „Completion API“, kein persönlicher Schlüssel; gespeichert wie bei anderen Anbietern (Umgebung oder Schlüsselspeicher, DPAPI). Im Unternehmen (AM7) darf nur der Betreiber ihn setzen. | Test |
| AM5-13 | **Tests ohne Netz**: Fake-Server für `/models` und `/chat/completions`; keine echten Schlüssel, keine echten Daten im Repo. | CI |

## 4. Entwurf

```yaml
# runtime/config/cloud_providers.yaml (Ergänzung)
    langdock:
      enabled: false
      kind: openai_compatible        # Langdock: OpenAI-kompatibel (laut Doku, vor G2 im Volltext prüfen)
      base_url: https://api.langdock.com/openai/eu/v1
      api_key: secret://langdock/api-key
      default_model: null
      timeout_s: 100                 # Langdock bricht nicht gestreamte Anfragen nach 105 s ab
```
- Regionsprüfung: Funktion `anbieter_url_erlaubt(provider, url)` in `cloud_settings.py`, aufgerufen beim Laden und beim Antrag (B4).
- Modellliste und Empfängerverzeichnis: zwei kleine YAML-Dateien unter `local_config/` (Vorbehalt), gelesen vom Kern, geändert nur als Antrag mit Gate (Muster `base_url`).

## 5. Tests und Abnahme

`tests/test_apps_am5_langdock.py` (Region, Modelle, Fehler, Optionen, kein Umschalten, Empfänger), Test des Inhaltsschutzes mit Personenbezug (kein Aufruf). Abnahme am PC mit einem Test-Workspace des Betreibers: Modellliste lesen, eine Anfrage ohne Personenbezug, eine mit Personenbezug (muss gesperrt werden), Anzeige der Token.

## 6. Rückfall

Anbieter-Schalter aus (Standard). Hauptschalter Cloud aus.

## 7. Abgrenzung

Kein echter Cloudweg im Gateway-Vorgang (B7). Keine Agenten (AM6). Keine Änderung am Regelwerk. Kein Streaming (der Adapter sendet `stream: false`; Streaming wäre eine eigene Änderung am Adapter).

## 8. Risiken

- Daten verlassen den Rechner. Der Schutz kommt vom Inhaltsschutz in SEDRA, nicht von Langdock.
- Angaben von Langdock können sich ändern (DPA-Fassung, Unterauftragsverarbeiter, Modelle); das Verzeichnis hat deshalb ein Datum und erinnert nach 12 Monaten.
- Das Zeitlimit von 100 s ist knapp unter dem Abbruch bei Langdock; lange Antworten scheitern. Streaming wäre die Lösung, ist aber nicht Teil dieses Bausteins.

## 9. Entscheidungen des Captains

| Nr | Frage | Vorschlag |
|---|---|---|
| AM5-E1 | Langdock zuerst nur außerhalb des Gateway-Vorgangs (Labor, Modulzuordnung)? | ja; Gateway erst nach KLA-O6/S6 |
| AM5-E2 | Modelle mit verlängerter Aufbewahrung grundsätzlich sperren? | ja, Freischaltung nur mit eigenem Eintrag |
| AM5-E3 | Dedizierte Langdock-Adresse (eigene Domain) zulassen? | erst wenn ein Kunde sie hat; dann eigene Entscheidung |
| AM5-E4 | Wer pflegt das Empfängerverzeichnis im Einzelplatz? | der Captain |

## 10. Berechtigungen vorab

Schreiben `runtime/config/cloud_providers.yaml`, `cloud_settings.py`, `models/cloud_api.py` (nur Fehlertexte, falls nötig), neue Vorlagen `runtime/config/cloud_modelle.beispiel.yaml`, `runtime/config/empfaenger.beispiel.yaml`, Tests. Nicht: `gateway/klassen.py`, `local_config/` auf dem PC, echte Schlüssel.

## 11. Nächste Gates

AM5-01 erledigen → G2 → G3 → G4 am PC mit Test-Workspace.
