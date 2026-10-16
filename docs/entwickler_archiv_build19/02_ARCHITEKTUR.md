# 02 – Architektur

Dieses Dokument beschreibt die Schichten von SEDRA so, wie sie im Quellcode liegen. Das Gesamtbild der älteren Teile (Jobs, Agent Manager, DevVM) steht ausführlich in `docs/ARCHITEKTUR.md`; hier liegt der Schwerpunkt auf dem, was seit Build 14 dazugekommen ist.

## Die Schichten auf einen Blick

```
┌──────────────────────────────────────────────────────────────────────┐
│ Oberfläche (uix/)        Shells · Werkzeuge · Rahmen (frame.js)      │
│                          Start-Shell · GUPPI XP · KI GateWay Studio  │
└───────────────┬──────────────────────────────────────────────────────┘
                │ HTTP, nur /api/… (Routen-Tabelle im Hub)
┌───────────────▼──────────────────────────────────────────────────────┐
│ Hub (uix_server.py: UIXHub) + desk/                                  │
│   Entscheidungen · Objekte · Registrierung · Vorgaben · Gateway      │
└───────┬───────────────────────────────┬──────────────────────────────┘
        │                               │
┌───────▼──────────────┐   ┌────────────▼─────────────────────────────┐
│ gateway/             │   │ models/                                  │
│ klassen · vorgang    │──▶│ ModelRouter.chat → Guard → Adapter       │
│ probe                │   │ structured.py (Schema-Zwang)             │
└──────────────────────┘   └────────────┬─────────────────────────────┘
                                        │ jeder Aufruf
┌───────────────────────────────────────▼──────────────────────────────┐
│ core/  (Kern: Guard, Inhaltsschutz, Audit, Missionen, b6core)        │
└──────────────────────────────────────────────────────────────────────┘
```

Die Regel: Die Oberfläche spricht nur über HTTP mit dem Hub. Der Hub spricht mit `desk/` und `gateway/`. Jeder Modellaufruf geht über den Router, und der Router geht über den Guard. Den Kern darf nichts aus den oberen Schichten importieren; das prüft ein Grenztest (`core_boundary.py`, Test `test_core_boundary_src`).

## Der Kern: `guppi_runtime/core/`

| Modul | Aufgabe |
|---|---|
| `guard.py` (`Guard`) | Entscheidet Aktionen der Missionen: erlauben, sperren, den Captain fragen |
| `content_guard.py` (`ContentGuard`) | Inhaltsschutz vor und nach jedem Modellaufruf (Build 16) |
| `content_policy.py` | Übersetzt Scan-Ergebnisse in Gruppen und Regeln |
| `audit.py` (`AuditLog`) | Hash-verkettete Audit-Kette; schreibt Ereignisse, nie Text |
| `b6core/` | Übernommener, geprüfter Fremdcode aus dem B6-KI-Gateway: Normalisierung, Regelscanner, Pseudonymisierung, Rückübersetzung. `HERKUNFT.sha256` belegt jede Datei. Kein Netz. |
| `registry.py`, `mission.py`, `step_journal.py`, `permission_levels.py` | Registrierung, Missionen, Schritt-Journal, Rechtestufen |

### Der Inhaltsschutz im Detail

- **Gruppen:** Die Scan-Ergebnisse fallen in Gruppen (zum Beispiel Zugang, Anweisung, versteckte Zeichen, Personenbezug). Gruppen sind **immer scharf**, wenn sie den Rechner verlassen würden, und bei der Route Cloud sowieso.
- **Modi:** `sandbox` ist scharf; `beobachten`, `vertraut` und ein unbestätigter Zustand beobachten nur (`MODE_SHARP`). Die Schärfe kommt aus dem Modus des Projekts (`sync_guard_mode`). Es gibt keinen zweiten Schalter.
- **Entscheidungen:** Ein Treffer, der eine Entscheidung braucht, erscheint in der einen Entscheidungsliste (`kind: content`) mit den Wegen *einmal* und *ablehnen*. „Einmal“ gilt für genau diesen Aufruf (Hash) für 600 Sekunden. Höchstens 50 Entscheidungen warten gleichzeitig (`MAX_PENDING`).
- **Ein Guard-Stopp** ist kein Anbieterfehler (`ContentGuardStop`). Er wird nicht als Ausfall des Modells gezählt.

## Modelle: `guppi_runtime/models/`

- **`router.py` (`ModelRouter`):** Die einzige Tür zu Modellen. `chat(mission_id, messages, provider, model, schema=None, **kwargs)`. Intern: `_guarded` prüft den Aufruf, `_once` führt ihn aus, bei `schema` gibt es eine Schleife mit höchstens drei Runden.
- **`structured.py`:** Eine flache Teilmenge von JSON Schema. `check_schema` lehnt alles ab, was die Adapter nicht sicher übersetzen. `validate` liefert deutsche Fehlersätze. `parse` entfernt Markdown-Zäune. Der Router hängt bei Bedarf einen Hinweis an den System-Prompt, setzt die Temperatur auf 0 und reicht `response_format` an den Adapter weiter.
- **Adapter:** `openai_local.py` (lokale OpenAI-kompatible Server), `llamacpp.py`, `lmstudio.py`, `llama_server_runtime.py`. Die Cloud ist in dieser Schicht nicht angebunden.

Wer ein neues Modell einbindet, schreibt einen Adapter und tut nichts am Guard. Die Prüfung sitzt im Router und gilt dann automatisch.

## Der Hub: `uix_server.py` und `desk/`

- **`UIXHub`** (`uix_server.py`) ist der HTTP-Server mit einer Routen-Tabelle. Lesende Routen (GET) und schreibende Routen (POST) sind getrennt aufgeführt. Eine neue Route gehört an eine Stelle dieser Tabelle, mit Kommentar, was sie tut.
- **`serve(project_root, architecture_root, port, open_browser, window, shell)`** startet den Server. Die Shell-Wahl (`shell`) kommt aus `uix_start.py`.
- **`desk/decisions.py`** führt alle Entscheidungen zusammen (Schalter, Routing, Schreibrouten, GateWay). `APPLY` ordnet jeder Entscheidungsart die Route zu, die sie nach dem Ja ausführt.
- **`desk/gateway.py`** liefert die Objekte und Karten für das GateWay, `desk/vorgabe.py` den Shell-Creator, `desk/registry.py` die Shell-Wahl und die Registrierung der Werkzeuge.

## Die Oberfläche: `guppi_runtime/uix/`

| Teil | Aufgabe |
|---|---|
| `ui/frame.js` + `frame.css` | Der Rahmen. Baut aus einer Vorgabe (`raster`) die Zonen: Leiste, Orte, Werkstück, Gespräch, Entscheidungen, leer. Vertragscode, nicht ändern ohne Test (`test_uix_frame`). |
| `ui/schema/vorgabe.schema.json` | Das Schema der Vorgabe-Datei. Dasselbe Schema zwingt das Modell beim Shell-Creator. |
| `ui/loader.js`, `ui/tokens.css` | Laden der Werkzeuge; Farben und Abstände nur als Token |
| `shells/` | Shells: `start`, `cockpit`, `minimal`, `paperclip`, `guppi-xp`, `gateway-studio`, `_template`, `_vorgabe` |
| `tools/` | Werkzeuge, die in Shells sitzen, u. a. `gateway`, `schutz`, `modules`, `decisions`, `task`, `logbook` |

Details zu Shells und Werkzeugen in `04_SHELLS_WERKZEUGE_VORGABEN.md`.

## Start: `uix_start.py` und die Startdateien

- `START_SEDRA.bat` (Windows) und `start_sedra.sh` (macOS/Linux) starten SEDRA. Ohne Argument öffnen sie die **Übersicht** der Oberflächen. Mit einem Namen (`cockpit`) starten sie direkt in diese Shell, nur für diesen Start. Mit `--gewaehlt` starten sie die in `uix.yaml` gewählte Shell.
- Die alten Startdateien `ERSTER_START.bat`, `START_GUPPI.bat` und `GUPPI_EINRICHTEN_UND_STARTEN.bat` sind entfernt; `START_SEDRA.bat` ersetzt sie.
- Ein bereits laufender Prozess wird mit PID und Paketordner gemeldet. Ein zweiter Start neben ihm wird verweigert (Build 18).

## Abhängigkeiten zwischen den Schichten (Prüfung)

- `core/` importiert nichts aus `models/`, `desk/`, `gateway/` oder `uix/`.
- `gateway/` importiert aus `core/` (Inhaltsregeln, b6core), nie aus `models/`. Den lokalen Modellaufruf bekommt der Vorgang als Funktion `complete_local` vom Hub übergeben; sie ruft den Router und damit den Guard.
- `uix/` spricht nur über HTTP. Shells und Werkzeuge haben keinen Python-Zugriff auf den Hub.

Diese Regeln prüft `core_boundary.py` automatisch; `test_core_boundary_src` nennt die Kernmodule ausdrücklich, damit ein neues Kernmodul bewusst aufgenommen wird.
