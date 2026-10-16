# Auftrag an GUPPI: Ausbau des Fensters "GUPPI Chat" (2026-10-13, 14:34)

Captain-Wunsch: Fenster wie die Claude Desktop App (Sitzungsliste + Chat). Claude hat die Grundversion gebaut (`uix/js/claude_chat.js`, Fenster `cchatWindow` in `retro_desktop.html`, CSS am Ende von `desktop.css`). GUPPI baut den Ausbau selbst (Anteil GUPPI >= 50 %), Claude gibt nur Spezifikation und Abnahme.

Regeln: nur die betroffene Datei plus ihren Test anfassen, nur betroffene Tests laufen lassen, neue Tests in eine Testdatei (`tests/test_cchat_ui.py`). Klassische Skripte, kein Modulsystem. Vor dem Modellstart die GPU-Lease halten. Kein Push zu GitHub.

## Schritte (in dieser Reihenfolge, je ein eigener Lauf)

1. **Sitzungen im Server** (`uix_server.py`, neu `uix/cchat_store.py`): Endpunkte `GET /api/cchat/sessions`, `PUT /api/cchat/session/<id>`, `DELETE /api/cchat/session/<id>`; Dateien unter `runtime_data/cchat/<id>.json`; Id nur `[0-9]{10,16}`, Titel max. 80 Zeichen, max. 200 Sitzungen, Nachrichten max. 200 je Sitzung. `claude_chat.js` laedt/speichert darueber, localStorage nur noch als Fallback. Test: ungueltige Ids, Groessenlimits, Token-Header Pflicht.
2. **Streaming**: `POST /api/chat/reply_stream` liefert Server-Sent-Events (`data: {"delta": "..."}`, am Ende `{"done": true, "model": "..."}`); der Chat zeigt den Text waehrend des Eintreffens und hat einen Stopp-Knopf (AbortController). Fallback auf `/api/chat/reply`, wenn der Stream-Endpunkt fehlt.
3. **Verlauf**: aeltere Nachrichten (mehr als 8) als kurze Zusammenfassung mitsenden statt abzuschneiden; Grenze aus der Kontextmessung des geladenen Modells (`docs`/Memory "Kontextmessungen").
4. **Bedienung**: Chat umbenennen, Antwort kopieren / neu generieren, eigene Nachricht bearbeiten, "Kopieren"-Knopf an Code-Bloecken, Markdown fuer Listen, Ueberschriften, Tabellen (weiter alles vorher escapen).
5. **Aus dem alten Chat uebernehmen**: Anhaenge (`/api/chat/attach`), "Als Auftrag planen" (`planCard`), Slash-Befehle (`slashCommand`, `runDiagCommand`).
6. **Kontextanzeige** (Fuellstand des Kontextfensters) und **Token-Verknuepfung** mit dem Guppy-Meter (Chat-Token fallen ins Tokenloch).

## Abnahme (Claude)
Fensterstart ohne Konsolenfehler, Chat anlegen/umbenennen/loeschen, Neustart behaelt die Sitzungen, Stream laeuft und laesst sich stoppen, `node --check` je Skript, betroffene Tests gruen. Keine Strings aus Modellantworten ungeprueft als HTML.
