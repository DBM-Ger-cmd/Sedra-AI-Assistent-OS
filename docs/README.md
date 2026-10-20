# Dokumentation von SEDRA (GUPPI OS) – Übersicht

Stand 20.10.2026 (geändert 20.10.2026, Linie L6). Diese Seite hat zuerst zwei Listen: **Was gilt** und **Historie**. Danach folgt die ausführliche Übersicht nach Themen. Keine Datei wurde verschoben.

## Was gilt

**Kerndokumente** (auf Stand 20.10.2026): [ARCHITEKTUR.md](ARCHITEKTUR.md) · [BETRIEB.md](BETRIEB.md) · [ENTWICKLUNG.md](ENTWICKLUNG.md) (mit der einheitlichen Linie L1 bis L7) · [MODELLE.md](MODELLE.md) · [CHANGELOG.md](CHANGELOG.md) · [LOGBUCH_AGENT_MANAGER.md](LOGBUCH_AGENT_MANAGER.md)

**Verträge und Regelwerke:** [SHELL_WERKZEUG_VERTRAG_v1.md](SHELL_WERKZEUG_VERTRAG_v1.md) · [COCKPIT_MODUL_v1.md](COCKPIT_MODUL_v1.md) · [JOB_SUPERVISOR_CONTRACTS.md](JOB_SUPERVISOR_CONTRACTS.md) · [CONTEXT_MANAGER_CONTRACTS.md](CONTEXT_MANAGER_CONTRACTS.md) · [REGELWERK_STANDARDLAEUFE.md](REGELWERK_STANDARDLAEUFE.md) · [AUFTRAGSSTRUKTUR.md](AUFTRAGSSTRUKTUR.md) · [TESTLAB.md](TESTLAB.md) · [SOLO_WORKFLOW.md](SOLO_WORKFLOW.md) · [MCP_SERVER_DEVVM.md](MCP_SERVER_DEVVM.md)

**Aktuelle Specs und Analysen:** [SPEC_AGENTEN_ORCHESTRIERUNG_v1.md](SPEC_AGENTEN_ORCHESTRIERUNG_v1.md) (Specs 0 bis 6, Entscheidungen des Captains) · [ANALYSE_BAUABLAUF_2026-10-20.md](ANALYSE_BAUABLAUF_2026-10-20.md) · [SPEC_EIN_SICHERER_WEG_v1.md](SPEC_EIN_SICHERER_WEG_v1.md) · [SPEC_GATEWAY_VORGANG_v1.md](SPEC_GATEWAY_VORGANG_v1.md) · [SPEC_GATEWAY_ARBEITSSTRECKE_2026-10-19.md](SPEC_GATEWAY_ARBEITSSTRECKE_2026-10-19.md) · [SPEC_SHELL_AUS_VORGABE_v1.md](SPEC_SHELL_AUS_VORGABE_v1.md) · [SPEC_SHELL_E_UND_MODULE_v1.md](SPEC_SHELL_E_UND_MODULE_v1.md) · [PLAN_ISOLATION_UND_UPDATE_2026-10-19.md](PLAN_ISOLATION_UND_UPDATE_2026-10-19.md) · [PLAN_STUFE_C_2026-10-19.md](PLAN_STUFE_C_2026-10-19.md)

**Jüngste Reviews und Berichte (Stand 19./20.10.):** [REVIEW_ARCHITEKTUR_2026-10-19.md](REVIEW_ARCHITEKTUR_2026-10-19.md) · [REVIEW_GESAMT_2026-10-19.md](REVIEW_GESAMT_2026-10-19.md) · [PRUEFBERICHT_KI_GATEWAY_KMU_2026-10-20.md](PRUEFBERICHT_KI_GATEWAY_KMU_2026-10-20.md) · [SEDRA_KERN_UND_KMU_SHELL_TECHNIK_2026-10-20.md](SEDRA_KERN_UND_KMU_SHELL_TECHNIK_2026-10-20.md) · [SHELL_TRANSLATOR_TECHNIK_2026-10-20.md](SHELL_TRANSLATOR_TECHNIK_2026-10-20.md)

## Historie

Beschreibt den Stand des jeweiligen Tages; wo es dem Obigen widerspricht, gilt das Obige.

- **Builds:** `BUILD_*` (Builds 2 bis 24, zuletzt [BUILD_20_FEINSCHLIFF_2026-10-19.md](BUILD_20_FEINSCHLIFF_2026-10-19.md) = Build 25 im Changelog) und [BUILD_2026-10-14.md](BUILD_2026-10-14.md); `TICKET_B6-G-*`
- **DevVM-Aufbau:** `DEVVM_AUFTRAG`, `DEVVM_PHASE0..5_BERICHT`, `PHASE0..9_STATUS`, `PHASE8F_LLAMA_SERVER`, `REAL_RUN_STATUS`, `SANDBOX_BOUNDARY_STATUS`
- **Entwürfe (`*_PROPOSED`):** [OFFENE_PUNKTE_GUPPI_B20_2026-10-15_PROPOSED.md](OFFENE_PUNKTE_GUPPI_B20_2026-10-15_PROPOSED.md), [PLAN_UND_PROMPT_SEDRA_ALS_GATEWAY_ASSISTENT_2026-10-15_PROPOSED.md](PLAN_UND_PROMPT_SEDRA_ALS_GATEWAY_ASSISTENT_2026-10-15_PROPOSED.md), [REGELWERK_DATENKATEGORIEN_CLOUDSPERRE_v0.1_2026-10-15_PROPOSED.md](REGELWERK_DATENKATEGORIEN_CLOUDSPERRE_v0.1_2026-10-15_PROPOSED.md), [REGISTER_NACHTRAG_v1.3.21_PROPOSED.md](REGISTER_NACHTRAG_v1.3.21_PROPOSED.md)
- **Ältere Reviews, Messungen, Recherchen, Pläne:** siehe die Abschnitte unten; dazu [historie/](historie/README.md) (v1.2 bis v1.20) und die Ordner `entwickler_archiv_*`

---

**Neu hier? Diese vier Dokumente zuerst lesen** (gültiger Stand):

| Dokument | Inhalt |
|---|---|
| [ARCHITEKTUR.md](ARCHITEKTUR.md) | Aufbau: Kern, Jobs, Modelle, Selbstentwicklung, Agent Manager, Oberfläche, Ordner |
| [BETRIEB.md](BETRIEB.md) | Einrichtung, Start, Konfiguration, Rezepte, GPU-Lease und Canary, Tests, Befehle, Störungen |
| [ENTWICKLUNG.md](ENTWICKLUNG.md) | Wie GUPPI baut (Specs, versteckte Tests, devvm_build), Erkenntnisse, **Regeln für alle Sitzungen** |
| [MODELLE.md](MODELLE.md) | Welches Modell welche Rolle hat, mit Messwerten; ausführlich in [MODELLVERGLEICH_2026-10-12.pdf](MODELLVERGLEICH_2026-10-12.pdf) |

Laufendes Protokoll aller Schritte: **[LOGBUCH_AGENT_MANAGER.md](LOGBUCH_AGENT_MANAGER.md)**.

Die übrigen Dokumente sind datierte Berichte, Pläne und Messungen. Sie beschreiben ihren Stand vom angegebenen Tag; wo sie dem gültigen Stand oben widersprechen, gilt der.

## Gültige Fachdokumente

| Dokument | Thema |
|---|---|
| [SOLO_WORKFLOW.md](SOLO_WORKFLOW.md) | Solo-Workflow des Coders im Detail |
| [TESTLAB.md](TESTLAB.md) | GPU-Lease und Ergebnis-Datenbank |
| [JOB_SUPERVISOR_CONTRACTS.md](JOB_SUPERVISOR_CONTRACTS.md), [CONTEXT_MANAGER_CONTRACTS.md](CONTEXT_MANAGER_CONTRACTS.md) | Verträge von Job Supervisor und Context Manager |
| [MCP_SERVER_DEVVM.md](MCP_SERVER_DEVVM.md) | MCP-Server für einen DevVM-Arbeitsordner |
| [UIX_ROADMAP.md](UIX_ROADMAP.md) | Pläne für die Oberfläche (Stand 04.10., Nachtrag 13.10.) |
| [ABGLEICH_UEBERGABEPAKET_SEDRA_2026-10-14.md](ABGLEICH_UEBERGABEPAKET_SEDRA_2026-10-14.md) | Übergabepaket SEDRA (Gesprächskonsolidat) gegen den Code von v1.20 geprüft: Begriffe, Statusmatrix, überholte Punkte, Anschluss an die UIX-Roadmap |
| [CHANGELOG.md](CHANGELOG.md) | Builds mit Nummer (ab 14.10.), was je Build dazukam; Paket mit `benchmarks/make_build.py` |
| [HARDENING_2026-10-14.md](HARDENING_2026-10-14.md) | Härtungsrunde auf dem Build: geprüfte Flächen, sechs Änderungen (Geheimnis-Sperre, Audit, Timeout, Fehlerbehandlung), offene Punkte |
| [BUILD_16_INHALTSSCHUTZ_2026-10-15.md](BUILD_16_INHALTSSCHUTZ_2026-10-15.md) | Build 16: der Inhaltsschutz im Kern – jeder Modellaufruf geprüft, Entscheidungen in der einen Liste, Audit ohne Text, Schärfe aus dem Modus; was bewusst noch fehlt |
| [SPEC_EIN_SICHERER_WEG_v1.md](SPEC_EIN_SICHERER_WEG_v1.md) | Spec: ein sicherer Weg – was SEDRA vom KI GateWay lernt und im Kern bekommt (S1–S7), wie das GateWay darauf sitzt (G1–G6), Bauplan Builds 16–18 |
| [BUILD_19_GATEWAY_2026-10-15.md](BUILD_19_GATEWAY_2026-10-15.md) | Build 19: das KI GateWay in SEDRA – Studio Flow, Schutzklassen und Matrix, Freigabe als Gate, Rechecks, Entwürfe mit Löschdatum, Shell „KI GateWay Studio“ |
| [BUILD_19_GUPPI_BEWEGT_SICH_2026-10-15.md](BUILD_19_GUPPI_BEWEGT_SICH_2026-10-15.md) | Build 19b (parallel, in Build 20 zusammengeführt): GUPPI öffnet Fenster und schlägt Handlungen als Knopf vor; Minimal mit Rückweg zur Übersicht, Bildzeichen und eigener Ablage |
| [SPEC_GATEWAY_VORGANG_v1.md](SPEC_GATEWAY_VORGANG_v1.md) | Spec: der GateWay-Vorgang in SEDRA – was die V4-Akte entscheidet, die 13 Merkmale, die Matrix, die vier Stationen, was MVP 1 nicht tut |
| [BUILD_18_START_SEDRA_2026-10-15.md](BUILD_18_START_SEDRA_2026-10-15.md) | Build 18: START_SEDRA (Übersicht, direkt in eine Shell, --gewaehlt), Befund zur „alten Oberfläche“, GUPPI XP als Wahl im Einstieg |
| [BUILD_17_SHELL_CREATOR_2026-10-15.md](BUILD_17_SHELL_CREATOR_2026-10-15.md) | Build 17: der Shell-Creator – Schema-Zwang am Router, der Rahmen aus Vorgabe (drei Formen 27/27 ohne Shell-Code), Satz an GUPPI oder Vorlage → Skizze → anlegen |
| [RECHERCHE_SHELL_CREATOR_2026-10-15.md](RECHERCHE_SHELL_CREATOR_2026-10-15.md) | Recherche: Shell-Creator mit lokalem Modell – 19 Repos bewertet, kein Einbau, drei Muster (Katalog statt Code, Schema-Zwang, Layout-Modell), drei Empfehlungen |
| [SPEC_SHELL_AUS_VORGABE_v1.md](SPEC_SHELL_AUS_VORGABE_v1.md) | Spec: eine Shell aus einer Vorgabe – Anordnung beschreiben statt programmieren; Rahmen im Vertrag; offene Frage ans Ersetzen |
| [ABNAHME_EXTERNE_LIEFERUNG_KI_GATEWAY_2026-10-15.md](ABNAHME_EXTERNE_LIEFERUNG_KI_GATEWAY_2026-10-15.md) | Die erste Lieferung von außen durch das Gate: zwei Vertragsbefunde (eigene Objekttypen, Vertrauen aus der Datei), was fehlt, die zwei Wege |
| [UEBERARBEITUNG_2026-10-15.md](UEBERARBEITUNG_2026-10-15.md) | Überarbeitung von Modul und drei Shells: Logikfunde (darunter die tote Shell-API an der Werkbank des Cockpits), Bedienwege mit echten Klicks, Stilaufwertung über Token |
| [SPEC_SHELL_E_UND_MODULE_v1.md](SPEC_SHELL_E_UND_MODULE_v1.md) | Spec der zweiten Shell (E, Minimal) und des Werkzeugs „Module“; §4 hält fest, was die zweite Shell über den Vertrag gelernt hat |
| [HARDENING_2026-10-14_BUILD9.md](HARDENING_2026-10-14_BUILD9.md) | Zweite Härtungsrunde, auf der Fläche von Build 7–9: Verknüpfungen beim Einbau, Durchsicht hinter Blockkommentaren, Hash nach dem Kopieren, Verfall der Einmal-Erlaubnis |
| [BUILD_2026-10-14.md](BUILD_2026-10-14.md) | Build vom 14.10.: Zusammenführung PC-Stand (Buildflow) + UIX-Arbeit, Prüfungen, bekannte Umgebungsabweichungen |
- `UIX_2_KONZEPT.md` – Entwurf für den Neubau der Oberfläche: ein Gespräch, ein Arbeitsplatz, ein Pult; Aufgaben statt Karten; Mensch nur an bleibenden Stellen; Ökosystem aus Werkzeug-Repos (Vorbild ArtCraft).
- `UIX_KOMMANDODECK_v1.md` – Konzept Build 5: Deck, Kommando (Strg+K), Werkstatt-Leiste, Organigramm, Erscheinungsbild; Paperclip als Vorbild, nicht Einbau.
| [SHELL_WERKZEUG_VERTRAG_v1.md](SHELL_WERKZEUG_VERTRAG_v1.md) | **Der Vertrag**: was eine Shell und ein Werkzeug dürfen und müssen (Manifeste, Lebenszyklus, Bus, Server, Desk §10, Reihenfolge §9) |
| [COCKPIT_MODUL_v1.md](COCKPIT_MODUL_v1.md) | Die festgelegte Form der ersten Shell: Zonen, 11 Regeln, Dock in der Shell, Gegenentwürfe D/E |
| [UIX_2_RICHTUNG_C.md](UIX_2_RICHTUNG_C.md) | Herleitung der Richtung C, Logikprüfung L1–L8, Modus und Grenzen, Vorlagen |
| [STAERKEN_INVENTUR_2026-10-14.md](STAERKEN_INVENTUR_2026-10-14.md) | S1–S12: welche Stärken der Runtime sichtbar werden müssen |
| [BUILD_9_GRENZEN_2026-10-14.md](BUILD_9_GRENZEN_2026-10-14.md) | Build 9: Modus und die vier Grenzen, Vorhaben, Installation fremder Module, Vorlagen für GUPPI |
| [BUILD_8_WERKBANK_2026-10-14.md](BUILD_8_WERKBANK_2026-10-14.md) | Build 8: Objektmodell, Verben, Live-Zeilen und die Werkbank-Werkzeuge (Kandidat, Tests, Live, Kosten) |
| [BUILD_7_DESK_2026-10-14.md](BUILD_7_DESK_2026-10-14.md) | Build 7: Andockstelle `desk/`, UI-Vertrag `uix/ui/`, Cockpit-Shell und die 16 Werkzeuge; Abnahme und was offen bleibt |
| [UIX_STYLE_MANIFEST_v0.2.md](UIX_STYLE_MANIFEST_v0.2.md) | Erscheinungsbild der Oberfläche, aus dem CSS abgeleitet: Charakter, Shell-Schichten, Tokens (Ist/Soll), Komponenten-Katalog, Zustandsfarben, Themes, Tickets |
| [UIX_ANALYSE_2026-10-13.md](UIX_ANALYSE_2026-10-13.md) | Durchsicht der Oberfläche im Browser: behobene Fehler, Vorschläge zur Weiterentwicklung |

## Reviews und Tests

| Datum | Dokument |
|---|---|
| 2026-10-12 | Review von `devvm_build`: im [Logbuch](LOGBUCH_AGENT_MANAGER.md) (Eintrag „REVIEW/HARNESS“) |
| 2026-10-11 | [REVIEW_2026-10-11.md](REVIEW_2026-10-11.md): Kern-Review |
| 2026-10-05 | [REVIEW_2026-10-05.md](REVIEW_2026-10-05.md): Code- und Sicherheitsreview · [TEST_REPORT_2026-10-05.md](TEST_REPORT_2026-10-05.md) · [TEST_LOG_2026-10-05.txt](TEST_LOG_2026-10-05.txt) |
| 2026-10-04 | [REVIEW_STRUCTURED_PROPOSAL_2026-10-04.md](REVIEW_STRUCTURED_PROPOSAL_2026-10-04.md): Vorschlag für ein unabhängiges Review |

## Modelle, Engine und Tempo

| Datum | Dokument |
|---|---|
| 2026-10-12 | [MODELLVERGLEICH_2026-10-12.pdf](MODELLVERGLEICH_2026-10-12.pdf) · [MODELL_VERGLEICH_ERGEBNISSE.md](MODELL_VERGLEICH_ERGEBNISSE.md) (automatisch erzeugt) |
| 2026-10-10 | [QWEN_ANSCHLUSS_2026-10-10.md](QWEN_ANSCHLUSS_2026-10-10.md): Qwen Code in der Bau-Schleife |
| 2026-10-09 | [MODELL_VERGLEICH_PLAN_2026-10-09.md](MODELL_VERGLEICH_PLAN_2026-10-09.md) · [FLASH_ATTENTION_UNTERSUCHUNG_2026-10-09.md](FLASH_ATTENTION_UNTERSUCHUNG_2026-10-09.md) · [VSCODE_MIT_GUPPI_MODELLEN_2026-10-09.md](VSCODE_MIT_GUPPI_MODELLEN_2026-10-09.md) · [CLINE_ANALYSE_2026-10-09.md](CLINE_ANALYSE_2026-10-09.md) |
| 2026-10-05 | [ENGINE_TEMPO_PLAN_2026-10-05.md](ENGINE_TEMPO_PLAN_2026-10-05.md) |

## Selbstentwicklung: DevVM, Agent Manager, Workflow

| Datum | Dokument |
|---|---|
| 2026-10-10 | [PROZESS_GUPPY_VON_UNTEN_2026-10-10.md](PROZESS_GUPPY_VON_UNTEN_2026-10-10.md) · [WORKFLOW_PRUEFUNG_2026-10-10.md](WORKFLOW_PRUEFUNG_2026-10-10.md) · [AM007_LAEUFE_AUSWERTUNG_2026-10-10.md](AM007_LAEUFE_AUSWERTUNG_2026-10-10.md) |
| 2026-10-07 | [AGENT_MANAGER_INTEGRATION_BERICHT_2026-10-07.md](AGENT_MANAGER_INTEGRATION_BERICHT_2026-10-07.md) · [AM_BAU_FEHLERANALYSE_2026-10-07.md](AM_BAU_FEHLERANALYSE_2026-10-07.md) · [EINGRIFFE_CLAUDE_AUSWERTUNG_2026-10-07.md](EINGRIFFE_CLAUDE_AUSWERTUNG_2026-10-07.md) |
| 2026-10-06 | [AM001_INVENTAR_UND_DEVVM_ABGLEICH_2026-10-06.md](AM001_INVENTAR_UND_DEVVM_ABGLEICH_2026-10-06.md) · [WORKFLOW_OPTIMIERUNG_2026-10-06.md](WORKFLOW_OPTIMIERUNG_2026-10-06.md) · [TESTMODUL_VORBEREITUNG_2026-10-06.md](TESTMODUL_VORBEREITUNG_2026-10-06.md) |
| 2026-10-05/06 | [DEVVM_AUFTRAG_2026-10-05.md](DEVVM_AUFTRAG_2026-10-05.md) und die Phasenberichte [0](DEVVM_PHASE0_BERICHT_2026-10-05.md) · [1](DEVVM_PHASE1_BERICHT_2026-10-06.md) · [2](DEVVM_PHASE2_BERICHT_2026-10-06.md) · [3](DEVVM_PHASE3_BERICHT_2026-10-06.md) · [4](DEVVM_PHASE4_BERICHT_2026-10-06.md) · [5](DEVVM_PHASE5_BERICHT_2026-10-06.md) |
| 2026-10-04 | Schleifenwächter: [LOOP_GUARD_E1_ATTEMPT_2026-10-04.md](LOOP_GUARD_E1_ATTEMPT_2026-10-04.md) · [LOOP_GUARD_REWORK_PLAN_2026-10-04.md](LOOP_GUARD_REWORK_PLAN_2026-10-04.md) · [LOOP_GUARD_STARNET_EXTENSIONS_PLAN_2026-10-04.md](LOOP_GUARD_STARNET_EXTENSIONS_PLAN_2026-10-04.md) |

## Recherchen

| Datum | Dokument |
|---|---|
| 2026-10-10 | [EXTERNE_AGENTENUMGEBUNGEN_2026-10-10.md](EXTERNE_AGENTENUMGEBUNGEN_2026-10-10.md) · [GITHUB_UEBERBLICK_2026-10-10.md](GITHUB_UEBERBLICK_2026-10-10.md) · [VERGLEICH_LITTLE_CODER_GUPPI_2026-10-10.md](VERGLEICH_LITTLE_CODER_GUPPI_2026-10-10.md) |

## Aufbau-Phasen (abgeschlossen, 2026-10-01 bis 07)

Diese Berichte beschreiben, wie Job Supervisor, Routing, Rechte, Hardware-Reservierung, eigener llama-server und Kontext-Management entstanden sind.
Einige Konfigurationskommentare im Code verweisen darauf.

[INTEGRATION_PLAN.md](INTEGRATION_PLAN.md) · [ARCHITECTURE_GAP_REPORT.md](ARCHITECTURE_GAP_REPORT.md) · [CONTEXT_TOKEN_PLAN.md](CONTEXT_TOKEN_PLAN.md) ·
[PHASE0](PHASE0_STATUS.md) · [PHASE2](PHASE2_STATUS.md) · [PHASE3](PHASE3_STATUS.md) · [PHASE4](PHASE4_STATUS.md) · [PHASE5](PHASE5_STATUS.md) · [PHASE6](PHASE6_STATUS.md) ·
[PHASE7](PHASE7_STATUS.md) · [PHASE8](PHASE8_STATUS.md) · [PHASE8F](PHASE8F_LLAMA_SERVER.md) · [PHASE9](PHASE9_STATUS.md) · [REAL_RUN_STATUS.md](REAL_RUN_STATUS.md) ·
[SANDBOX_BOUNDARY_STATUS.md](SANDBOX_BOUNDARY_STATUS.md)

## Historie

[historie/](historie/README.md): Paket- und Versionsnotizen von v1.2 bis v1.20 (Handoff, Changelog, Testbericht, alte Startanleitungen). Sie gelten nicht mehr als Anleitung.
