---
name: sedra-app-anlegen
description: Eine neue Sammel-App (Reiter mit mehreren Modi) in der Harness-Shell von One Sedra anlegen - Ort in orte_kern.json, Shell-Eintrag, Startgruppe, Icon, Gateway, Platzhalter-Werkzeug, Spec und Test, am Beispiel der App Team. Nutzen, wenn eine Alt-Shell oder mehrere Werkzeuge als eine App in der Harness zusammengefasst werden sollen oder ein neuer Ort (places) entsteht.
---

# Sammel-App in der Harness-Shell anlegen

Vorbild ist die App Team (Commit `5b7c530`, `docs/SPEC_APP_TEAM_v1.md`): ein Reiter, oben eine Modusleiste, ein Überblick, der Karten aus mehreren Werkzeugen zeigt, dazu weitere Modi. Regeln für Dateigrenzen, Farben und Routen stehen im Skill `sedra-ui-vertrag`; dieser Skill gibt die Reihenfolge und die Stellen, die man leicht vergisst. Gearbeitet wird im eigenen Worktree (Skill `sedra-worktree`).

## Stellen, die zusammen geändert werden

Pfade unter `runtime/src/sedra_runtime/`.

1. **Ort:** `uix/ui/orte_kern.json` ist die Quelle. `uix/ui/places.js` wird daraus erzeugt, nie von Hand ändern. Danach prüfen, dass der Gleichlauf-Test grün ist.
2. **Shell:** `uix/shells/harness/shell.yaml` (Menüeintrag, `app.flaeche`), `start_gruppen.json` (Startseite), `app.js` (Einhängen der Fläche).
3. **Fläche:** `uix/shells/harness/<name>.js` und `<name>.css`. Modi als Liste, der gewählte Modus wird unter `sedra.harness.<name>.modus` im Browser gemerkt (in try/catch, die App muss auch ohne Speicher laufen). Keine eigenen Farben, nur Tokens.
4. **Platzhalter-Werkzeug:** `uix/tools/<name>/tool.yaml`, `tool.js`, `README.md`. Es trägt die App im Werkzeugverzeichnis, bis die Fläche alles übernimmt.
5. **Icon:** `uix/shells/minimal/icons.js`.
6. **Gateway:** `desk/gateway.py`, wenn die App Routen oder einen Ort anmeldet.
7. **Spec:** `docs/SPEC_APP_<NAME>_v1.md` mit Umfang und ausdrücklich "nicht gebaut".
8. **Test:** `tests/test_uix_<name>_app.py`, Vorbild `test_uix_team_app.py` (6 Tests). Browserteile nur mit `SEDRA_BROWSER=1`.

## Entscheidungen, die vorher feststehen müssen

- Zeigt die Fläche Daten anderer Werkzeuge, liest sie diese über deren vorhandene Routen. Keine zweite Datenhaltung.
- Eine alte Shell mit gleichem Inhalt bleibt unverändert, bis der Captain den Gleichstand abnimmt. Das steht in der Spec und im Register.
- Das Menü zeigt nur, was die App trägt (bei Team: nur Team).

## Prüfen

1. `python benchmarks/run_tests.py uix` mit `SEDRA_WISSEN_STANDARD=aus` und `PYTHONIOENCODING=utf-8`. Wackler `test_uix_workflow_live` (`id_required`) und `test_uix_shell_start` stehen auch auf `main` rot.
2. Mit `SEDRA_BROWSER=1` den neuen Browsertest einzeln laufen lassen.
3. Sichtprüfung mit dem Skill `sedra-ui-sichtpruefung`: Reiter öffnen, jeden Modus anklicken, Seite neu laden (Modus bleibt).
4. Melden, was nicht am PC geprüft wurde.

## Fallen

- `places.js` von Hand geändert: der nächste Lauf überschreibt es.
- Eine Fläche ohne Eintrag in `start_gruppen.json` erscheint nicht auf der Startseite.
- Windows: CRLF bleibt erhalten, Patch-Skripte mit dem Write-Werkzeug anlegen, keine Heredocs.
- Übergabe an `main` über den Skill `sedra-paket-ablauf`.
