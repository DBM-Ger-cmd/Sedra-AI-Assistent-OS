# SEDRA: Kern und die Shell „KI Gateway für KMU“ – ausführliche technische Übersicht

**Für:** Klaus Bruhns · **Von:** David Bennöhr · **Stand:** 20.10.2026
**Grundlage:** der Arbeitsstand im Hauptverzeichnis (Branch `release-vorbereitung`, Basis Build 25). Alle Zahlen sind am
20.10.2026 aus dem Code gezählt bzw. aus dem letzten Testlauf übernommen. Wo etwas nicht geprüft ist, steht das dabei.

---

## 1. Überblick in einem Absatz

SEDRA ist ein **lokales** Programm, das KI-Arbeit unter festen Regeln ausführt. Der **Kern** läuft auf dem eigenen Rechner
und entscheidet, was den Rechner verlassen darf. **Oberflächen** (Shells) sitzen darauf und zeigen, was der Kern tut. Die
Shell „KI Gateway für KMU“ ist die Arbeitsfläche des KI Gateways im Design der Präsentation. Eine Oberfläche entscheidet nie
selbst, ob etwas freigegeben wird; das tut der Kern.

## 2. Der Kern

### 2.1 Umfang

- **342 Python-Dateien**, rund **43.000 Zeilen**.
- **187 Testmodule** in `runtime/tests/`.
- Eine Schnittstelle mit **153 Routen** unter `/api/…` (HTTP, nur lokal erreichbar).

### 2.2 Aufbau nach Bereichen

| Bereich (Ordner unter `runtime/src/guppi_runtime/`) | Aufgabe |
|---|---|
| `core/` | Grundlagen, allgemeiner Inhaltsschutz (`content_guard.py`, `content_policy.py`) |
| `core/b6core/` | Schutzkern: Erkennung personenbezogener Daten, Pseudonymisierung. **Eingefroren**: die Herkunft jeder Datei ist per SHA-256 festgehalten (`HERKUNFT.sha256`). Änderungen brauchen eine bewusste Entscheidung. |
| `models/` | Anbindung der Modelle: lokal über den llama-server, Cloud nur über Anbieter, die ausdrücklich eingeschaltet sind. Der Cloudweg ist im Ist-Stand simuliert, solange kein Anbieter eingeschaltet ist. |
| `gateway/` | Das KI Gateway: Vorgänge, Schutzklassen, Regelbuch, Ablage, Wissensbasis (`vorgang.py`, `klassen.py`, `zusatz.py`, `ablage.py`, `wissen.py`) |
| `desk/` | Zustand der Oberfläche: Entscheidungen, Objekte, Installation, Schnittstelle zum Gateway |
| `uix/` und `uix_server.py` | Oberfläche und HTTP-Schnittstelle, Token-Prüfung, Modul-Freigaben |
| `sprache/` | Aufnahme und Spracherkennung. Ohne installierten Erkennungsdienst sagt der Kern das ehrlich. |
| `fisch/` | Übersetzen, Nachrichten, Transkripte (Shell „Translator“, Umbenennung läuft) |
| `jobs/`, `agent_manager/`, `capabilities/`, `tools/`, `sandbox/`, `coder_ext/`, `selfdev/` | Ausführung von Aufträgen, Werkzeuge, Prüfumgebung für Änderungen |
| `update_suche.py`, `update_holen.py`, `update_anwenden.py` | Aktualisierung aus dem Repository: nur auf Klick suchen, herunterladen, prüfen, nur mit Bestätigung übernehmen, mit Sicherung und Rückweg |

### 2.3 Grundregeln, die der Kern durchsetzt

1. **Personendaten bleiben lokal**, solange keine Rechtsgrundlage und kein Auftragsverarbeitungsvertrag dokumentiert sind
   (Regel R-01).
2. **Zugangsdaten und Kartendaten sperren den Vorgang vollständig**: kein Modellaufruf, auch nicht lokal (R-07).
3. **Anweisungen an die KI** im Dokument sperren den Vorgang; in der eigenen Anfrage verlangen sie eine Prüfung (R-08, R-09).
4. **Eine Freigabe gilt genau einmal**, für genau diese Anfrage. Gebunden ist sie an Anfrage, Dokument, Schutzklasse, Weg,
   Übergabe, Zweck und verantwortliche Person. Ändert sich eines davon, gilt die Freigabe nicht mehr.
5. **Nur restriktiver, nie offener**: Der Weg darf eine Stufe strenger sein als gewünscht, nie offener.
6. **Entscheidungen erteilt nur der Kern.** Ein Werkzeug oder ein Modell kann keine Freigabe erteilen. Werkzeuge außerhalb
   des Pakets bekommen die Shell ohne die Freigabefunktion.
7. **Jede Aktion wird im Audit-Protokoll festgehalten**, mit Prüfsummen und Gründen, nie mit dem Inhalt der Anfrage.

### 2.4 Schnittstelle und Absender

Die Oberfläche spricht nur über HTTP mit dem Kern. Jede Anfrage nennt ihren Absender (Werkzeug oder Shell). Der Server
prüft, ob der Absender die Route in seinem Manifest hat. Sonst antwortet er mit `tool_route_not_allowed`. Der Zugangsschlüssel
gelangt nicht in die Oberfläche: Die Oberfläche bekommt nur ihren eigenen Zugang über eine geprüfte Schnittstelle.

**Stand der Isolation (Plan `docs/PLAN_STUFE_C_2026-10-19.md`):**
- **Stufe A** (erledigt): Die Oberfläche bekommt den Schlüssel nicht mehr als globale Variable.
- **Stufe B** (erledigt): Die Prüfung der Modul-Quellen erkennt bekannte riskante Muster.
- **Stufe C** (im Code, eigener Plan): Werkzeuge außerhalb des Pakets laufen in einem abgeschotteten Rahmen (iframe ohne
  Zugriff auf die Seite). Der Browsertest bestätigt, dass verbotene Versuche verweigert werden.

## 3. Die Shell „KI Gateway für KMU“ (`gateway-kmu`)

### 3.1 Zweck

Die Shell zeigt das KI Gateway im Design der Präsentation „KI Gateway für KMU · B6 · SEDRA“ (Designvorschlag V4.2 von dir,
19.10.2026). Sie ist eine Arbeitsfläche: Der Kopf zeigt den Ablauf, das Werkstück in der Mitte arbeitet, unten ist das Gespräch.

### 3.2 Aufbau in drei Zonen

- **Kopf** (`sh-gateway-kmu-kopf`): Eyebrow „B6 / SEDRA · Ein sicherer Weg zur KI“, Titel „KI Gateway für KMU“, Untertitel
  „KI-Power. Mit Kontrolle.“, Satz „Eine Aufgabe. Eine Oberfläche. Nachvollziehbare Kontrollpunkte.“, und der Ablauf mit fünf
  Schritten: *Aufgabe eingeben → Schutz prüfen → Entwurf erzeugen → Ergebnis prüfen → selbst entscheiden.* Der Ablauf ist
  Anzeige und keine Schaltfläche. Der Bogen aus Folie 11 steht rechts im Kopf. Beim Rollen des Werkstücks wird der Kopf
  kompakt; oben angekommen wächst er wieder. Zwei Schwellen verhindern Flackern.
- **Werkstück** (`sh-gateway-kmu-body`): rollt. Oben die Verben, darunter das Werkzeug des gewählten Objekts. Die Kugel aus
  Folie 4 liegt schwach im Hintergrund.
- **Gespräch** (unten): das Gesprächswerkzeug, in der Höhe ziehbar (Variable `--talk-h`, Standard 160 px).

### 3.3 Gestaltung

- Alle Farben, Schriften und Abstände kommen aus den Tokens `--kmu-…` in `ui/tokens.css`: Hintergrund `#0d174e`, tiefer
  Hintergrund `#080d33`, Kästchen `#243269`, Akzent `#53ddd0`, Titel `#ffffff`, Untertitel `#b4c2ec`.
- Mischungen für Glas und Licht entstehen per `color-mix` aus denselben Tokens.
- **Kein Hex-Wert** in `shell.css` und `shell.js` (Vertragsprüfung).
- Schaltflächen des Vertrags (`.s-btn`) sind in dieser Shell Pillen mit Licht beim Zeigen; die erste Handlung ist gefüllt.
- Bewegung nur über `transform` und `opacity`, lange Wege. `prefers-reduced-motion` schaltet alles ab.

### 3.4 Dateien

| Datei | Umfang | Inhalt |
|---|---|---|
| `shells/gateway-kmu/shell.js` | 113 Zeilen | Aufbau von Kopf, Werkstück und Gespräch, Ablauf, Parallaxe, kompakter Kopf |
| `shells/gateway-kmu/shell.css` | 217 Zeilen | Gestaltung über die Tokens |
| `shells/gateway-kmu/shell.yaml` | 12 Zeilen | Id `gateway-kmu`, Vertrauensstufe CAPTAIN, Freigabe-Route `POST /api/decisions/answer` |
| `shells/gateway-kmu/kmu-hero.png` | 1280×720 | Bogen mit Schild, verkleinert |
| `shells/gateway-kmu/kmu-glow.png` | 560 px | Kugel, verkleinert |
| `runtime/assets/kmu-praesentation/` | — | Vollauflösung der Folienbilder und Design-Ableitungen |

### 3.5 Die Werkzeuge darin

Die Shell kennt kein Werkzeug beim Namen; die Registrierung sagt, wer ein Objekt zeichnet. Im Werkstück ist es das Werkzeug
**`gateway`**:
- Vorgänge (neu, Liste, Detail mit den vier Stationen),
- Dateien (Eingang, Vorschau, Arbeitskopie, Speichern unter mit Vermerk),
- Regeln (Regelbuch, gemerkte Vorgaben),
- Verlauf und Frage an das Wissen („Frag SEDRA“, ohne Modell).

Eingebettet ist darin das Werkzeug **`schutz`** (KI Gateway · Schutz). Es zeigt den Überblick mit Stationen und Zählern,
die Regeln mit ihrer Schärfe, die Prüfung eines Textes ohne Modell und den Verlauf des Tages. Die Reiter des Schutzes sind
im Gateway ausgeblendet, das Menü links übernimmt diese Auswahl.

## 4. Das KI Gateway: der Ablauf eines Vorgangs

1. **Anlegen.** Ein Vorgang bekommt einen Titel, einen Wunsch (lokal oder Cloud) und eine Kennung `GW-…`.
2. **Eingabe.** Eine Anfrage, optional ein Dokument (`.md`, `.txt`, `.docx`). Das Dokument wird im Eingang abgelegt; die
   Originale bleiben unverändert, eine Arbeitskopie ist möglich.
3. **Prüfung** (Station 2 „Schutz prüfen“):
   - Schutzklasse **SK0** (öffentlich) bis **SK3** (streng vertraulich),
   - Merkmale: P01 Personenbezug, P02 Besondere Kategorien, P03 Strafsachen, P04 amtliche Kennungen, V01 Minderjährige,
     F01 Bankverbindung, F02 Kartendaten, F03 Kartendaten mit Prüfwert (sperrt), S01 Zugangsdaten (sperrt), S02 Anweisungen
     an die KI (sperrt im Dokument), G01 Geschäftsgeheimnis, G02 Vertraulichkeitsvereinbarung, R01 Rechtsstreit (von Hand),
     A01 Hochrisiko-Kontext (von Hand),
   - erlaubte Wege: lokal, Cloud nach Pseudonymisierung, Cloud zulässig,
   - Policy: automatisch erlaubt, menschliche Prüfung nötig, gesperrt.
4. **Übergabe** (Station 2): Der Text mit Platzhaltern wie `<PERSON_001>`, `<EMAIL_001>`, `<KUNDE_001>`. Sie entsteht nur,
   wenn die Prüfung es erlaubt; bei Sperre wird kein Text gespeichert.
5. **Freigabe** (Station 3): ein Klick, gebunden an genau diesen Vorgang. Bei gesperrtem Vorgang gibt es keinen Knopf.
   Das Gateway fragt zusätzlich nach Zweck und verantwortlicher Person.
6. **Entwurf** (Station 4): Das lokale Modell erzeugt einen Entwurf, der als KI-Entwurf gekennzeichnet ist (R-14).
7. **Prüfung durch den Menschen** (Station 5): Erst nach dem Haken „geprüft“ kann der Entwurf ausgegeben werden. Es gibt
   keinen Versand. Was danach geschieht, liegt außerhalb von SEDRA.

## 5. Die Regeln (Regelbuch R-01 bis R-16)

| Regel | Merkmal | Kategorie | Lokal | Cloud | Prüfung |
|---|---|---|---|---|---|
| R-01 | P01 | Personenbezogene Daten | ja | nein, bis Rechtsgrundlage und AVV | nein |
| R-02 | P02 | Besondere Kategorien (Art. 9) | nur nach Prüfung | nie | ja |
| R-03 | P03 | Strafrechtliche Daten (Art. 10) | nur nach Prüfung | nie | ja |
| R-04 | P04 | Amtliche Kennungen | nur nach Prüfung | nie | ja |
| R-05 | V01 | Minderjährige | nur nach Prüfung | nie | ja |
| R-06 | F01/F02 | Bankverbindung, Kartendaten | ja | nie | nein |
| R-07 | F03/S01 | Kartendaten mit Prüfwert, Zugangsdaten | nein | nie | — (gesperrt) |
| R-08 | S02 | Anweisungen an die KI im Dokument | nein | nie | — (gesperrt) |
| R-09 | S02 | Anweisungen an die KI in der Anfrage | nur nach Prüfung, ohne Platzhalter | nie | ja |
| R-10 | G01 | Geschäftsgeheimnis, Kalkulation | nur nach Prüfung | nie | ja |
| R-11 | G02 | Vertraulichkeitsvereinbarung | ja | nie | nein |
| R-12 | R01 | Rechtsstreit | ja | nie | nein |
| R-13 | A01 | Hochrisiko-Kontext | nur nach Prüfung | nie | ja |
| R-14 | — | KI-Kennzeichnung des Entwurfs | — | — | — |
| R-15 | — | keine Kategorie, Scan vollständig | ja | ja | nein |
| R-16 | — | Scan unvollständig oder Datei unlesbar | nein | nein | ja |

**Wichtig:** Die Regeltabelle ist eine Tabelle im Code. Wer fachlich anders entscheidet, ändert die Tabelle; die Normbezüge
sind Annahmen des Teams und keine Rechtsprüfung.

**Zusätzliche Erkennung** (`gateway/zusatz.py`, 55 Zeilen): Sie ergänzt den eingefrorenen Schutzkern um Zugangsdaten
(Kennwort, Passwort, API-Schlüssel, Token), Geschäftsinformationen (vertraulich, Preisuntergrenze, Sonderrabatt, Marge,
Kaufpreis, Konditionen, nicht veröffentlicht), Gehaltsdaten (Gehalt, brutto, Vergütung), den Verweis auf einen öffentlichen
externen Dienst, Personalnummern (`P-123`), Anschlüsse (`TEL-…`), Geburtsdaten und Kontokennungen sowie Anweisungen an die KI
(„ignoriere alle Regeln“). Die Treffer folgen denselben Regelnamen und durchlaufen dieselbe Einstufung.

## 6. Tests und Prüfung

### 6.1 Testsatz

- **187 Testmodule** insgesamt. Im letzten vollständigen Lauf: **170 grün, 0 rot**. 16 Module laufen nicht, weil die
  DevVM-Abhängigkeit `dulwich` auf diesem Rechner fehlt (sie werden mit Grund übersprungen, nicht gelöscht).
- **Gateway:** `test_gateway` (45 Tests grün), `test_gateway_kmu_shell`, `test_gateway_menu_browser`, `test_gateway_nav`,
  `test_gateway_ende_zu_ende`, `test_gateway_vorgaben`, `test_gateway_wissen`, `test_gateway_ablage`,
  `test_gateway_freigabe_nach_neustart`.
- **Oberfläche:** `test_uix_contract` (35 Tests grün), `test_uix_flows`, `test_uix_shell_start`, `test_menue_seite`,
  `test_stufe_c_bruecke` (12 Tests), `test_stufe_c_rahmen`.
- **Schutzkern:** `test_content_guard`; die Herkunftsprüfung des eingefrorenen Kerns ist grün.

### 6.2 Die 20 synthetischen Prüffälle

Das Prüfdokument „SEDRA 20 synthetische Prüffälle Büroalltag“ enthält 20 Eingaben mit erwartetem Verhalten. Sie wurden durch
dieselbe Pipeline gelaufen wie im Gateway (Anlegen, Prüfung, Übergabe), ohne Modell und ohne Oberfläche. Ausführlicher Bericht:
`docs/PRUEFBERICHT_KI_GATEWAY_KMU_2026-10-20.md`.

**Ergebnis vor der letzten Korrektur:** 6 bestanden, 2 offen (brauchen ein Modell), 12 nicht bestanden.
**Nach der Korrektur** (Zugangsdaten, Geschäftsinformation, Gehalt, Personalnummern, Anweisung an die KI, Vornamen):
- Zugangsdaten (Fall 16) sind gesperrt.
- Gehalts-, Konditions- und Geschäftsfälle (11, 15, 18, 20) gehen zur menschlichen Prüfung und bleiben lokal.
- Im Klartext bleibt kein Name außer „Paula“ in einer Notiz (Fall 10, nur Vorname).

### 6.3 Was offen ist (ehrlich)

1. **Personalnummern, Anschlüsse, Geburtsdaten** werden erkannt und lokal gehalten, aber im Text **nicht ersetzt**. Dafür
   bräuchte die Pseudonymisierung eine Erweiterung im eingefrorenen Kern.
2. **Ein einzelner Vorname** (z. B. „Paula“ ohne Nachnamen) wird nicht ersetzt, weil das auch gewöhnliche Wörter träfe.
3. **Zugangsdaten sperren den ganzen Vorgang.** Dadurch ist ein Dokument mit einem einzigen Geheimnis nicht auswertbar.
   Die Alternativen (Text maskiert speichern, oder nur Fundstellen zeigen) sind offen und brauchen eine Entscheidung.
4. **Die Namenserkennung ist bewusst konservativ**: Sie erkennt Namen nur in belegbaren Formen (Selbstnennung, Anrede,
   Rollenwort mit Vorname, bekannter Vorname mit Nachname, Unterschrift). Eine Erweiterung ist eine Änderung am eingefrorenen
   Kern und braucht deine Freigabe.
5. **Die Oberfläche selbst** wurde für die 20 Fälle nicht durchgeklickt; geprüft ist die Pipeline dahinter.
6. **Der Beweistest mit einem Modell** (Sitzung „KI GateWay testen“, Port 8089) ist abgeschlossen. Sein Ergebnis: Der lokale
   Filter bereinigt Personendaten nicht zuverlässig; die Wahl zwischen deterministischer Schwärzung und besserem Filter-Prompt
   liegt bei dir.

## 7. Die Demo der Shell

Für die Bausteinprüfung gibt es eine eigenständige HTML-Demo der Shell (Datei `demo_kmu_look2.html` im Scratchpad, ohne Technik
aus dem Projekt): Ablauf oben, linke Navigation mit sechs Bereichen, die vier Stationen, „Wartet auf dich“, „Zuletzt“, unten die
Gesprächszeile. Die Demo arbeitet mit einfachen Regeln und ohne Modell. Sie zeigt das Erscheinungsbild und den Ablauf, nicht
die echte Prüfung.

## 8. Der Rekorder und die Leiste (neu heute)

- **Aufnahme in eigenem Fenster:** Die Aufnahme läuft in `fenster/rekorder.html`. Der Wechsel der Shell lädt nur die
  Hauptseite neu; die Aufnahme läuft weiter. Ein Test prüft das.
- **Leiste unten rechts** in jeder Shell: Zeit, Start, Pause, Stopp, Verwerfen. Sie spricht mit dem Fenster über einen
  Browser-Kanal. Fällt das Fenster weg, zeigt die Leiste nach etwa 2,5 Sekunden „aus“.
- **Offen:** Der Start aus dem Aufnahme-Modus der Fisch-Shell ist noch nicht eingebaut; heute startet man über die Leiste.

## 9. Was man sagen kann und was nicht

**Sagen:**
- SEDRA läuft lokal, Personendaten bleiben lokal, Zugangsdaten sperren, jede Freigabe gilt genau einmal, jede Aktion
  wird protokolliert.
- Die Shell zeigt den Ablauf von der Anfrage bis zur eigenen Entscheidung.
- 20 synthetische Fälle sind durchgerechnet; Ergebnis und offene Punkte sind dokumentiert.

**Nicht sagen:**
- Vollständige Erkennung aller Personen oder Datenarten.
- Rechtskonformität nach DSGVO oder AI Act (die Normbezüge sind Annahmen des Teams).
- Cloud-Verarbeitung ohne eingeschalteten Anbieter und ohne Freigabe.
- Automatische Transkription ohne installierten Erkennungsdienst.
- Dass die Oberfläche durch alle 20 Fälle geklickt wurde.

---

## Anhang: Wo was liegt

| Thema | Datei |
|---|---|
| Kurzfassung für das Dashboard | `docs/SEDRA_KERN_UND_KMU_SHELL_TECHNIK_2026-10-20.md` |
| Diese ausführliche Fassung | `docs/SEDRA_KERN_UND_KMU_SHELL_AUSFUEHRLICH_2026-10-20.md` |
| Prüfbericht der 20 Fälle | `docs/PRUEFBERICHT_KI_GATEWAY_KMU_2026-10-20.md` |
| Plan Isolation und Update | `docs/PLAN_ISOLATION_UND_UPDATE_2026-10-19.md` |
| Plan Stufe C | `docs/PLAN_STUFE_C_2026-10-19.md` |
| Shell-Code | `runtime/src/guppi_runtime/uix/shells/gateway-kmu/` |
| Gateway-Code | `runtime/src/guppi_runtime/gateway/` |
| Regelbuch im Code | `runtime/src/guppi_runtime/gateway/klassen.py` |
| Eingefrorener Schutzkern | `runtime/src/guppi_runtime/core/b6core/` (mit `HERKUNFT.sha256`) |
