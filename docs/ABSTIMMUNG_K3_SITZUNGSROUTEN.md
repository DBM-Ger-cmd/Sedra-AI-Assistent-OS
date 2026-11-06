# ENTWURF – Abstimmung mit One Sedra K3: Sitzungsrouten aus den Prozess-Apps

| Feld | Wert |
|---|---|
| Von | Coder 2 (SEDRA-MOD-01/02) |
| An | One-Sedra-Chat (K3), über den Koordinator |
| Datum | 06.11.2026 |
| Basis | `2b13daa` (Git-Bundle, HEAD geprüft) |
| Art | **Entwurf, nichts gestellt, keine Datei geändert** |
| Herkunft | `NEW_AI_GENERATED`, Zitate `EXISTING_REUSE` |

## 1. Worum es geht

Die Apps „n8n Workflows“ (`workflow`) und „Szenario Studio“ (`scenario`) rufen zwei Routen der One-Sedra-Shell (`/api/harness/…`) auf. Damit hängen sie an Routen, deren Owner der One-Sedra-Chat ist. Ändert K3 diese Routen, ihre Antwortform oder die Vorlage, funktioniert der Knopf „Von SEDRA entwerfen lassen“ in beiden Apps nicht mehr. Coder 2 ändert daran nichts. Der Entwurf soll die Abhängigkeit festhalten, damit beide Seiten davon wissen.

## 2. Welche Routen, welche Dateien

| Route | Wo erlaubt | Wo aufgerufen | Was gesendet wird | Was erwartet wird |
|---|---|---|---|---|
| `POST /api/harness/sitzungen` | `uix/tools/workflow/tool.yaml` (`api:`), `uix/tools/scenario/tool.yaml` (`api:`) | `uix/ui/workflow-extras.js:80` (`sedraEntwerfen`) | `{vorlage: 'prozessmodellierer', titel: 'Prozess: …'}` (Titel höchstens 60 Zeichen) | Antwort mit Feld `id` (Sitzungs-ID `S-…`) |
| `POST /api/harness/sitzungen/<S-id>/nachricht` | dieselben Manifeste (`POST /api/harness/sitzungen/*`) | `uix/ui/workflow-extras.js:82` | `{text: <Auftrag + Beschreibung>}` | `{antwort_id}` laut `harness/api.py:14`; die App wertet nur den Sonderfall `status: 'kein_modell'` mit `grund` aus |

Auslöser in der Oberfläche: Knopf „Von SEDRA entwerfen lassen“ (`uix/ui/workflow-editor.js:92`). Beide Apps nutzen denselben Editor (`sedraWorkflowEditor.create`, `uix/tools/workflow/tool.js:3`, `uix/tools/scenario/tool.js:7`).

## 3. Woran die Apps auf Serverseite hängen (nur gelesen)

| Abhängigkeit | Beleg (`2b13daa`) | Owner |
|---|---|---|
| Wegemuster der Harness | `harness/api.py:98` `WEG` (`sitzungen`, `sitzungen/S-…/nachricht`) | One Sedra |
| Herkunftsprüfung für die Nachricht | `harness/api.py:101–103` `GESCHUETZT` enthält `sitzungen/S-…(/nachricht)`; Prüfung `herkunft_verlangt` (`:244`) mit `harness/herkunft.py` | One Sedra |
| Antwortform `kein_modell` | `harness/api.py:14` (Docstring), Handler `nachricht` (`:524`) | One Sedra |
| Freigabeklasse | `desk/freigabeklasse.py:279` `'POST sitzungen'` = H nur mit `erlaubnisse_bestaetigt`, sonst N; `:282` `'POST sitzungen/nachricht'` = N | gesperrt, Captain |
| Vorlage | `runtime/config/harness_vorlagen/prozessmodellierer.yaml`: Werkzeuge `datei_lesen, dateien_auflisten, suchen, erinnern, belohnungen_lesen, prozess_beantragen`, `rechte: {}`, `max_zuege: 8` | One Sedra |
| Antrag und Übernahme | `harness/antraege.py:23` `KIND_PROZESS`, `:142` `prozess_antrag`, `:159` `_prozess_anwenden` → `WorkflowStore.save` | One Sedra (Antrag), Coder 2 (Speicher `workflows/store.py`) |
| API-Allowlist der App | `desk/gateway.py` (Kopf `X-SEDRA-Tool`, Methode und Pfad gegen `api:`) | geteilt |

Die App sendet **kein** `erlaubnisse_bestaetigt`. Das Anlegen der Sitzung ist damit Klasse N und vergibt keine Rechte. Der Entwurf entsteht nur über den Antrag `harness_prozess` (Klasse H) im Posteingang.

## 4. Tests, die den Weg abdecken

| Test | Deckt | Lauf auf `2b13daa` |
|---|---|---|
| `tests/test_process_browser.py:197` | Sitzung mit Titel „Prozess: …“ und Vorlage `prozessmodellierer` aus der App | `NOT_RUN` (Browser-Bahn) |
| `tests/test_harness_prozess_antrag.py` | Antrag → Posteingang → Übernahme in den Bestand | PASS (im Desk-Lauf, 289/0 rot) |
| `tests/test_harness_vorlagen.py:58`, `:145`, `:188` | Vorlage `prozessmodellierer` vorhanden | nicht einzeln gelaufen (Gruppe `harness`) |

Lücke: Kein schneller Test (ohne Browser) prüft, dass die Manifeste von `workflow` und `scenario` diese zwei Routen erlauben und dass die Antwort ein `id` trägt.

## 5. Fragen an K3

1. Bleiben `POST /api/harness/sitzungen` und `…/sitzungen/<id>/nachricht` mit dieser Form (Eingabe `vorlage`, `titel` / `text`; Ausgabe `id` / `status: kein_modell`) im K3-Umbau stabil?
2. Bleibt die Vorlage `prozessmodellierer` mit dem Werkzeug `prozess_beantragen` bestehen?
3. Soll eine App überhaupt Harness-Sitzungen anlegen dürfen, oder will K3 dafür einen eigenen Weg (z. B. ein Verb über `/api/actions`)? Dann bräuchten beide Apps eine Anpassung. Das wäre ein eigener Auftrag für Coder 2, mit Reservierung.
4. Wenn K3 die Routen ändert: Wer passt `workflow-extras.js` an? `uix/ui/` ist für Coder 2 gesperrt.

## 6. Vorschlag (keine Umsetzung)

- Bis zur Antwort von K3 nichts ändern.
- Wenn K3 die Routen stabil hält: einen schnellen Vertragstest vorschlagen (Manifest erlaubt die Routen, `POST sitzungen` liefert `id`). Dateiort und Owner legt der Koordinator fest.
- Wenn K3 einen anderen Weg will: Interface-Request von K3 an Coder 2, danach Auftrag mit Reservierung für `uix/ui/workflow-extras.js` und die zwei Manifeste.
