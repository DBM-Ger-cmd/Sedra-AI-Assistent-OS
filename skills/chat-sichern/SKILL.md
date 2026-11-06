---
name: chat-sichern
description: Den Stand und das Wissen eines Chats sichern, bevor er mit /clear gelöscht wird (Wissensdatei, Projektnotizen, Logbuch, Commit). Nutzen, wenn der Captain "Chat sichern" sagt oder einen Chat beenden will.
---

# Chat sichern

Der Captain löscht Chats mit `/clear` und will eine einzige Anlaufstelle. Gesichert wird, was eine neue Sitzung braucht, um ohne den Verlauf weiterzumachen. Erst wenn alles geschrieben ist, sagst du "gesichert" und der Captain darf löschen.

## Ablauf
1. **Stand erfassen (nur lesen):** `git status`, `git log --oneline -10`, `git branch -a`, `git worktree list`, Abstand zu `origin/main`. Laufende oder wartende Sitzungen (`list_sessions` mit `linked`), offene Anträge im Posteingang, Teststand mit Zahlen.
2. **Wissensdatei** `docs/WISSEN_SEDRA_GESAMT.md`: neuen Abschnitt "Arbeit im Chat vom <Datum> (<Thema>)" vor dem Abschnitt "Alle Chats" einfügen, die Liste der Sitzungen ergänzen, "Offene Punkte" aktualisieren. Inhalt: was gebaut wurde (Commits, Dateien, Zahlen), Entscheidungen des Captains mit Datum, Fallen und Befunde, was offen ist. Zahlen nur mit Quelle (Testlauf, Commit), nichts schätzen.
3. **Projektnotizen (Memory):** vorhandenen Eintrag zum Thema aktualisieren statt neuen anzulegen; Überholtes als überholt markieren; Lektionen als eigene Notiz (Typ `feedback` oder `reference`) mit Warum und Wann anwenden. Danach die Zeile im Index `MEMORY.md` prüfen (eine Zeile je Notiz, ohne Inhalt).
4. **Logbuch** `docs/LOGBUCH_AGENT_MANAGER.md`: eine Zeile `| JJJJ-MM-TT HH:MM | BAU | Text | Bezug |`, Uhrzeit aus `date`, Datei hat CRLF.
5. **Verlauf exportieren (optional, nur auf Wunsch):** `export_transcript` der Sitzung in einen Ordner außerhalb des Repos. Nie einchecken: Verläufe können Schlüssel oder Personendaten enthalten.
6. **Committen:** nur Wissensdatei und Logbuch (und neue Specs oder Berichte aus dem Chat), mit Co-Author-Zeile. Nichts pushen, keine Tags.
7. **Rückmeldung** in wenigen Zeilen: was wo gesichert ist (Dateien, Commit), was offen bleibt, welche Branches und Worktrees noch gebraucht werden. Erst danach "gesichert".

## Regeln
- Keine lokalen Laufwerks- oder Benutzerpfade in eingecheckte Dateien, dort Platzhalter wie `<guppi>` (`docs/ENTWICKLUNG.md` Regel 10). In den Projektnotizen dürfen Pfade stehen, sie liegen nicht im Repo.
- Keine Schlüssel, Tokens oder Zugangsdaten schreiben, auch nicht in Notizen.
- Nichts erfinden: was nicht geprüft wurde, steht als "nicht geprüft" da.
- Nichts löschen, keine Notiz überschreiben, ohne sie vorher gelesen zu haben.
