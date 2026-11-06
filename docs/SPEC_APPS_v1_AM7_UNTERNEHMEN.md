# SPEC Apps v1 – AM7: Betrieb im Unternehmen (KMU-Shell): Betreiber, Rollen, Richtlinie, Profile (03.11.2026)

Status: **G1**, Entscheidungen getroffen (03.11.2026, wie vorgeschlagen: Betriebsart **A**); vor G2 wird dieses G1 auf Betriebsart A zugeschnitten. Nichts gebaut. Teil von `docs/KONZEPT_APPS_UND_ERWEITERUNGEN_v1.md` §11. Setzt AM2 und AM3 voraus.
Ziel: SEDRA lässt sich in einem Unternehmen so betreiben, dass ein **Betreiber** festlegt, welche Apps, Shells, Anbieter und Rechte es gibt, und **Beschäftigte** in einer kontrollierten Umgebung (KMU-Shell) mit Dokumenten und KI arbeiten – mit Nachweis.
**AM7-E1 ist entschieden (Betriebsart A, 03.11.2026).** Nächster Schritt: dieses G1 auf Betriebsart A zuschneiden, dann G2.
Pfade relativ zu `runtime/src/sedra_runtime/`, Zeilen für c364081. Rechtliche Begriffe sind Einordnung, keine Rechtsprüfung.

## 1. Befund

| Nr | Befund | Beleg |
|---|---|---|
| B1 | SEDRA kennt **keine Benutzer und keine Rollen**. Im Gateway-Vorgang steht als Verantwortliche Person die Bezeichnung „Nutzer“; Kommentar: „SEDRA kennt keine Rollen: der Nutzer ist die Prüfung“. | `gateway/vorgang.py:48` |
| B2 | Rollen und Berechtigungen sind im Gateway-MVP ausdrücklich ausgeschlossen; Rollen im Prüffall TC-011 sind „Demo-Annahmen“. | `docs/SPEC_GATEWAY_VORGANG_v1.md:18, 77` |
| B3 | Der Server lauscht nur auf Loopback; der Browser bekommt **einen** Token in der Adresse (`…/#<token>`). Wer die Adresse hat, ist „der Captain“. | `uix_server.py:3981, 3995` |
| B4 | Die Freigabe eines Gateway-Vorgangs ist an Anfrage, Dokument, Schutzklasse, Weg, Übergabe, Zweck und verantwortliche Person gebunden (G-05). | `gateway/vorgang.py:17`; `docs/SEDRA_KERN_UND_KMU_SHELL_AUSFUEHRLICH_2026-10-20.md` §2.3 |
| B5 | Das Regelwerk enthält R-13 „Hochrisiko-Anwendungskontext (Personal, Kredit, Bildung, Strafverfolgung)“ mit dem Vermerk „EU AI Act Anhang III (Annahme; Rolle Anbieter/Betreiber offen)“ und R-14 „KI-Kennzeichnung des Entwurfs“ (Art. 50). | `gateway/klassen.py:76–80` |
| B6 | Die KMU-Shell bietet `dock` und `talk`, trägt `trust: CAPTAIN` (im Paket) und hat als einzige Route die Antwort auf Entscheidungen. Logbuch, Modus und Grenzen, Module, Einstellungen sind dort nicht erreichbar (nach `provides`; nicht im Browser geprüft). | `uix/shells/gateway-kmu/shell.yaml` |
| B7 | Das Audit ist eine Hash-Kette ohne Inhalte; es gibt keine Angabe, **welche Person** gehandelt hat (es gibt nur eine). | `core/audit.py` (ARCHITEKTUR §1); B1 |
| B8 | Der Release-Updater verlangt die Bestätigung jeder Rechteänderung eines Moduls. | `update_anwenden.py:7–8` |

### 1a. Erster realer Fall (Nachtrag 03.11.2026)

Der USB-Stick für einen Arbeitskollegen (`docs/WISSENSDATENBANK_USB_STICK_CHAT.md` auf Branch `fix/harness-list-projects`; `docs/PLAN_USB_STICK_MINIMAL.md` auf Branch `plan/usb-stick-minimal`) ist genau die Betriebsart A: eigener Rechner, eigene SEDRA, Harness als Standard. Heute ohne Richtlinie, ohne Rollen, ohne festgelegte Person. Er eignet sich als **Pilot** für AM7: zuerst die Richtlinie (AM7-04) als Datei auf dem Stick, die der Kollege nicht über SEDRA ändern kann.

## 2. Die Grundsatzfrage: Betriebsart

SEDRA ist heute ein Programm für **eine Person an einem Rechner**. Für Beschäftigte gibt es drei Betriebsarten. Sie unterscheiden sich so stark, dass alles Weitere davon abhängt:

| Art | Beschreibung | Folgen | Bewertung |
|---|---|---|---|
| **A – je Person ein Rechner mit eigener SEDRA** | Jede Person hat ihre Installation (lokal, Loopback wie heute). Der Betreiber verteilt eine **Richtlinie** und Apps. | Das Sicherheitsmodell von heute bleibt (Loopback, ein Token). Rollen gibt es nur als „wer an diesem Rechner sitzt“. Der Betreiber sieht Nachweise nur über Export. **Grenze:** Gegen eine Person mit Administratorrechten am eigenen Rechner kann SEDRA die Richtlinie nicht durchsetzen; das muss das Betriebssystem tun (Datei schreibgeschützt, Verteilung über die IT). | **Vorschlag für v1** |
| **B – ein Rechner, mehrere Windows-Konten** | Eine Installation je Windows-Konto oder eine gemeinsame. | Gemeinsame Installation: Token-Dateien und `local_config` müssten je Konto getrennt sein; DPAPI ist je Konto (`uix_clients.py:2–4`). Eigene Installation je Konto = Art A auf einem Gerät. | nur als Variante von A |
| **C – ein Server, Zugriff über das Netz** | SEDRA lauscht im Netz, Personen melden sich an. | Grundlegende Änderung: Loopback-Annahmen fallen (`uix_server.py:3535–3540`), Anmeldung, Sitzungen, TLS, Mandantentrennung, Mehrbenutzer-Ablage. Das ist ein **eigenes Produkt-Vorhaben**, nicht ein Baustein dieses Konzepts. | nicht in v1 |

## 3. Anforderungen (unter Annahme Betriebsart A; endgültig nach AM7-E1)

### 3.1 Rollen

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| AM7-01 | Feste Rollen in v1: `betreiber` (legt Richtlinie fest, gewährt), `pruefung` (Datenschutz/Revision: liest Nachweise, entscheidet Prüffälle nach R-13), `sachbearbeitung` (arbeitet in der KMU-Shell). Keine frei definierbaren Rollen in v1. | Test |
| AM7-02 | In Betriebsart A ist die Rolle einer Installation in der Richtlinie festgelegt (`rolle: sachbearbeitung`); die Rolle `betreiber` hat eine eigene Installation oder einen eigenen Verwaltungszugang mit eigenem Token (AM7-E2). | Test |
| AM7-03 | Die verantwortliche Person im Gateway-Vorgang (G-05) wird aus der Richtlinie gesetzt (Name/Kennung der Person, nicht frei eingebbar), wenn eine Richtlinie aktiv ist; sonst wie heute „Nutzer“. | Test |

### 3.2 Richtlinie des Betreibers

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| AM7-04 | Datei `local_config/richtlinie.yaml` (Schema `richtlinie.schema.json`): `rolle`, `person`, `apps` (Positivliste: id, Versionsbereich, optional Hash), `shells` (erlaubt, Start-Shell), `obergrenzen` (z. B. `community: verboten`, `dienste: verboten`, `zellen_fremd: verboten`, `ereignisse_inhalt: verboten`), `anbieter` (erlaubte Cloud-Anbieter und Modelle, AM5), `agenten` (AM6), `grundfunktionen_sichtbar` je Rolle, `aufbewahrung` (Gespräche, Entwürfe, Audit-Export). | Schema-Test |
| AM7-05 | Ist eine Richtlinie aktiv, gilt sie **über** der Gewährung (Konzept §5.2): App nicht auf der Liste → nicht geladen (`richtlinie_app_nicht_erlaubt`); Obergrenze verletzt → Fähigkeit nicht wirksam; Shell nicht erlaubt → Wechsel nicht möglich. | Test |
| AM7-06 | Sachbearbeitung kann die Richtlinie nicht über SEDRA ändern (keine Route, kein Antrag). Änderungen kommen als neue Datei vom Betreiber. SEDRA erkennt eine Änderung (Hash) und protokolliert `RICHTLINIE_GEAENDERT {alt_hash, neu_hash}`. Ob die Datei vor der Person geschützt ist, entscheidet das Betriebssystem (§2, Art A). | Test |
| AM7-07 | Optional (AM7-E3): Die Richtlinie trägt eine Signatur des Betreibers; ohne gültige Signatur gilt die letzte gültige Fassung und ein Warnhinweis erscheint. | Test |

### 3.3 KMU-Shell

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| AM7-08 | Für `sachbearbeitung` zeigt die KMU-Shell nur: Gespräch, eigene Entscheidungen, eigene Aufgaben/Vorgänge und die von der Richtlinie erlaubten Fach-Apps. | uix_check mit Rolle |
| AM7-09 | Für `betreiber`/`pruefung` gibt es einen Zugang **„Verwaltung“**, der die Grundfunktionen Logbuch, Modus und Grenzen, Module und Berechtigungen, Einstellungen und Zustand öffnet – **dieselben** Apps des Pakets, kein Nachbau (`grundfunktionen: …: verwaltung`, AM2-14). | uix_check |
| AM7-10 | Fach-Apps der KMU-Shell kommen als Shell-eigene Paket-Apps (`uix/shells/gateway-kmu/apps/`, AM2-07). Kandidaten (nicht festgelegt): Dokumentenablage, Vorgangsliste, Schutzklassen-Übersicht, Verzeichnis der eingesetzten KI (aus AM3-26, AM5-08, AM8). Jede bekommt eine eigene Spec. | – |
| AM7-11 | Schutzklassen ändern, freigeben, Regeln ändern bleiben Kern; Fach-Apps zeigen und beantragen nur (Konzept §10). | Code-Prüfung |

### 3.4 Nachweis und Information

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| AM7-12 | Jeder Audit-Eintrag trägt bei aktiver Richtlinie `person` und `rolle` (aus der Richtlinie, nicht vom Aufrufer), weiter ohne Inhalt. | Test |
| AM7-13 | Export für die Prüfung: Audit-Kette mit Prüfung der Kette, Verzeichnis der Apps und Gewährungen (AM3-26), Empfängerverzeichnis (AM5-08), Liste der Vorgänge mit Schutzklasse, Weg, Zweck, verantwortlicher Person – ohne Inhalte. Format JSON und eine lesbare Fassung. | Test |
| AM7-14 | Eine Seite **„Was SEDRA mit deinen Eingaben tut“** für Beschäftigte, erzeugt aus Richtlinie und Empfängerverzeichnis: was lokal bleibt, was an wen geht, wie lange es wo liegt, wer es sehen kann. Keine Versprechen über das Gespeicherte hinaus. | uix_check, Textprüfung |
| AM7-15 | Hochrisiko-Kontext (R-13): Trifft der Inhaltsschutz A01, geht der Vorgang an die Rolle `pruefung` (Entscheidung dort), nicht an die Sachbearbeitung. | Test |
| AM7-16 | KI-Kennzeichnung (R-14) bleibt an jedem Entwurf; die Richtlinie kann sie nicht abschalten. | Test |

### 3.5 Trennung und Aufbewahrung

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| AM7-17 | Eine Installation gehört zu genau einem Unternehmen (kein Mandantenbetrieb in v1). | Doku |
| AM7-18 | Aufbewahrung aus der Richtlinie: Gesprächsverläufe, Entwürfe (heute 24 h Vorgabe im Gateway, `gateway/vorgang.py:50`), Ablagen der Apps; Löschen geschieht täglich und wird ohne Inhalt protokolliert. | Test |
| AM7-19 | Updates von SEDRA und Apps übernimmt nur der Betreiber (Release-Updater mit Rechtebestätigung, B8; App-Updates AM3-13ff). | Test |

## 4. Themen zur Prüfung durch Fachleute (nicht von dieser Spec beantwortet)

- Rolle des Unternehmens nach der EU-KI-Verordnung (Betreiber eines KI-Systems; ob SEDRA dabei als Anbieter gilt, ist offen – so steht es auch in `gateway/klassen.py:76`).
- Pflichten zur KI-Kompetenz der Beschäftigten und zur Information über KI-Nutzung; was AM7-14 dafür leisten kann und was nicht.
- Hochrisiko-Zwecke (R-13): ob ein Unternehmen SEDRA dafür überhaupt einsetzen darf und mit welchen Pflichten.
- Datenschutz-Folgenabschätzung, Auftragsverarbeitung mit Cloud-Anbietern (AM5), Beteiligung einer Arbeitnehmervertretung bei Protokollierung mit Personenbezug (AM7-12).
- Aufbewahrungsfristen.

## 5. Tests und Abnahme

Erst nach G2. Abnahme mit einem Pilotbetrieb (Betreiber + eine Sachbearbeitung) in Betriebsart A.

## 6. Rückfall

Keine Richtlinie = Einzelplatzbetrieb wie heute. Schalter `betrieb_unternehmen` (Standard aus).

## 7. Abgrenzung

Kein Server-Betrieb (Art C), kein Mandantenbetrieb, keine frei definierbaren Rollen, keine Anmeldung mit Passwort in SEDRA (in Art A meldet sich die Person am Rechner an).

## 8. Risiken

- Hoch. Grundlegendste Änderung des Konzepts: Aus „der Captain“ werden mehrere Personen.
- Eine Richtlinie auf einem Rechner, den die Person selbst verwaltet, ist nur so stark wie der Dateischutz des Betriebssystems.
- Protokollierung mit Personenbezug (AM7-12) ist selbst eine Verarbeitung personenbezogener Daten der Beschäftigten.

## 9. Entscheidungen des Captains

**Entschieden vom Captain am 03.11.2026: alle Vorschläge dieser Tabelle übernommen.**

| Nr | Frage | Vorschlag |
|---|---|---|
| AM7-E1 | Betriebsart für v1 | **A** (je Person ein Rechner, Richtlinie verteilt) |
| AM7-E2 | Betreiber: eigene Installation oder Verwaltungszugang in derselben? | eigene Installation (Art A konsequent) |
| AM7-E3 | Signierte Richtlinie in v1? | nein in v1, Hash + Protokoll; mit Pilotkunden neu bewerten |
| AM7-E4 | Gespräch (freier Chat) für Sachbearbeitung oder nur geführter Gateway-Ablauf? | durch die Richtlinie wählbar; Vorgabe: nur Gateway-Ablauf |

## 10. Berechtigungen vorab

Erst nach AM7-E1. Voraussichtlich: `desk/` (Richtlinie), `uix_server.py`, `gateway/vorgang.py` (verantwortliche Person), `core/audit.py` (Felder `person`, `rolle` – Kern, Captain-Entscheidung), KMU-Shell, Tests.

## 11. Nächste Gates

AM7-E1 → G1 überarbeiten → G2 → G3 → Pilot.
