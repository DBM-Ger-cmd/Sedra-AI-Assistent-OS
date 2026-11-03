# Konzept: Apps und Erweiterungen in SEDRA v1 (03.11.2026)

Stand des Codes: `main` c364081. Dieses Konzept ersetzt `docs/ENTWURF_APPS_MODELL_2026-11-03.md` als Grundlage; der Entwurf bleibt als Verlauf.
Die Bausteine stehen je in einem eigenen Spec (`docs/SPEC_APPS_v1_AM0_…` bis `…_AM8_…`, §11). Nichts davon ist gebaut. Stand 03.11.2026: alle Entscheidungen wie vorgeschlagen; AM0 und AM1 in **G2** (`SPEC_APPS_v1_AM0_G2.md`, `SPEC_APPS_v1_AM1_G2.md`).

Pfade ohne Vorsatz sind relativ zu `runtime/src/guppi_runtime/`. Zeilennummern gelten für c364081. Wo etwas nicht im Code gelesen wurde, steht das dabei.
Alles, was rechtliche Pflichten betrifft (DSGVO, EU-KI-Verordnung, Verträge), ist **Einordnung, keine Rechtsprüfung**.

---

## 1. Auftrag

Captain, 03.11.2026: Werkzeuge und Erweiterungen sollen einheitlich als **Apps** behandelt werden, die über ein **Manifest** mit Kern und Shell zusammenarbeiten.
Im Verlauf präzisiert:
1. **Vorbild Android**: ein Kern, darauf aufsetzende Apps, Berechtigungen je App.
2. Die Grundsatzfragen werden **in der Berechtigung jeder App** festgelegt, nicht einmal für alle.
3. **Shells dürfen eigene Apps haben**; eine App muss nicht in jeder Shell verfügbar sein – **außer den Grundfunktionen**, die überall gleich sein müssen. Die Liste der Grundfunktionen ist bestätigt.
4. Die **KMU-Shell** (Unternehmen: Dokumente, sichere KI-Umgebung für Beschäftigte) ist mitzudenken.
5. **Langdock** anbinden, beide Richtungen, zuerst als Modellquelle.
6. Genau und ausführlich, nichts erfinden, nichts beschönigen; auch Punkte einbeziehen, die noch nicht besprochen wurden; ein **ganzheitliches** Konzept, das Gutes übernimmt.

---

## 2. Bestandsaufnahme: was es heute gibt

### 2.1 SEDRA hat nicht einen, sondern acht Erweiterungswege

Sie sind nacheinander entstanden, jeder für seinen Zweck, jeder mit eigener Prüfung. Das ist der wichtigste Befund für ein ganzheitliches Konzept.

| Nr | Weg | Wo | Manifest / Form | Herkunft und Prüfung | Rechte | Gate beim Einbau |
|---|---|---|---|---|---|---|
| E1 | **UI-Werkzeuge** | `uix/tools/<id>/`, `local_config/tools/<id>/` | `tool.yaml` | Schema in `desk/gateway.py` `check_tool`; Durchsicht `desk/install.py:26` (Muster wie `eval`, `fetch`) | `api:`-Routenliste, `trust` | `install_module` (`uix_server.py:385ff`), Rechte `grant_module_write_routes` (`:1265ff`); daneben **Anlegen aus der Vorlage** ohne Gate (`module_scaffold`, `:598–660`: „Kein Gate: der Inhalt ist unsere eigene Vorlage“), Ergebnis `trust: CAPTAIN` in `local_config/` |
| E2 | **Shells** | `uix/shells/<id>/`, `local_config/shells/<id>/` | `shell.yaml` (Code oder Vorgabe) | `check_shell`; Vorgabe-Shells ohne Code (`gateway.py` `_check_frame_shell`) | `api:`, `provides` | wie E1 |
| E3 | **Kern-Erweiterungen des Desk** (Objekttypen, Verben) | `desk/extensions.py:3` `MODULES` | Python-Modul mit `register(registry, hub)` | nur Paket; beim Start eingefroren (`kinds_frozen`), Fehler → `DESK_KIND_REFUSED` | volle Rechte im Prozess | keins (Paketcode, Review) |
| E4 | **Architektur-Module, Dienste, Skills, Tools** | `architecture/…/core/registry/*.yaml`, `core/registry.py` | YAML je Komponente mit `core_contract` | Vertragsversion geprüft (`core/registry.py:11–14`) | aus der Architektur | keins (Paket) |
| E5 | **Selbst entwickelte Fähigkeiten (E1-Stufe)** | `capabilities/` | Python-Dateien | nur neue Dateien, nur nach Abnahme, Hashes (`selfdev/self_integration.py`, Kopf) | im Prozess | ja, je Übernahme und Rücknahme |
| E6 | **Agenten-Vorlagen** | `agent_manager/` (Register, Import) | Vorlage mit `permissions` | `agent_import.check_permissions` (`agent_manager/agent_import.py:126`): `network_mode` muss `deny` sein, kein `external_write`, kein `privileged`, Wirkungsklassen | `tools_allowed`, `workspace_mode`, `side_effect` | Import mit Vorprüfung; Lauf mit Gate (ARCHITEKTUR §5) |
| E7 | **Harness-Vorlagen** (Agenten im Gespräch) | `runtime/config/harness_vorlagen/*.yaml` | `harness_vorlage` mit `werkzeuge`, `rechte` (z. B. `bauagent.yaml:7–8`) | harter Vorbehalt: nur Claude/Captain ändern (`harness/vorbehalte.py`, Eintrag `runtime/config/harness_vorlagen/**`) | Werkzeugliste + Freigabe-Katalog | Änderung über Antrag mit Gate (Grenzen der Schleife) |
| E8 | **Daten-Erweiterungen**: Skill-Bibliothek, Cloud-Anbieter, Wissensquellen | `skill_library/`, `config/cloud_providers.yaml`, `wissen/` | Dateien / Konfiguration | Skills: nur Text, nie ausgeführt, verdächtige als `flagged` (`skill_library/__init__.py:8–10`); Anbieter: Schalter, Standard aus | keine eigenen Rechte (Daten) bzw. Netz über den Kern | Anbieter: Schalter; Wissensquellen: Freigabe (Antrag „Wissensquelle freigeben …“ erwähnt in `SPEC_UIX_STUFE6_RAHMEN_v1.md:17`, Befund C1; der Weg selbst nicht gelesen) |

Folgerung: Die Idee „alles ist eine App“ trifft heute nur E1 und E2. Ein ganzheitliches Konzept muss **die gemeinsame Sprache** für alle acht Wege liefern – ohne sie in eine Form zu zwingen, die nicht passt (Python im Prozess ist etwas anderes als ein abgeschottetes Fenster). §5 und Baustein AM8.

### 2.2 Fünf Vokabulare für Rechte und Wirkung

| Vokabular | Werte | Wo | Wofür |
|---|---|---|---|
| Guard-Entscheidung | `ALLOW`, `BLOCK`, `CAPTAIN_REQUIRED`; unbekannte Aktion → `CAPTAIN_REQUIRED` | `architecture/…/core/guard/guard_rules.yaml:4` | jede Aktion des Kerns |
| Permission-Stufen | 0 `READ_ONLY` … 6 `EXTERNAL_ACTION` | `runtime/config/permission_levels.yaml:7–14` | Obergrenze über dem Guard (Jobs) |
| Harness-Katalog | `frei`, `vorarbeiter`, `captain`, `verboten` | `harness/katalog.py:18` | Werkzeugaufrufe im Gespräch |
| Wirkungsklassen der Agenten | `read_only`, `proposal_only`, `preview`, `reversible_write`, `destructive_write`, `external_side_effect`, `privileged` | `agent_manager/agent_import.py:170–180` | Fähigkeiten einer Agenten-Vorlage |
| Vertrauen der Module | `CORE`, `CAPTAIN`, `GUPPI_BUILT`, `COMMUNITY` + Routenliste | `desk/gateway.py:50` | UI-Werkzeuge und Shells |

Keines davon ist falsch; sie beantworten verschiedene Fragen. Was fehlt, ist **eine Abbildung**, damit der Captain in einer App-Berechtigung dieselben Worte sieht wie in einer Agenten-Vorlage. Das Konzept führt deshalb keine sechste Sprache ein, sondern nimmt die **Wirkungsklassen der Agenten** (die genaueste Sprache, die es schon gibt) als gemeinsame Anzeigesprache und bildet die anderen darauf ab (§5.3). Der Guard bleibt, was er ist: die einzige Stelle, die entscheidet.

### 2.3 Was am App-Weg (E1/E2) schon gut ist und übernommen wird

| Bestand | Beleg | Bewertung |
|---|---|---|
| Manifest mit Schema, unbekannte Schlüssel abgewiesen | `gateway.py:63` `TOOL_KEYS`, `unknown_field` | übernehmen |
| Allowlist je Werkzeug, Server antwortet 403 und protokolliert | `uix_server.py:3561–3572`, Audit `UIX_TOOL_DENIED` | übernehmen, präzisieren (Verben) |
| **Abschottung aller Nicht-CORE-Werkzeuge im iframe ohne Token** | `uix/ui/loader.js:151, 164`; Brücke `uix/ui/bruecke.js`; Browser-Test `runtime/tests/test_stufe_c_rahmen.py` (laut `PLAN_STUFE_C` §10; Test selbst nicht gelesen) | übernehmen; Stärke des Bestands |
| Freigaben nie über ein Modul | `uix/ui/rahmen.js:59` (`decide` wirft); `bruecke.js:5` | übernehmen, unverrückbar |
| Einbau immer als `COMMUNITY`, egal was das Manifest sagt | `uix_server.py:396–400`, `:462–465` | übernehmen |
| Rechte-Erhöhung als Gate, gebunden an den Hash des Manifests | `uix_server.py:1265–1335` | verallgemeinern (AM3) |
| Release-Update nennt jede Rechteänderung eines Moduls einzeln und braucht Bestätigung genau dieser Liste | `update_anwenden.py:7–8, 89–115` | für App-Updates übernehmen (AM3) |
| Reservierte Ereignisse sendet nur der Strom | `uix/ui/bus.js:43–45`; `gateway.py` `events_emits_reserved` | übernehmen, um Klassen erweitern (AM3) |
| Vorgabe-Shells ohne eigenen Code | `gateway.py` `_check_frame_shell`, `FRAME_API` (`:68`) | **ausbauen**: einziger Weg für fremde Shells (AM0) |
| Externe Clients mit eigenem Token, nur `objects`/`actions` | `uix_clients.py:21–22`; Herkunft vom Server gesetzt (`desk/kinds.py:154`) | Grundlage für Dienste (AM4) |
| Inhaltsschutz am Modellaufruf, Regeln R-01 bis R-16, fail-closed | `core/content_guard.py`; `gateway/klassen.py:47–83` | Grundlage für Langdock (AM5/AM6) und KMU (AM7) |

### 2.4 Was fest verdrahtet ist oder fehlt

| Nr | Befund | Beleg |
|---|---|---|
| F1 | Die Taskleiste der Harness-Shell hat eine feste Zellenliste; Cockpit und Rahmen-Shells leiten ihre Leiste dagegen schon aus `kind: instrument` ab. | `shells/harness/taskleiste.js:15–16, 176–178` gegen `shells/cockpit/strip.js:16`, `ui/frame.js:146` |
| F2 | Orte stehen in zwei Listen (JS mit Wörtern und Objekt, Python nur Name und Hinweis), ein Test hält sie gleich. | `ui/places.js:14`, `chat_tools.py:108` |
| F3 | Werkzeuge können keine Orte, keine Shell-Bindung, keine Leistenzelle als Daten mitbringen. | `gateway.py:63` |
| F4 | Fremde Shells laufen **mit Code in der Seite**: Der Einbau nimmt Shells an, der Lader lädt Shell-Skripte unabhängig vom Vertrauen. `PLAN_STUFE_C` §7: „Shells bleiben Kern.“ | `uix_server.py:391`, `ui/loader.js:174`, `docs/PLAN_STUFE_C_2026-10-19.md` §7 |
| F5 | `uix/**`, `desk/gateway.py`, `desk/install.py`, `uix_server.py` sind keine harten Vorbehalte der Harness; ein Modell mit Schreibbereich `runtime/**` kann dort nach einer gewöhnlichen Karte schreiben. Ein Werkzeug im Paketordner ist `CORE` und läuft mit Seitenzugriff. | `harness/vorbehalte.py:10–31` |
| F6 | `GET /api/*` ist als Route zulässig; für `COMMUNITY` bleibt jede GET-Route erreichbar, die im Manifest steht. | `gateway.py:59, 137` |
| F7 | Die Rahmenseite bekommt dieselbe CSP wie die Shell (`connect-src 'self'`). | `uix_server.py:3686–3687, 3743` |
| F8 | Ereignisse gehen mit voller Nutzlast an jeden Rahmen, der sie in `listens` nennt; `decision.pending` trägt einen Titel bis 120 Zeichen. | `bruecke.js:91–97`; `uix_server.py:1184, 1505` |
| F9 | Kein Update-Weg für eingebaute Module (gleiche `id` → Fehler), keine Hash-Prüfung beim Laden. | `uix_server.py:404–406` |
| F10 | Der Gate-Text beim Einbau sagt „läuft in derselben Seite wie die Shell“ – seit Stufe C falsch. | `uix_server.py:415` |
| F11 | Einbau- und Rechte-Gates haben keine eigene Guard-Regel; sie laufen über `unknown_action: CAPTAIN_REQUIRED`. Ergebnis richtig, Absicht nicht ausgedrückt. | `guard_rules.yaml:4`; Aktionen `install_module`, `grant_module_write_routes` |
| F12 | Im Rahmen fehlen Design-Tokens der Seite; Tastatur und Fokus über die Rahmengrenze sind ein bekanntes Risiko; der Rahmen ist nur im Cockpit im Browser geprüft. | `PLAN_STUFE_C` §5, §10 „Bekannte Grenzen“ |
| F13 | Der Gateway-Vorgang kennt **keine Rollen** und **keinen echten Cloudweg**: verantwortlich ist „Nutzer“, Cloud nur `simuliert`, Rechtsgrundlage für Personenbezug in der Cloud fest `False`. | `gateway/vorgang.py:43, 48–49`; `gateway/klassen.py:19` |
| F14 | Die Abhängigkeiten einer Shell (Werkzeuge, Kern-Module, ui-Dateien) werden für den USB-Stick von Hand aufgezählt. | `docs/ENTSCHEIDUNGEN_USB_STICK.md:7–9` |
| F15 | Die Vertrauensstufe `GUPPI_BUILT` wird von **keinem** Code-Pfad vergeben. Der Vertrag sagt, ein von SEDRA gebautes Modul trage sie und komme über das Einbau-Gate (Vertrag §7.2–7.3); das Einbau-Gate setzt aber immer `COMMUNITY`. `GUPPI_BUILT` kommt im Code nur als zulässiger Wert vor. | `desk/gateway.py:50`; `uix_server.py:396–400`; Suche nach `GUPPI_BUILT` im Paket |
| F17 | **Testläufe umgehen alle Vorbehalte.** Der MasterChat darf in seiner Sitzung Tests und Code unter `runtime/**` schreiben und `run_tests` starten; der Lauf führt den Code auf dem Rechner aus (ohne VM), neue Testdateien werden mitgenommen. Dieser Code kann jede Datei schreiben, auch `core/**` und `uix/ui/**`. | `runtime/config/harness_vorlagen/masterchat.yaml:14–26`; `runtime/config/harness_laeufe.yaml` (`run_tests`); `harness/lauf_huelle.py:1–5`; `runtime/benchmarks/run_tests.py:32` |
| F18 | **Alle Freigabe-Wege außer der Konsole nimmt der Server mit dem Browser-Token an** (zehn Wege, F1–F10 in der Vorlage AM0-E1 §5b.2). Code in der Seite kann deshalb jede Freigabe erteilen, auch für Programme, Regeln und Datenabfluss. Einzige Ausnahme heute: `guppi approve` in der Konsole. | `uix_server.py:261–310, 2196–2213`; `harness/api.py:245`; `cli.py:316–324` |
| F16 | Einbau und Rechte-Erhöhung schreiben in die Manifestdatei des Moduls (`trust: COMMUNITY` bzw. `CAPTAIN`). Eine Hash-Prüfung nach dem Einbau muss das berücksichtigen; jede Erhöhung ändert den Hash. | `uix_server.py:462–466, 1324–1327` |

---

## 3. Leitbild: Android, übertragen und nicht kopiert

| Android | SEDRA | Abweichung mit Grund |
|---|---|---|
| Kernel und Systemdienste | **Kern**: Guard, Audit, Inhaltsschutz, Missionen/Entscheidungen, Desk, Token, Einbau | – |
| App-Sandbox je App | iframe `sandbox="allow-scripts"` ohne Token für jede Nicht-CORE-UI | Systemapps (CORE) laufen in der Seite; Abschottung auch für CORE wäre teuer (`PLAN_STUFE_C` §6.1 empfiehlt bewusst: CORE in der Seite). Die Grenze von CORE ist die **Herkunft**, deshalb muss die Herkunft geschützt werden (F5, AM0). |
| `AndroidManifest.xml` | `tool.yaml` (Version 1.1, §6) | – |
| Berechtigungen `normal` / `dangerous` / `signature` | Schutzstufen **A / B / C** | C wird nie an Apps vergeben, auch nicht auf Antrag |
| Laufzeit-Abfrage | Antrag mit **Gate im Posteingang** | ein Gate, kein Häkchen; gebunden an Manifest-Hash |
| Intents / Binder | Desk: `POST /api/objects`, `POST /api/actions` | Verben haben eigene Gates; eine App ist nur Antragsteller |
| Broadcasts mit Berechtigung | Ereignisstrom, Klassen `öffentlich` / `inhalt` | Apps senden nicht in den Kernstrom |
| Hintergrunddienste | **Dienste** außerhalb des Server-Prozesses (AM4) | fremder Code nie im Server-Prozess |
| Arbeitsprofil / Geräterichtlinie (Work Profile, Device Owner) | **Betreiber-Richtlinie** und Rollen (AM7) | – |
| Launcher, Hersteller-Oberflächen | **Shells** mit eigenen Apps (AM2) | Grundfunktionen überall gleich |
| Paketsignatur, Installer-Prüfung | Hashes im Gate, Herkunftsdatei, Prüfung beim Laden (AM0) | keine Signatur mit Schlüssel in v1 (offen, §12) |
| App-Store | **kein** Store | Quelle ist ein Ordner/Git-Klon mit Commit; der Captain/Betreiber sieht jede Datei |
| „Alle Berechtigungen“ | gibt es nicht | jede Fähigkeit einzeln |

---

## 4. Begriffe und Schichten

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ Apps (UI)        Fläche · Zelle · Ort        ── iframe für alles außer CORE             │
│ Apps (Dienst)    Prozess außerhalb des Servers, eigenes Token (AM4)                     │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ Shells           besitzen den Bildschirm; Code nur aus dem Paket, sonst Vorgabe (AM0)   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ Vertragscode     uix/ui: Lader, Brücke, Rahmen, Bus, api, Wechsel, Kernorte            │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ Kern             Desk (Objekte, Verben, Entscheidungen, Strom) · Guard · Audit ·        │
│                  Inhaltsschutz · Missionen · Token · Einbau/Berechtigung · Kern-Erw. E3 │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

- **App**: alles mit einem `tool.yaml`. Sie hat bis zu drei **Beiträge** zur Oberfläche: **Fläche** (Inhalt eines Reiters/Fensters), **Zelle** (Eintrag der Leiste), **Ort** (Name, Wörter, Gruppe im Start-Menü, in der Palette und im Chat). Ab AM4 kann sie stattdessen oder zusätzlich ein **Dienst** sein.
- **Grundfunktion**: eine Fähigkeit mit festem Kernweg, die jede Shell für die passende Rolle erreichbar machen muss – meist eine App des Pakets, in manchen Shells eine eigene Fläche (§7).
- **Kern-Erweiterung**: Python-Code im Server-Prozess (E3, E5). **Nie eine App von außen.** Eine App kann eine Kern-Erweiterung *benötigen* (`needs.kern`), aber nicht mitbringen.
- **Erweiterung** (Oberbegriff, AM8): alles aus E1–E8. Jede Erweiterung hat eine **Herkunft**, eine **Wirkungsklasse** je Fähigkeit und erscheint im **Verzeichnis**.
- **Captain**: heute der einzige Mensch im System. Ab AM7 gibt es Rollen: **Betreiber** (legt fest, gewährt), **Prüfung** (Datenschutz/Revision) und **Sachbearbeitung** (Beschäftigte, die arbeiten). Im Einzelplatzbetrieb ist der Captain alles zugleich.

---

## 5. Berechtigung: eine Sprache, vier Achsen, eine Regel

### 5.1 Die vier Achsen

1. **Vertrauen** (Herkunft): `CORE` (Paket), `CAPTAIN` (vom Captain selbst abgelegt oder aus der Vorlage angelegt), `GUPPI_BUILT` (von SEDRA gebaut, mit Spec und verstecktem Test, Vertrag §7 – heute von keinem Code-Pfad vergeben, F15, AM3-29), `COMMUNITY` (alles, was durch den Einbau kommt). Legt die **Abschottung** und die **Obergrenze** fest.
2. **Schutzstufe** der Fähigkeit: **A** normal, **B** gefährlich, **C** Kern. Legt fest, **wie** gewährt wird.
3. **Shell**: wo die App sichtbar ist (`shells:`). Sichtbarkeit, keine Sicherheitsgrenze.
4. **Rolle** (ab AM7): wer die App benutzen darf.

### 5.2 Die eine Regel

```
wirksam(Fähigkeit) = beantragt(Manifest)
                   ∩ gewährt(Captain bzw. Betreiber)
                   ∩ Obergrenze(Vertrauen)              ← Kerncode, nicht konfigurierbar
                   ∩ Richtlinie(Betreiber, ab AM7)      ← enger als Gewährung möglich, nie weiter
```
- Mehr beantragt als gewährt → die App **lädt nicht** (Grund in `rejected`), sie wird nicht still gekürzt.
- Gewährung gilt nur, solange der **Hash des Manifests** dem gewährten entspricht.
- Erhöhung ist ein Gate; Entzug ist sofort und ohne Gate (Audit).
- Der Guard entscheidet weiter jede Aktion. Eine gewährte App-Fähigkeit macht eine Aktion **nie** erlaubt, die der Guard sonst prüfen würde; sie öffnet nur den Weg, die Aktion zu **beantragen**.

### 5.3 Gemeinsame Wirkungsklassen (Anzeigesprache)

Übernommen aus den Agenten-Vorlagen (`agent_import.py:170–180`). Jede Fähigkeit jeder Erweiterung trägt genau eine. Die Schutzstufe folgt daraus.

| Wirkungsklasse | Bedeutung | Schutzstufe für Apps | Entspricht ungefähr (Anzeige, keine Gleichsetzung) |
|---|---|---|---|
| `read_only` | liest eigene Daten / öffentliche Zustände | A | Permission 0–1, Katalog `frei` |
| `proposal_only` | legt einen Vorschlag/Antrag an, ändert nichts | A | Antrag im Posteingang |
| `preview` | zeigt, was eine Handlung täte | A | Probe-Routen |
| `reversible_write` | ändert, mit Rückweg | B | Permission 2–4 mit Gate, Katalog `captain` |
| `external_side_effect` | wirkt außerhalb des Rechners (Netz, Cloud) | B | Permission 6, Grenze `netz` |
| `destructive_write` | ändert ohne vollständigen Rückweg | **nicht für Apps**; nur Kern-Verben mit eigenem Gate | Permission 4–5, Katalog `captain`/`verboten` |
| `privileged` | ändert Regeln, Rechte, Kern | C – nie | Guard `BLOCK` für `bypass_guard`, `modify_core_invariants` |

Hinweis zur Genauigkeit: Die Spalte „entspricht“ ist eine **Lesehilfe**. Die Permission-Stufen sind eine Obergrenze für Jobs, der Katalog stuft Werkzeugaufrufe im Gespräch ein; sie werden durch dieses Konzept nicht zusammengelegt (AM8 §Abgrenzung).

### 5.4 Schalter je App (aus der Diskussion, jetzt Teil der Berechtigung)

| Schalter | Werte | Schutzstufe | Werkseinstellung `COMMUNITY` (Vorschlag, Entscheidung AM3-E1) | Obergrenze im Kern |
|---|---|---|---|---|
| Aktivierung | aus / an | – (Klick, Audit) | aus | – |
| Zelle in der Leiste | nein / text | B | nein | nie Code in der Leiste |
| Ereignisse | je Name; Klasse `öffentlich` / `inhalt` | A / B | nur `öffentlich` | `inhalt` nur gefiltert |
| Dienst-Prozess | nein / Host / microVM | B | nein | Host nur `CAPTAIN`/`GUPPI_BUILT` |
| Lesen | eigene Typen / benannte fremde Typen | A / B | eigene | sensible Bereiche nie (AM0-03) |
| Verben | je `typ.verb` | B | keine | Verb behält sein Gate |
| Kern-Verben mit Außenwirkung | je Verb, z. B. `langdock_agent.fragen` (AM6) | B | keine | eine App hat selbst nie Netz (`connect-src 'none'`, AM0-04); hinaus geht nur der Kern durch den Inhaltsschutz |
| Ablage | eigene, Größe begrenzt | A | ja, 1 MB (Vorschlag) | nie fremde Ablage |

Schreiben in `uix/**` und andere Kernpfade ist **kein** Schalter einer App, sondern ein Vorbehalt des Projekts (AM0-01).

---

## 6. Manifest v1.1 (Überblick, verbindlich in den Bausteinen)

```yaml
tool:
  # --- bestehend (v1.0) ---
  id: rechnung                      # [a-z0-9-]{2,40}, = Ordnername, global eindeutig (auch über Shell-Ordner hinweg)
  name: "Rechnungen"
  description: "Rechnungen prüfen und ablegen."
  version: 1.2.0
  kind: object                      # object | instrument | panel | dienst (AM4)
  handles: [rechnung]
  order: 100
  slot: inhalt
  entry: {js: tool.js, css: tool.css}
  api: []                           # v1.1: für Nicht-CORE abgeleitet aus `rechte` (AM3); für CORE wie bisher
  events: {emits: [], listens: [system.state]}
  trust: CAPTAIN                    # Einbau setzt COMMUNITY
  tests: [test.spec.js]
  instanzen: eine
  gedaechtnis: [ablage]
  zweck: betrieb
  gruppe: arbeit                    # bestehend (Nachtrag N2)
  # --- neu ---
  shells: [harness, gateway-kmu]    # AM1: Verfügbarkeit; fehlt = alle Shells
  zelle: {feld: rechnungen, label: "Rechnungen", ort: rechnung}          # AM1
  ort: {id: rechnung, label: "Rechnungen", hint: "…", words: [rechnung], object: {type: rechnung, id: alle}, symbol: "▤"}   # AM2
  grundfunktion: null               # AM2: nur im Paket erlaubt; Wert = Name der Grundfunktion, z. B. logbuch
  rechte:                           # AM3: Antrag; gewährt wird außerhalb des Manifests
    lesen: [rechnung]
    verben: []
    ereignisse: [system.state]
    zelle: nein
    dienst: nein
    ablage: 1MB
  needs: {ui: ">=1.1 <2", apps: {gateway: ">=1.0 <2"}, kern: [gateway]}   # bestehend `ui`; neu `apps` (AM2), `kern` (AM8)
  rollen: [sachbearbeitung, pruefung]   # AM7, in AM2 nur im Schema vorgesehen
```

Was **nicht** im Manifest steht, weil der Autor es nicht bestimmen darf: Vertrauen nach dem Einbau, Herkunft (Quelle, Commit, Hashes), Gewährung, Aktivierung, Richtlinie. Diese Angaben schreibt der Kern in eigene Dateien unter `local_config/` (Vorbehalt `**/local_config/**`, `vorbehalte.py:11`).

---

## 7. Grundfunktionen (bestätigt) und Shells

**Liste** (vom Captain bestätigt, 03.11.2026): Entscheidungen/Posteingang · Gespräch · Aufgaben · Logbuch · Modus und Grenzen · Module und Berechtigungen · Einstellungen und Zustand.

Präzisierung aus dem Code: Nicht jede Grundfunktion ist heute ein Werkzeug. Die Harness-Shell hat ein **eigenes** Gespräch und eigene **Einstellungen** (`shells/harness/`), andere Shells nutzen das Werkzeug `talk`. Eine Grundfunktion ist deshalb eine **Fähigkeit der Oberfläche mit einem festen Kernweg**, nicht zwingend dasselbe Werkzeug:

| Grundfunktion | fester Kernweg (darf nicht nachgebaut werden) |
|---|---|
| Entscheidungen | `GET /api/decisions`, Antwort nur über `sedraStand.entscheiden` (`ui/stand.js:73`) |
| Gespräch | Modellaufruf nur über den Router mit Inhaltsschutz |
| Aufgaben | Desk-Objekte `task`/Harness-Aufgaben |
| Logbuch | Audit-Kette lesen, nie schreiben |
| Modus und Grenzen | `desk/boundaries.py`, Änderung nur als Antrag |
| Module und Berechtigungen | Einbau-, Rechte- und Aktivierungswege des Kerns |
| Einstellungen und Zustand | Schalter nur als Antrag; Zustand lesen |

Jede Shell **erklärt** in `shell.yaml` je Grundfunktion, wie sie erreichbar ist (Ort, Slot oder eigene Fläche); `uix_check` prüft es (AM2). Sichtbarkeit nach Rolle kommt mit AM7. Shells dürfen eigene Apps mitbringen (`uix/shells/<shell>/apps/<id>/`), fremde Shells nur als **Vorgabe ohne Code** (AM0).

---

## 8. Lebenszyklus einer App

```
Quelle (Ordner/Git) ─► Vorlegen (Gate: Dateien+Hashes+Rechte+Funde) ─► Eingebaut, aus
     ─► Aktivieren (Klick, Audit) ─► Geladen (Rahmen) ─► [Rechte-Antrag (Gate)] ─► …
     ─► Update vorlegen (Gate: Datei-Diff + Rechte-Diff) ─► alte Fassung läuft bis zur Freigabe
     ─► Entziehen (sofort) / Deaktivieren (sofort) / Entfernen (Audit, Ablage: behalten oder löschen)
```
Jeder Übergang hat ein Audit-Ereignis (Liste in AM3-27). Beim **Laden** prüft der Kern die Herkunft (Hashes) bei jeder `COMMUNITY`-App (AM0-02).

---

## 9. Daten, Ereignisse, Kommunikation

- **Ablage**: Heute trennt der Server die Ablage nach dem Kopf `X-SEDRA-Tool` (Vertrag §10.3; `uix_server.py` `ablage_lesen/schreiben`). Neu: Größengrenze je App, Export im Modul-Werkzeug, Wahl beim Entfernen (behalten/löschen), ab AM7 getrennt je Profil.
- **Ereignisse**: zwei Klassen. `öffentlich` = `system.state`, `model.changed`, `desk.resync`, `tools.refresh`, `slot.changed`. `inhalt` = alle anderen (u. a. `decision.*`, `task.changed`, `live.line`, `talk.context`, `object.open`, `agent.changed`, `issue.changed`, `budget.warning`, `desk.error`, `harness.*`). Für Rahmen-Apps filtert die Brücke Nutzlasten nach einer festen Schlüsselliste (AM3).
- **Senden**: Apps senden nie in den Kernstrom. Für Rahmen ist `emit` heute leer (`rahmen.js:49`); das bleibt so. Ein App-eigener Namensraum ist nicht vorgesehen (Abgrenzung AM3).
- **Handeln**: nur über Desk-Verben (`POST /api/actions`), Prüfung des Verbs gegen die Gewährung im Server (AM3), das Gate des Verbs bleibt.
- **Netz**: Apps haben kein Netz. Was nach außen geht, geht über den Kern und den Inhaltsschutz (AM5, AM6).

---

## 10. Was nie eine App sein darf

Guard und seine Regeln · Audit · Entscheidungen erteilen (Freigabe, Karten, Posteingang-Antwort) · Inhaltsschutz und Schutzkern `b6core` · Permission-Stufen, Vorbehalte, Freigabe-Katalog · Einbau, Vertrauensvergabe, Gewährung, Aktivierung · Manifestprüfung, Lader, Brücke, Rahmen, Bus · Token- und Client-Token-Vergabe · Schreiben in `local_config/` · Betreiber-Richtlinie · Rollenvergabe.
Eine App darf diese Dinge **anzeigen** (Logbuch, Posteingang als Grundfunktion des Pakets) und **beantragen**, nie ausführen oder ersetzen.

---

## 11. Bausteine

| Baustein | Spec | Inhalt in einem Satz | hängt ab von | Risiko |
|---|---|---|---|---|
| **AM0** | `SPEC_APPS_v1_AM0_HAERTUNG.md` | Lücken F4–F11 schließen, ohne neue Funktion | – | gering–mittel |
| **AM1** | `SPEC_APPS_v1_AM1_ZELLEN_UND_SHELLS.md` | Manifest v1.1 Grundform (`zelle`, `shells`), Harness-Leiste aus Manifesten | – | mittel (Anzeige) |
| **AM2** | `SPEC_APPS_v1_AM2_ORTE_UND_GRUNDFUNKTIONEN.md` | Orte aus Manifesten, Shell-eigene Apps, Grundfunktionen erklärt und geprüft | AM1 | mittel |
| **AM3** | `SPEC_APPS_v1_AM3_BERECHTIGUNG.md` | `rechte`, Gewährung, Aktivierung, Update mit Diff, Ereignisklassen, fremde Zellen, Berechtigungsseite | AM0 | mittel–hoch |
| **AM4** | `SPEC_APPS_v1_AM4_DIENSTE.md` | Dienste außerhalb des Prozesses; MCP-Zugang des Desk mit Berechtigung | AM3 | hoch |
| **AM5** | `SPEC_APPS_v1_AM5_LANGDOCK_MODELL.md` | Langdock als Cloud-Anbieter, EU fest, durch den Inhaltsschutz | Cloud-Schalter (besteht); für Gateway-Vorgänge: Beschluss KLA-O6/S6 | mittel–hoch |
| **AM6** | `SPEC_APPS_v1_AM6_LANGDOCK_AGENTEN.md` | SEDRA fragt Langdock-Agenten (ausgehend) als Kern-Verb | AM5, AM3 | hoch |
| **AM7** | `SPEC_APPS_v1_AM7_UNTERNEHMEN.md` | Rollen, Betreiber-Richtlinie, Profile, Verwaltung in der KMU-Shell | AM2, AM3 | hoch |
| **AM8** | `SPEC_APPS_v1_AM8_VERZEICHNIS.md` | ein Verzeichnis aller Erweiterungen (E1–E8), gemeinsame Wirkungsklassen, Auslieferungsprofile | AM3 | mittel |
| **AM9** (aufgenommen 03.11.2026) | Skizze in `SPEC_APPS_v1_AM0_E1_OBERFLAECHENCODE.md` §7 | Werkstatt und Betrieb trennen: SEDRA läuft aus einem freigegebenen Stand, Änderungen kommen nur über die Übernahme des Updaters; **mit G5** (Freigaben auf eigener Herkunft) | AM0 | hoch |

Reihenfolge-Vorschlag: AM0 und AM1 parallel → AM2 → AM3 → AM8 (Anzeige) und AM5 → AM4 → AM6 → AM7.
Begründung: AM0 ist Voraussetzung für alles mit fremdem Code; AM1/AM2 bringen sichtbaren Nutzen ohne neue Rechte; AM3 ist die Mitte; AM5 ist klein, wenn die Schnittstelle stimmt; AM7 ist der größte Schritt und braucht ein Konto-Modell, das es heute nicht gibt.

---

## 11a. Punkte, die bisher nicht besprochen waren und jetzt aufgenommen sind

| Punkt | Warum er dazugehört | Wo |
|---|---|---|
| Acht Erweiterungswege statt einem | „Alles ist eine App“ trifft heute nur zwei davon; ein ganzheitliches Konzept braucht eine gemeinsame Sicht | §2.1, AM8 |
| Fünf Rechte-Vokabulare | Der Captain sieht sonst je Stelle andere Wörter für dieselbe Wirkung | §2.2, §5.3, AM8 |
| Fremde Shells laufen mit Code in der Seite | Die Abschottung der Werkzeuge wäre über eine fremde Shell umgehbar | F4, AM0-06 |
| Das Modell kann Paketcode schreiben | Herkunft ist die einzige Grenze von CORE; Code in der Seite liest den Token und kann Freigaben selbst erteilen (`ui/api.js:6`) | F5, AM0-01, Vorlage AM0-E1 |
| Testläufe führen Modell-Code auf dem Rechner aus | umgeht alle Vorbehalte, nicht nur die der Oberfläche | F17, Vorlage AM0-E1 §5a.3, Maßnahme G4 |
| Werkstatt und Betrieb sind derselbe Ordner | SEDRA ändert sich selbst, während es läuft – für Oberfläche und Python | Vorlage AM0-E1 §3, AM9 |
| `GUPPI_BUILT` wird nie vergeben | Der Selbstbau-Weg des Vertrags (§7) endet heute als `COMMUNITY` | F15, AM3-29 |
| Rechte im Manifest gespeichert | Widerspricht jeder Hash-Prüfung | F16, AM3-05 |
| Gate-Texte und Guard-Regeln für den Einbau | Der Captain entscheidet auf Grundlage dieser Texte | F10, F11, AM0-07/08 |
| Design, Tastatur, Fokus im Rahmen | Fremde Apps sollen bedienbar und erkennbar sein | F12, AM3-19–22 |
| Leistung | Jede fremde App ist ein eigenes Dokument im Browser; die Harness begrenzt offene Apps auf 8 (`shells/harness/app.js:16`) | AM3-24 (unsichtbarer Rahmen nur bei Bedarf) |
| Ablage einer App: Größe, Export, Löschen beim Entfernen | Daten bleiben sonst unbemerkt liegen | §9, AM3-25 |
| Update mit Rückweg und Rechte-Diff | Der Release-Updater kann das schon; Apps nicht | AM3-13–15 |
| Auslieferungsprofile (USB-Stick) | Abhängigkeiten werden heute von Hand gesucht | F14, AM8-10–12 |
| MCP-Zugang ohne Einschränkung | „Zu konfigurieren gibt es nichts“ – jeder Prozess des Kontos kann ihn nutzen | AM4 Teil A |
| Fremde MCP-Server als Werkzeuge | neuer Angriffsweg über Werkzeugbeschreibungen | AM4 Teil C (zurückgestellt) |
| Betriebsart im Unternehmen | ohne sie ist jede Rollen-Technik geraten | AM7 §2 |
| Information der Beschäftigten, Nachweis für Prüfung | im Unternehmen Pflichtthema (rechtlich zu prüfen) | AM7-13/14 |
| Alte Routen als Hülle | Vertrag §10: alte Routen bleiben ein Jahr | AM3 §3 (Übergang `trust`) |

## 12. Offene Fragen und Grenzen dieses Konzepts

Entscheidungen, die vor dem jeweiligen Bau fallen müssen, stehen in den Specs (IDs `AMn-En`). Übergreifend offen:
1. **Signatur**: Reichen Hashes im Gate und Herkunftsdatei, oder braucht es signierte Pakete (Schlüssel, Verteilung, Widerruf)? Offen seit `PLAN_STUFE_C` §7. Vorschlag: v1 ohne Signatur, Hashes reichen für den Einzelplatz; für Unternehmen (AM7) neu bewerten.
2. **CORE in der Seite**: Bleibt die Entscheidung aus `PLAN_STUFE_C` §6.1 bestehen? Vorschlag: ja, dafür die Herkunft härten (AM0-01, AM0-02).
3. **Konto-Modell**: SEDRA kennt keine Benutzer (`gateway/vorgang.py:48`: „SEDRA kennt keine Rollen“). AM7 setzt eines voraus. Wie Anmeldung auf einem lokalen Rechner aussehen soll (Windows-Konto, eigene Anmeldung, ein Rechner je Person), ist **nicht entschieden** und in diesem Konzept nicht vorweggenommen.
4. **Rechtliche Einordnung** (KMU, Langdock): Fachleute. Das Regelwerk selbst sagt „Annahme des Teams, keine Rechtsprüfung“ (`gateway/klassen.py:8`).

Grenzen dieser Arbeit (ehrlich):
- Nicht gelesen: die Stufe-C-Tests im Einzelnen, `core/content_guard.py` im Einzelnen, `desk/actions.py`, `desk/gated.py`, `desk/objects.py`, `orchestra/`, `sandbox/`, `desk_mcp.py`, `devvm_mcp.py`, `state_mcp.py`, das Agenten-Register, die Harness-Shell außer den genannten Dateien, `uix/shells/_template/`. Wo eine Spec davon abhängt, steht es dort als Aufgabe für G2.
- Langdock: nur Suchauszüge, keine Volltexte (Domains in der Sitzung nicht erreichbar). Siehe AM5 §1.
- Aufwandsschätzungen in Tagen werden bewusst nicht gegeben; die Bausteine nennen Dateien und Tests, an denen sich der Aufwand ablesen lässt.

---

## 13. Getroffene Entscheidungen (Protokoll)

| Datum | Entscheidung | Quelle |
|---|---|---|
| 03.11.2026 | Werkzeuge und Erweiterungen als Apps mit Manifest | Captain |
| 03.11.2026 | Grundsatzfragen je App in der Berechtigung festlegen | Captain |
| 03.11.2026 | Vorbild Android: Kern + Apps | Captain |
| 03.11.2026 | Shells dürfen eigene Apps haben; Apps nicht überall verfügbar | Captain |
| 03.11.2026 | Ausnahme: Grundfunktionen in allen Shells gleich; Liste bestätigt | Captain |
| 03.11.2026 | KMU-Shell einbeziehen | Captain |
| 03.11.2026 | Langdock: beide Richtungen, zuerst Modellquelle | Captain |
| 03.11.2026 | Ausarbeitung als Gesamtkonzept mit Specs; Weiterarbeit ohne Langdock-Volltexte | Captain |
| 19.10.2026 | CORE-Werkzeuge bleiben in der Seite; Nicht-CORE im Rahmen | `PLAN_STUFE_C` §6, §10 |
| 03.11.2026 | Richtung 2a (Langdock-Agenten fragen) als **Kern-Verb** statt als Dienst-App. Grund: kein Netz in der microVM, keine Sicherheitsgrenze für Dienste auf dem Host, Schlüssel und Inhaltsschutz liegen im Kern (AM6 §1) | Vorschlag Claude, übernommen vom Captain |
| 03.11.2026 | **Alle Vorschläge** der Entscheidungstabellen AM0-E… bis AM8-E… übernommen (u. a. Vorbehalt für ganz `uix/**`, Werkseinstellung fremder Apps, Betriebsart A im Unternehmen, Langdock zuerst außerhalb des Gateway-Vorgangs) | Captain |
| 03.11.2026 | AM0 und AM1 in G2 bringen | Captain |
| 03.11.2026 | AM3-E1 (Werkseinstellung fremder Apps: nach dem Einbau aus, nur normale Rechte) ausdrücklich bestätigt | Captain |
| 03.11.2026 | AM0-E1 (Schutz des Oberflächen-Codes) **wieder offen**, zur Ausarbeitung zurückgegeben; Vorlage `SPEC_APPS_v1_AM0_E1_OBERFLAECHENCODE.md` (Vorschlag: gestuft hart/weich/frei; Baustein AM9 „Werkstatt und Betrieb trennen“) | Captain / Claude |
| 03.11.2026 | Auswirkungen „Kern-Verb statt Dienst-App“ für Langdock-Agenten beschrieben (AM6 §12) | Claude, auf Frage des Captains |
| 03.11.2026 | Restrisiko der gestuften Lösung nachgearbeitet (Vorlage AM0-E1 §5a): neuer Befund F17; Vorschlag „O3+“ mit Abnahme vor Wirkung (G2) und Ausführung von Modell-Code nur nach Sicht (G4, vorrangig) | Claude, auf Auftrag des Captains |
| 03.11.2026 | **G4 sofort, O3+ übernommen, AM9 mit G5 aufgenommen** | Captain |
| 03.11.2026 | Fall „bestätigter schädlicher Code erteilt Freigaben“ nachgearbeitet (Vorlage AM0-E1 §5b): Befund F18, Klassen H/N, Vorschlag G9 Bestätigung außerhalb des Browsers, G10 Kanal im Audit, G11 Vollständigkeitstest | Claude, auf Auftrag des Captains |
| 03.11.2026 | **G9, G10, G11 übernommen** (Klassen H/N als Grundlage von G9); G2 für G4 schreiben | Captain |
| 03.11.2026 | G4-E1 bis E4 übernommen, G4 bauen (G3) | Captain |
| 15.10.2026 | Fremdes Modul kommt als COMMUNITY mit Leserouten; Schreiben nur per Gate | `uix_server.py:1265` (Kommentar) |
