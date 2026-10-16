# Was wir bisher gemacht haben – Stand 16.10.2026

Für Klaus und Torsten. Diese Datei fasst zusammen, was seit dem Start der Cloud-Arbeit umgesetzt wurde, welche Entscheidungen gefallen sind, was offen ist und welche Risiken wir sehen. Sie ersetzt nicht die Verträge und Regelwerke im Projekt, sondern verweist auf sie.

## 1. Kurzfassung

- Ein **API-Zugang** zu Cloud-Modellen (NVIDIA, OpenAI-kompatibel und Anthropic) ist gebaut. Er ist **standardmäßig aus**.
- Jeder Cloud-Aufruf läuft durch den **Inhaltsschutz**. Dessen Regeln sind unverändert.
- Die **KI Labor** in der Cockpit-Shell bündelt Anbieter, Schlüssel, Modelle, Tests und die Läufe.
- Ein **Sandbox-Verfahren** erlaubt einem Cloud-Modell, Oberflächen zu entwerfen. Es darf nur in einem festgelegten Arbeitsbereich schreiben. Übernommen wird erst nach Prüfung.
- Die **Redesign-Phase A** (dunkle Farbtokens als Standard, Kontrasttests) ist umgesetzt.
- Mehrere **Overhaul-Läufe** und ein Spec-Versuch mit drei Modellen laufen. Ergebnisse stehen noch aus.
- Ein **Bewertungslauf** zum Projekt OmniRoute (MIT-Lizenz) läuft. Ziel ist, nützliche Bausteine für SEDRA zu übernehmen.

## 2. Der API-Zugang (Kern)

**Dateien:** `runtime/src/guppi_runtime/models/cloud_api.py`, `cloud_settings.py`, `labor.py`.

- **Standard aus.** Ohne Hauptschalter und Anbieter-Schalter wird nichts gebaut und nichts gesendet.
- **Keine Schlüssel in Dateien.** Die Konfiguration enthält nur einen Verweis. Der Wert kommt aus einer Umgebungsvariable oder aus der verschlüsselten Ablage (Windows-DPAPI, nur für den Windows-Benutzer lesbar).
- **Keine Schlüssel in der Oberfläche.** Die Anzeige sagt nur „umgebung“, „gespeichert“ oder „fehlt“.
- **Fehlermeldungen ohne Schlüssel.** Der Grund des Anbieters wird angezeigt, aber Schlüssel-Ausschnitte werden geschwärzt.
- **Kein stiller Wechsel.** Der Router wählt Cloud nie von selbst. Ein Aufruf zu einem Cloud-Anbieter muss ausdrücklich benannt sein.
- **Zuordnung Modul → Modell** (`module_models`): Jedes Modul kann ein eigenes Modell haben. Ein Eintrag mit unbekanntem Anbieter wird ignoriert.

## 3. Der Inhaltsschutz

Die Regeln des Inhaltsschutzes sind **nicht geändert** worden. Neu ist nur der Umgang mit Fundstellen vor dem Versand:

- **Eigene Begriffe statt Sperre** (`redesign_prep.py`): Beanstandete Stellen werden durch Begriffe wie `[PERSON-001]` oder `[SCHLUESSEL-001]` ersetzt. Die Zuordnung bleibt lokal. Danach prüft der Schutz den Text erneut.
- **Captain-Entscheidung** (16.10.2026): Dieses Schwärzen ist erlaubt, die Schwelle des Schutzes bleibt.
- **Fehlende Rückübersetzung:** Im Cloud-Pfad bleiben Antworten mit Platzhaltern stehen. Das ist keine rechtliche Anonymisierung.

**Offener Punkt, bitte entscheiden:** Das Regelwerk (R-01, Cloudsperre v0.1) sagt, dass pseudonymisierte Daten personenbezogen bleiben und ohne Rechtsgrundlage nicht in die Cloud gehen. Die Funktion im Inhaltsschutz pseudonymisiert Personenbezug aber beim Versand. Das weicht vom Regelwerk ab. Dazu braucht es eine Entscheidung von Klaus. Bis dahin ist die Cloud-Nutzung für personenbezogene Daten nicht freigegeben.

## 4. Die KI Labor (Cockpit, Werkstatt)

**Datei:** `uix/tools/labor/`.

- **Anbieter und Schlüssel:** Schalter, Adresse, Schlüssel speichern oder löschen. Speichern erfolgt auf Klick.
- **Modelle:** Karten mit Filterspalte, Suche, Sortierung und Seiten. „Modelle abfragen“ liest die Liste live beim Anbieter, ohne Prompt.
- **Module und ihr Modell:** Pro Modul wird das Modell gewählt (Gespräch, Redesign-Läufe).
- **Tests:** „Verbindung testen“ prüft in Schritten: Schlüssel, Modellliste, eine beantwortete Testnachricht. „Alle Modelle testen“ spricht jedes Modell einmal an. Das kostet Tokens und dauert.
- **Läufe:** Jeder Lauf ist eine Karte. Sie zeigt Modell, Status, Aufrufe, geschriebene Dateien und klappt die Details auf.

**Gesprächsleiste:** Neben „Senden“ wählt man „GUPPI lokal“ oder ein Cloud-Modell. Das Modell aus der Zuordnung „Gespräch“ ist die Vorgabe.

## 5. Das Sandbox-Verfahren (Grundsatz des Captains)

**Dateien:** `sandbox_edit.py`, `redesign_agent.py`, `redesign_run.py`, `spec_lab.py`, `redesign_review.py`.

- Ein Cloud-Modell **darf Dateien schreiben, aber nur** unter `workspace/GUPPI_OS/redesign/`. Die Live-Dateien bleiben unberührt.
- Jeder Lauf bekommt eine **Liste erlaubter Dateien**. Schreibversuche außerhalb werden abgelehnt.
- Das Modell arbeitet über **JSON-Schritte im Text**. So prüft der Inhaltsschutz jeden Schritt, und es gibt kein Sonderformat, das den Schutz umgeht.
- Jeder Schreibvorgang kommt ins Protokoll (Pfad und Größe, nie der Inhalt).
- **Übernahme ins Projekt** erfolgt erst nach Prüfung durch den Vorarbeiter und mit Freigabe durch den Captain.

**Prüfregeln** (`redesign_review.py`): keine Hex-Farben außerhalb der Tokens, höchstens 400 Zeilen je Datei, keine `fetch`- oder `localStorage`-Aufrufe in Werkzeugen, JavaScript muss syntaktisch gültig sein.

## 6. Redesign

**Phase A (abgeschlossen):** `uix/ui/tokens.css`. Die dunkle Palette „Deep Space Command“ ist der Standard. Das helle Thema „Klar“ bleibt erhalten. Ein Test prüft die Lesbarkeit (mindestens 5:1 auf Flächen, Sekundärtext 6,0:1). Der Umschalter startet auf „Nacht“.

**Plan:** `docs/REDESIGN_PLAN.md` mit Phasen A bis F.

**Offene Entscheidungen zum Redesign:** Akzentfarbe (Vorschlag Türkis, nicht NVIDIA-Grün), Stil der Desktop-Oberfläche, Kartenraster für alle Ansichten.

## 7. Läufe, die gerade laufen

- **Overhaul pro Shell:** Retro, Minimal, Paperclip, KI GateWay Studio, GUPPI XP und Start. Jede Shell hat einen eigenen Dateibereich und ein eigenes Modell. Ergebnisse stehen aus.
- **Spec-Lauf:** Drei Modelle entwerfen eine neue Shell **nur aus einer Spezifikation**, ohne bestehenden Code. Ergebnisse stehen aus.
- **Bewertung OmniRoute:** Ein Modell prüft, welche Bausteine für SEDRA nützlich sind. Ziel ist „Open Sedra“, eine Übernahme mit Namensnennung nach MIT-Lizenz. Die Bewertung wird vom Vorarbeiter geprüft.

Für alle Läufe gilt: **Die Ergebnisse werden geprüft, bevor etwas übernommen wird.**

## 8. Bekannte Probleme

- **Modell laden (lokal):** Der Fehler „provider_unavailable:load_failed:ValueError“ ist nicht geklärt. Die Meldung zeigt jetzt den Grund. Die Ursache ist offen. Bitte mit dem neuen Text melden.
- **Tests unter Windows:** Einige Tests (Wissensbasis, Chat-Tests, Arbeitsplatz) scheitern beim Aufräumen des Temp-Ordners, weil SQLite-Dateien noch offen sind. Der eigentliche Testlauf ist grün. Das ist ein Aufräumfehler, den wir beheben sollten.
- **Test `library_not_built`:** Der Bibliotheks-Index fehlt im Arbeitsordner.
- **Reasoning-Modelle:** Sie brauchen viele Tokens, sonst bleibt die Antwort leer. Die Grenzen sind entsprechend hoch gesetzt.
- **Anbieter-Überlastung:** Zeitüberschreitungen und 503-Fehler werden jetzt wiederholt.

## 9. Git-Stand

- Das lokale Repository hat den Commit `afcc0d9`. Er ist mit dem GitHub-Stand `main` zusammengeführt und auf GitHub gepusht. Das hatte der Captain freigegeben.
- **Danach ist viel nicht committet.** Wir sollten einen Commit machen, bevor weitere Änderungen dazukommen.

## 10. Sicherheitskopie

Vor den Redesign-Arbeiten: `Sicherheitskopie_GUPPI_Runtime_v1.20_2026-10-16_1105` im Projektordner. Enthält den Git-Verlauf und die Arbeitsdaten. Ohne den Ordner `engines` (rund 1,2 GB, reproduzierbar).

## 11. Hinweise für Klaus und Torsten

1. **Schlüssel:** Ein NVIDIA-Testschlüssel stand im Chat. Der Captain hat bestätigt, dass es ein Testschlüssel ist. Für den Produktivbetrieb sollte ein eigener Schlüssel verwendet werden.
2. **Personenbezug in der Cloud:** Entscheidung nach Regelwerk R-01 offen (siehe Abschnitt 3).
3. **Schreibzugriff des Cloud-Modells:** Grundsatzentscheidung des Captains, begrenzt auf den Arbeitsbereich. Wir sollten sie formal bestätigen.
4. **Externe Projekte:** Bevor Auszüge fremder Projekte an die Cloud gehen, prüfen wir Lizenz und Inhalt.

## 12. Verweise

- Redesign-Plan: `docs/REDESIGN_PLAN.md`
- Architektur: `docs/ARCHITEKTUR.md`
- Betrieb: `docs/BETRIEB.md`
- Verträge: Regelwerk `REGELWERK_DATENKATEGORIEN_CLOUDSPERRE_v0.1` (im Projekt unter `runtime/src/guppi_runtime/gateway/klassen.py`)

## 13. Entscheidungen (nachgetragen am 16.10.2026)

1. **Personenbezug in der Cloud:** Klaus fordert eine einheitliche Regel auf rechtlicher Grundlage. Bis diese vorliegt, gilt die Cloud für Personenbezug als nicht freigegeben. Der Inhaltsschutz wird entsprechend angepasst, sobald die Regel steht.
2. **Schreibzugriff des Cloud-Modells:** Der Captain gibt die Freigabe für den gewählten Arbeitsbereich (`workspace/GUPPI_OS/redesign/`). Live-Dateien sind davon ausgenommen. Übernahme nur nach Prüfung und Freigabe.
3. **Commit:** Stand `6c4d462` im lokalen Repository, nicht gepusht.

### Ergänzung: Freigabe Arbeitsbereich und Inhaltsschutz

- **Freigabe Schreibzugriff (Captain):** Arbeitsbereich ist die Shell und die Umgebung `E:\Sedra Umgebung\SEDRA_Build_024_Cockpit_Paperclip_Arbeitsplatz_2026-10-15\GUPPI_Runtime_v1.20`. Technisch schreibt ein Lauf nur in `workspace\GUPPI_OSedesign\` innerhalb dieses Ordners, pro Lauf mit Dateiliste. Live-Code wird nur nach Prüfung übernommen.
- **Inhaltsschutz, Personenbezug (Klaus):** Personenbezug geht nicht in die Cloud (Blockade statt Pseudonymisierung), bis eine einheitliche Regel auf rechtlicher Grundlage vorliegt. Betroffen sind Gespräch, KI Labor und Läufe. Begriffe aus fremden Auszügen (`redesign_prep.py`) entfernen Personenbezug vor dem Versand, nur Nicht-Personenbezogenes geht hinaus.
