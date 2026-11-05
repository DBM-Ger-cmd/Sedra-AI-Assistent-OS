# Entwurf: Belohnungssystem und Lernen (05.11.2026)

Wunsch des Captains: Wörter wie „danke“ oder „das hast du gut gemacht“ sollen zeigen, welche Antworten gut waren, in der Wissensdatenbank landen und beim Programmieren helfen, wenn eine Lösung als besonders gut bewertet wird. Im Hermes-Agent gibt es dazu eine Vorlage mit einem lernenden System; sie ist gelesen und unten eingeordnet.

## 1. Gebaut: Belohnungssystem (Stufe L1)

- **Auslöser:** eine kurze Nachricht (höchstens 300 Zeichen) mit einem Lobwort, **direkt nach** einer zu Ende gekommenen Antwort. Wörter in `config/belohnung.yaml`, eigene in `local_config/belohnung.yaml` (`lob`, `lob_zusaetzlich`, `besonders_zusaetzlich`). „nicht gut gemacht“ und „kein danke“ zählen nicht, ganze Wörter nur.
- **Stufen:** ★ gute Antwort („danke“, „super“ …), ★★ besonders gut („perfekt“, „genau so“, „hervorragend“ …).
- **Was gespeichert wird** (`harness/belohnung.py`): ein Eintrag `belohnung` in der Sitzung (die Oberfläche zeigt das Zeichen an der Antwort, auch beim Wiederöffnen), ein Abschnitt in `runtime_data/harness/belohnungen/JJJJ-MM-TT.md` (Markdown: Zeit, Sitzung, Vorlage, Modell, kurzer Auszug der Frage und der Antwort), eine Zeile im Index, ein Audit-Ereignis `HARNESS_BELOHNUNG`.
- **Beim Programmieren:** hatte die Antwort Werkzeuge, steht im Eintrag **was gelöst wurde**: geänderte Dateien, ausgeführte Befehle und Läufe, Werkzeuge mit Anzahl (nur, was gelang). So lässt sich eine gelobte Lösung später nachschlagen („Gelöst in Dateien: …“).
- **Wissensdatenbank:** der Ordner `runtime_data/harness/belohnungen` ist eine Markdown-Quelle (Wurzel `projekt`, Stufe 1). Einstellungen → System → Info → „Gute Antworten in die Wissensdatenbank aufnehmen“ stellt den Antrag, der Captain gibt ihn im Posteingang frei.
- **Übersicht:** dieselbe Info-Seite zeigt die Zahl der guten Antworten, je Vorlage und je Modell, die letzten mit Frage und Lösung.
- **Grenzen:** das Merken hält nie eine Nachricht auf (jeder Fehler bleibt folgenlos); gelobt wird jede Antwort höchstens einmal; die Eintragsart zählt nicht in den Verlauf, der ans Modell geht.

## 2. Hermes: das lernende System („Rückblick“)

Der Skill `rueckblick` (Hermes, `skills/workflow/rueckblick/SKILL.md`) ist ein After Action Review mit **vier Fragen**: Was war geplant? Was ist tatsächlich passiert? Warum ist es so passiert (auch: warum hat Ticket, Umsetzung, Test oder Prüfung es nicht früher gefangen)? Was machen wir nächstes Mal besser (jede Maßnahme mit Zieldatei und dem genauen neuen Satz)? Merkmale:

- **Pflicht** nach jedem Ticket und **sofort** bei Vorfällen: Rückweisung durch den Prüfer, blockierter Commit, gescheiterter Test, **Korrektur durch den Nutzer**, Abweichung vom Plan.
- **Fakten sammeln, nicht erinnern:** Commit-Texte, Prüfberichte, Gate-Ausgaben, Nutzeraussagen.
- Ergebnis `docs/AAR/<ID>.md`, höchstens 30 Zeilen; Maßnahmen, die Regeln ändern, werden dem Nutzer **vorgeschlagen, nicht eigenmächtig** umgesetzt; Zugestimmtes wird eine Zeile in `docs/AAR/LESSONS.md`.
- Der **Planer liest `LESSONS.md` und die letzten drei Rückblicke** und baut die gelernten Regeln in das neue Ticket ein; Aufräumen: mehr als 3 Rückblicke → ältester ins Archiv, `LESSONS.md` über 25 Zeilen → Übernommenes ins Archiv.

## 3. Wie beides zusammenpasst (L2 bis L4 gebaut)

| Stufe | Inhalt |
|---|---|
| **L1 (gebaut)** | Lob erkennen, gute Antworten merken, Wissensdatenbank, Übersicht |
| **L2 (gebaut)** | **Korrekturen** als Gegenstück: Wörter wie „falsch“, „das stimmt nicht“, „so nicht“ merken die Antwort als korrigiert (⚑), gleiche Ablage. Lob und Korrektur sind zusammen die Fakten für den Rückblick |
| **L3 (gebaut)** | Vorlage **Rückblick** (`config/harness_vorlagen/rueckblick.*`, Werkzeug `belohnungen_lesen`) (aus Hermes übernommen und auf Sedra angepasst): liest Lob, Korrekturen, Audit und Commits einer Sitzung oder eines Tages, beantwortet die vier Fragen, schlägt Maßnahmen mit Zieldatei vor (Antrag im Posteingang), schreibt zugestimmte Regeln in `docs/AAR/LESSONS.md` |
| **L4 (gebaut)** | Die gelernten Regeln wirken: Bauagent und Vorarbeiter bekommen `LESSONS.md` (höchstens 25 Zeilen) in den Systemprompt, gute Lösungen werden bei ähnlichen Aufträgen über die Wissensdatenbank gefunden |

### Stand L2 bis L4 (05.11.2026)

- **L2:** `korrektur` in `config/belohnung.yaml` (eigene Wörter: `korrektur_zusaetzlich`); eine Korrektur geht vor dem Lob („danke, aber das ist falsch“), trifft auch eine abgebrochene oder fehlerhafte Antwort; Eintrag `belohnung` mit `urteil: korrektur`, ⚑ an der Antwort, die Worte des Captains stehen im Eintrag der Wissensdatenbank.
- **L3:** Vorlage **Rückblick** (vier Fragen, `docs/AAR/<ID>.md` höchstens 30 Zeilen, Maßnahmen nur mit dem Ja des Captains, eine Zeile je Regel in `docs/AAR/LESSONS.md`, Aufräumregeln wie bei Hermes); Chat-Werkzeug `belohnungen_lesen` (nur lesen, ohne Karte: Zeitraum, Art, Stichworte); in Bauagent, Oberflächen-Designer und MasterChat zum Nachschlagen guter Lösungen.
- **L4:** `schleife.system_prompt(…, regeln)`: die letzten höchstens 25 Zeilen aus `<Projekt>/docs/AAR/LESSONS.md` (höchstens 2 000 Zeichen) stehen im Systemprompt jeder Sitzung des Projekts, vor der Zusammenfassung; ohne Datei ändert sich nichts.

## 4. Vorhersagen beim Tippen (gebaut)

Aus den gelobten und korrigierten Antworten leitet die Eingabe Vorschläge ab (`belohnung.vorschlaege`, `GET /api/harness/vorschlaege`, `vorschlaege.js`):

- Beim Tippen (ab 3 Zeichen, kurz verzögert, nicht bei `/` und `@`) erscheinen unter dem Feld **Aufträge, die du schon einmal so gestellt hast und deren Antwort du gelobt hast** (★, ★★ vorn; die Vorlage, in der du gerade bist, zählt mit), bei Code mit den Dateien, in denen sie gelöst wurde (Klick auf die Datei hängt sie als `@pfad` an). **Klick oder Tab** übernimmt den ersten Vorschlag.
- Passt ein Auftrag zu einem, der **korrigiert** wurde (mindestens zwei Stichworte), steht darüber **⚑ Zuletzt korrigiert:** mit deinen Worten von damals.
- Ähnlichkeit: Anfang der Frage, gemeinsame Stichworte (mindestens zwei Drittel der getippten, das letzte unfertige Wort darf ein Wortanfang sein), ohne Füllwörter; höchstens 5 Vorschläge; nur lokal, nur aus den eigenen Einträgen.
- Abschalten oder anpassen: `vorschlaege: {an: false}` oder `max`, `min_zeichen` in `local_config/belohnung.yaml`.
