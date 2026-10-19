# Plan: Isolation der Module und Auto-Update für SEDRA

**Stand:** 19.10.2026, nach dem Release `v1.21.0` (Tag auf Commit `afb414c`).
**Art:** reine Planung. Es ist noch nichts umgesetzt; jeder Schritt braucht eine Freigabe des Captains.
**Grundlagen:** `docs/REVIEW_ARCHITEKTUR_2026-10-19.md` (Abschnitt 9, Kern–Shell–Modul) und `docs/REVIEW_GESAMT_2026-10-19.md` (Befunde P3, P4, J2).

---

## 1. Ausgangslage (verifiziert im Code)

- **Freigabe-Route:** Werkzeuge beantworten Freigaben nicht mehr selbst (Entscheidung 2026-10-19). Die Rahmen-Route der Vorgabe-Shells (`desk/gateway.py`, `FRAME_API`) bleibt bestehen, weil die Entscheidungszone der Oberfläche sie braucht.
- **Routenliste:** Ein Werkzeug darf nur die Routen seines Manifests aufrufen, aber nur, wenn es den Kennzeichen-Header mitschickt (`uix/ui/api.js`).
- **Lücke P4:** `window.sedraApi` ist global, trägt den Token und lässt jede Modul-Kennung wählen (`uix/ui/api.js:37`). Modul-Code kann also direkt `fetch` nutzen und die Liste umgehen. Der Einbau-Prüfer erkennt `fetch` und `eval`, aber nicht `sedraApi` oder `location.hash`.
- **Fremdmodule:** Werden als COMMUNITY geladen; dort sind nur GET-Routen erlaubt (`uix/manifest`, `_common`). Die Installation läuft über ein Gate mit Hash-Prüfung.
- **Auto-Update:** Gibt es nicht. `updater.py` packt nur interne Entwicklungsläufe und lädt nichts.

## 2. Ziel

1. Module können die Kernfunktionen nur über einen festen, geprüften Weg erreichen, nicht über den Token.
2. Ein Fremdmodul kann keine Freigabe erteilen und keine fremden Routen aufrufen.
3. SEDRA lässt sich aus dem öffentlichen GitHub-Repository auf eine geprüfte Version aktualisieren, mit Freigabe, Sicherung und Rückweg.

## 3. Isolation der Module

### 3.1 Stufen (Entscheidung des Captains: erst die Routenliste, dann die Isolation)

| Stufe | Inhalt | Aufwand | Wirkung |
|---|---|---|---|
| **A: Routenliste erzwingen** | Jeder Modul-Aufruf geht über einen Kanal, der den Modulnamen setzt. `sedraApi` gibt Modulen nur noch die Funktion ihres eigenen Namens; der Token wird nicht mehr an Modul-Code gereicht. | klein–mittel | schließt die Umgehung über `sedraApi`, nicht über direktes `fetch` |
| **B: Prüfung der Modul-Quelle** | Der Einbau-Prüfer erkennt zusätzlich `sedraApi`, `location.hash`, `document.cookie`, `XMLHttpRequest`, dynamische `import()` außerhalb der Liste. | klein | erkennt bekannte Muster, kein Beweis |
| **C: Isolation** | Module laufen in einem `iframe` mit `sandbox` (ohne `allow-same-origin`) und sprechen per `postMessage` mit dem Kern. Der Kern prüft jede Nachricht gegen die Routenliste. | groß | echte Grenze; die Oberfläche muss umgebaut werden |

**Empfehlung:** Stufe A zuerst, dann Stufe B, Stufe C später als eigenes Projekt.

### 3.2 Schritte für Stufe A

1. Bestandsaufnahme: alle Aufrufe von `sedraApi` und `fetch` in `uix/tools` und `uix/shells` erfassen (Skript, read-only).
2. `sedraApi` so umbauen, dass der Token nie an Modul-Code geht. Die Kernseite (Rahmen, Shells) behält den Zugriff.
3. Für Module: Aufrufe nur über `call(path, options)`, Kennung wird vom Kern gesetzt.
4. Tests: ein Modul kann eine fremde Kennung nicht wählen; ein Modul ohne Route bekommt `403`; der Token ist in Modulcode nicht lesbar.
5. Bestehende Werkzeuge prüfen (Gateway, Gespräch, Schutz, Entscheidungen, Labor, Arbeitsplatz), dass sie weiter funktionieren.

**Stand Stufe A (umgesetzt, nicht committet bis zur Freigabe):** `window.sedraApi` gibt nur noch `forModule`, `api` (Kern) und `events`; der Token verlässt die Kernfunktionen nicht mehr. Der Loader übernimmt den Zugang beim Start und entfernt die globale Kopie. Werkzeuge außerhalb des Pakets bekommen die Shell ohne `decide`. Grenze: Code auf derselben Seite kann die Adresse lesen; die echte Grenze ist Stufe C. Die Browser-Tests der Oberfläche schlagen auch vor dieser Änderung fehl, sie sind noch nicht als Nachweis geeignet.

## 4. Auto-Update aus GitHub

### 4.1 Quelle und Versionen

- Repository: `https://github.com/DBM-Ger-cmd/Sedra-AI-Assistent-OS` (öffentlich).
- Nur Release-Tags (`vX.Y.Z`), nie der laufende Stand von `main`. Der erste Tag `v1.21.0` existiert.
- Jeder Release bekommt eine Prüfsummendatei (SHA-256 je Datei), die im Release veröffentlicht wird.

### 4.2 Ablauf

1. **Suche** (nur lesen): Nur auf Klick vergleicht SEDRA die installierte Version mit den Tags. Ist eine neuere Version da, zeigt SEDRA das mit Versionsnummer an. Das Update startet erst, wenn du es bestätigst (Entscheidung 2026-10-19).
2. **Vorschau:** Die Liste der geänderten Dateien, Größe und Version wird im Menü angezeigt. Nichts wird geschrieben.
3. **Freigabe:** Über das Gate im Menü, wie bei anderen Änderungen. Die Freigabe nennt die Version und die Dateien.
4. **Herunterladen** in einen eigenen Ordner, nicht ins Programm. Jede Datei wird gegen die Prüfsumme geprüft; schlägt eine fehl, wird nichts übernommen.
5. **Sicherung:** Der aktuelle Stand wird vollständig als Kopie gesichert (eigener Ordner mit Datum und Version).
6. **Übernahme** der geänderten Dateien, nur der Programmdateien. Geschützt und nie überschrieben: `local_config/`, `workspace/`, `runtime_data/`, Modelle, Schlüsselablage, `runtime/portable/`.
7. **Wirkung** nach dem Neustart von SEDRA. Schlägt der Start fehl, stellt der Starter die Sicherung wieder her.
8. **Rückweg:** Ein Knopf „Auf vorherige Version zurücksetzen“ nutzt die Sicherung; auch das ist eine Freigabe.

### 4.3 Sicherheitsregeln

- Keine Ausführung von Code aus dem Download, bevor er übernommen ist.
- Die Prüfsummen kommen aus demselben Release; das schützt nicht gegen einen Angriff auf das GitHub-Konto selbst. Wenn das wichtig ist, folgt später eine Signatur (z. B. signierte Tags).
- Updates dürfen Modulrechte ändern (Entscheidung 2026-10-19). Jede solche Änderung braucht eine eigene, ausdrückliche Freigabe, die sie beim Namen nennt, z. B. „Modul Gespräch: neue Route POST /api/xyz“. Ohne diese Freigabe wird der Rest des Updates übernommen, die Rechteänderung nicht.
- Eine Rechteänderung kann in einem Update auch Rechte entziehen; auch das wird einzeln genannt und freigegeben.

## 5. Reihenfolge

1. **Stufe A** der Isolation (Abschnitt 3.2), mit Tests.
2. **Update, Teil 1:** Suche und Vorschau (nur lesen, ohne Schreiben). Klein.
3. **Update, Teil 2:** Herunterladen, Prüfsumme, Sicherung, Übernahme, Rückweg. Mittel.
4. **Stufe B** der Isolation.
5. **Stufe C** (Isolation per `iframe`) als eigenes Projekt, nach Freigabe.

Begründung: Stufe A schließt die größte bekannte Lücke. Das Update braucht diese Grenze, damit ein neues Release keine Module mit mehr Rechten einführt.

## 6. Offene Fragen an den Captain

1. ~~Update-Suche automatisch oder auf Klick?~~ **Entschieden:** nur auf Klick, mit Hinweis auf die neue Version und Bestätigung vor dem Start.
2. ~~Besondere Freigabe für Rechteänderungen?~~ **Entschieden:** ja, eigene Freigabe mit Nennung jeder Änderung (Abschnitt 4.3).
3. Sollen Releases signiert werden, bevor das Update in den Alltag geht? *Empfehlung:* ja, vor dem ersten Update für andere Nutzer.
4. Reicht Stufe A als Zwischenstand, oder soll Stufe C direkt geplant werden? *Empfehlung:* Stufe A zuerst, C als eigenes Projekt.

## 7. Risiken

- Der Umbau von `sedraApi` kann Werkzeuge brechen. Gegenmittel: Tests je Werkzeug, Browserprüfung vor dem Release.
- Ein Update mit Fehlern kann SEDRA am Start hindern. Gegenmittel: Sicherung und automatischer Rückweg beim fehlgeschlagenen Start.
- Die Prüfsummen schützen gegen Übertragungsfehler, nicht gegen einen kompromittierten Release. Gegenmittel: Signatur (Frage 3).

## 8. Nicht im Plan

- Änderungen an der Ablage der Schlüssel (liegt in `v1.21.0` bereits gesichert).
- Der Kombi-Modus mit mehreren Schritten und Rückfragen.
- Die Rahmen-Route der Vorgabe-Shells; dazu gibt es eine eigene Entscheidung.
