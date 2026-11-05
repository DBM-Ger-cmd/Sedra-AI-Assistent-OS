# Roadmap One Sedra – UIX und Werkzeuge (Stand 05.11.2026)

Ergänzt `ROADMAP_ONE_SEDRA_RENEW_2026-11-05.md` (Phasen R0–R7, Unterchats U0–U9). Hier: was die Oberfläche (UIX) und die Chat-Werkzeuge noch brauchen.

## 1. Bestand

**UIX** (`runtime/src/guppi_runtime/uix/shells/harness/`): Shell, Seitenleiste, Verlauf, Eingabe mit Vorschlägen, Taskleiste (Temp/VRAM/RAM, Token, Cache), Start-Menü, Einstellungen (Modell, Erlaubnisse, Katalog, Hilfswerkzeuge, Token, Info), Aufgabe/Freigaben, Desktop Builder (Module, Start-Menü, Taskleiste, Layout, Profile), Rechtsklick „Im Chat anpassen“ (21 Module).

**Werkzeuge im Chat** (`harness/werkzeuge.py`, 20): `app_oeffnen`, `befehl`, `belohnungen_lesen`, `datei_aendern`, `datei_lesen`, `datei_schreiben`, `dateien_auflisten`, `desktop_lesen`, `erinnern`, `lauf_starten`, `lauf_status`, `lauf_stoppen`, `modell_entladen`, `modell_laden`, `projekt_beantragen`, `sitzungen_auflisten`, `sitzungen_aufraeumen`, `suchen`, `vorlage_beantragen`, `youtube_transkript`.

**Vorlagen:** bauagent, modellierer, pruefer, vorarbeiter, masterchat, desktop-designer, rueckblick.

## 2. UIX-Roadmap

| Stufe | Ziel | Inhalt | Prüfung |
|---|---|---|---|
| **X1 Alltag** | Das Gebaute fühlt sich fertig an | Neustart + Strg+F5; Builder und Profile am echten Sedra durchklicken; Bedienfehler sammeln; Schriftgrößen und Kontrast je Profil | Browser-Test an eigener Testinstanz, Playwright-Test laufen lassen |
| **X2 Apps statt Ansichten** | Shell-Funktionen als Apps in einem Rahmen | App-Rahmen (Titel, Menü, Zustand) einheitlich; Translator, Wissensbasis, Cockpit, Paperclip, Gateway als Apps; Start-Menü-Gruppen aus Manifesten (AM1/AM2) | je App ein Node-/Python-Test, Grundfunktionen bleiben sichtbar |
| **X3 Profile fertig** | Zuschnitt je Auftraggeber | Profil-Export/-Import, Prüfung beim Laden, Vorlagen KMU/Privat/Stick, Marke/Logo/Schrift/Startseite vollständig | Profil-Roundtrip-Test, Grundfunktionen nie ausblendbar |
| **X4 Bedienung** | Weniger Klicks | Tastaturkürzel, Befehlspalette, Vorschläge ausbauen (Dateien, Vorlagen), Rechtsklick-Module für alle Seiten, Layout-Rückgängig/Wiederholen im Builder | Bausteine-Tests, keine neuen setInterval außerhalb Taskleiste/Start-Menü |
| **X5 Barrierefreiheit und Sprache** | Nutzbar für Fremde | Tastaturbedienung, Fokusreihenfolge, Screenreader-Beschriftung, Deutsch/Englisch aus einer Textdatei | Prüfliste, Kontrastprüfung |
| **X6 Rollen sichtbar** | Nach Rolle schlanker | Ansicht nach Rolle (AM7), Berechtigungsseite, Richtlinie sichtbar | hängt an R3/R4 |

Regeln bleiben: keine Hex-Farben in Shell-CSS, `textContent` statt `innerHTML`, Dateien höchstens 400 Zeilen, `setInterval` nur in Taskleiste und Start-Menü.

## 3. Werkzeug-Roadmap

| Stufe | Ziel | Inhalt | Freigabe |
|---|---|---|---|
| **W1 Lücken schließen** | Jedes Werkzeug hat Karte, Wegeintrag, Test | `katalog.OHNE_KARTE` und `freigabeklasse.py` abgleichen; fehlende Tests ergänzen | Test `test_freigabe_vollstaendig` |
| **W2 Wissen** | Chat nutzt das Wissen | Werkzeuge `wissen_suchen` (Wissensdatenbank lesen), `wissen_beantragen` (Quelle vorschlagen, Freigabe im Posteingang); Betriebslog und gute Antworten dort abfragbar | lesen frei, Antrag mit Freigabe |
| **W3 Oberfläche** | Chat baut die Oberfläche mit | `desktop_aendern` (Profil/Layout ändern, nur als Vorschlag mit Vorschau, Übernahme per Freigabe), `profil_wechseln` | Vorschau + Ja |
| **W4 Lernen** | Lernschleife im Werkzeug | `rueckblick_schreiben` (Antrag für `docs/AAR/LESSONS.md`, Maßnahmen nur mit Zustimmung des Captains), `vorschlaege_pflegen` | Antrag |
| **W5 Hilfswerkzeuge ohne GPU** | Aufgaben auf der CPU | E1–E5 aus `PLAN_CPU_HILFSWERKZEUGE_2026-11-04.md` | je nach Plan |
| **W6 Außenwelt** | Dienste und Cloud | Dienste außerhalb des Prozesses (AM4), Langdock-Agenten ausgehend (AM6); jedes Werkzeug mit Rechten (AM3) | Berechtigung + Inhaltsschutz |
| **W7 Werkzeug-Verzeichnis** | Erweiterungen verwalten | Verzeichnis aller Erweiterungen (AM8), Wirkungsklassen, Update mit Diff | Betreiber-Richtlinie |

Regel für jedes neue Werkzeug: Schema in `SCHEMAS`, Zweig in `vorbereiten`/`ausführen`, Eintrag in `HARNESS_WEGE`/`HARNESS_UNTERWEGE`/`ROUTEN_HARNESS`, Regex `WEG`/`GESCHUETZT` in `harness/api.py`, Karte im Katalog (oder `OHNE_KARTE`), Test; Schreibwerkzeuge nie ohne Freigabe.

## 4. Zuordnung zu den Unterchats

| Unterchat | UIX | Werkzeuge |
|---|---|---|
| U1 Shell-Inventur | X2 Vorbereitung | – |
| U2/U3 Apps Translator, Wissensbasis | X2 | W2 |
| U4 Profile exportieren | X3 | W3 |
| U5/U6 Freigaben S4, Rechte | X6 | W1, W6 |
| U7 Lernen ausbauen | X4 | W4, W5 |
| U8 Stick aus Profil | X3 | – |
| neu **U10 Werkzeug-Lücken (W1)** | – | W1, parallel startbar, nur `harness/` und Tests |
| neu **U11 UIX-Alltag (X1)** | X1, X4 | – |

## 5. Reihenfolge

X1 und W1 sofort (klein, gefahrlos) → X2 mit W2 → X3 mit W3 → X4 und W4/W5 → X5 → X6 mit W6/W7 (nach Freigaben S4 und Rechten).
