# Recherche: Ein Shell-Creator mit lokalem Modell – was es auf GitHub dafür gibt (15.10.2026)

**Captain, 02:41:** *„Gibt es ein Repo, mit dem wir unseren Shell-Creator verbessern können, so dass er ein richtiges Werkzeug wird,
das mit Prompt-Eingaben über das lokale Modell Shells erstellt und benötigte Programme und Funktionen in der Shell abbildet und baut?“*

Die Recherche lief am 15.10. zwischen 02:41 und 02:44 (danach keine weiteren Aufrufe, Captain-Entscheidung); vier Quellen
wurden nicht geholt (Outlines-Repo, smolagents-Repo, Open-Interpreter-Repo, OpenHands-SDK-Doku, Open-WebUI-Artefakte,
Adaptive Cards) – dafür stehen Zweitquellen. Stars und Lizenzen sind Stand der abgerufenen Seiten; Commit-Daten zeigte
GitHub nicht an. **Kurzurteil vorweg: Es gibt kein Repo, das man einbaut. Es gibt drei Muster, die man übernimmt, und eine
Mechanik (Schema-Zwang für lokale Modelle), die den Creator von einem Namensfeld zu einem Werkzeug macht.**

## 1. Was die Kandidaten sind

| Repo | Kategorie | Stars | Lizenz | Stack | Passung | Warum |
|---|---|---|---|---|---|---|
| [wandb/openui](https://github.com/wandb/openui) | Prompt → UI | 22,6k | Apache-2.0 | Python-Backend + Tailwind-Frontend; Ollama/LiteLLM/LocalAI | **nur Muster** | Erzeugt freies HTML aus Prompts – genau das, was unser Gate nicht durchlässt (Code von einem Modell ohne Vertrag). Zeigt aber den Ablauf „Prompt → Vorschau → nachbessern“. |
| [dyad-sh/dyad](https://github.com/dyad-sh/dyad) | lokaler App-Builder | 21,6k | Apache-2.0 + FSL für `src/pro` | Electron/Vite/React, Ollama | **nicht** | Baut React-Apps, Electron-App, gemischte Lizenz. |
| [stackblitz-labs/bolt.diy](https://github.com/stackblitz-labs/bolt.diy) | lokaler App-Builder | 19,9k | MIT (WebContainers kommerziell) | React Router, WebContainers, 22 Anbieter, Ollama/LM Studio | **nicht** | Wartungsmodus („keine neuen Features“), riesig, WebContainers-Lizenz. |
| [a2ui-project/a2ui](https://github.com/google/A2UI) | deklaratives UI-Protokoll | 16,7k | Apache-2.0 | JSON; Renderer Lit/React/Angular/Flutter | **Muster** | *Flache Liste von Komponenten mit IDs, Katalog vorab freigegebener Komponenten, Modell darf nur daraus wählen.* Jedes Modell, das JSON kann, reicht. Early preview (v0.9/1.0-rc). |
| [vercel-labs/json-render](https://github.com/vercel-labs/json-render) | Prompt → JSON → UI | 18,7k | Apache-2.0 | Zod-Katalog, Renderer für React/Vue/Svelte/Solid – **kein Vanilla** | **Muster** | `catalog.prompt()` erzeugt den System-Prompt aus dem Katalog; „KI kann nur Komponenten aus deinem Katalog nutzen“. Einhaltung wird nur per Prompt erzwungen. |
| [MCP-UI-Org/mcp-ui](https://github.com/MCP-UI-Org/mcp-ui) | Agent-UI-Protokoll | 5,2k | Apache-2.0 | TS/Ruby/Python; `<ui-resource-renderer>` Web Component; rawHtml/externalUrl/remote-dom | **nicht** | Liefert HTML/iframes von Servern – das ist der Weg, den unser Gate bewusst verschließt. |
| [mathuo/dockview](https://github.com/mathuo/dockview) | Zonen-Layout | n/a | MIT | `dockview-core`: **Vanilla TS, null Abhängigkeiten**, Serialisierung | **mit Umbau** | Einziger Layout-Manager ohne Framework. Aber: ein Build-Schritt (TS-Paket), eigene DOM-Hoheit – kollidiert mit dem Rahmen aus der Vorgabe-Spec. Nur, wenn wir freies Ziehen wollen. |
| [golden-layout/golden-layout](https://github.com/golden-layout/golden-layout) | Zonen-Layout | 6,7k | MIT | JS; v3 im `dev` „ziemlich instabil“ | **nicht** | Unsicherer Stand. |
| [caplin/FlexLayout](https://github.com/caplin/FlexLayout) | Zonen-Layout | 1,4k | MIT | nur React; JSON-Modell `row/tabset/tab` mit `weight` | **nur Muster** | Das JSON-Modell (Zeilen, Reiter-Sätze, Gewichte, `Model.fromJson/toJson`) ist ein gutes Vorbild für `raster:` in der Vorgabe. |
| [GrapesJS/grapesjs](https://github.com/GrapesJS/grapesjs) | Page-Builder | 26,3k | BSD-3 | Vanilla per `<script>`, CDN | **nicht** | Baut freie HTML-Seiten, nicht Zonen mit Werkzeugen nach Vertrag; groß. |
| [puckeditor/puck](https://github.com/puckeditor/puck) | Page-Builder | 13,5k | MIT | React | **nicht** | React. |
| [eclipsesource/jsonforms](https://github.com/eclipsesource/jsonforms) | Formular aus JSON Schema | 2,7k | MIT | React/Angular/Vue; „vanilla“ heißt dort React ohne Material | **nur Muster** | Formular aus Schema – wir brauchen das klein, selbst (Einstellungen eines Werkzeugs, Photocraft-Muster). |
| Ollama *structured outputs* ([Doku](https://docs.ollama.com/capabilities/structured-outputs)) | Schema-Zwang | – | – | `format: <JSON-Schema>` im `/api/chat`, auch über die OpenAI-kompatible API als `response_format` | **direkt** | Das lokale Modell liefert garantiert gültiges JSON gegen unser `vorgabe.schema.json`. Schema trotzdem in den Prompt, Temperatur 0. |
| llama.cpp **GBNF** ([grammars/README](https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md)) | Schema-Zwang | – | MIT | `json_schema` / `response_format` an `llama-server`; Grammatik aus JSON-Schema | **direkt** | Dasselbe für llama.cpp-Server. Grenzen: `additionalProperties` standardmäßig false, kein `patternProperties`, `pattern` muss `^…$` sein, verschachtelte `$ref` kaputt – unser Schema muss flach bleiben. |
| [dottxt-ai/outlines](https://github.com/dottxt-ai/outlines) | Schema-Zwang (Bibliothek) | 15,9k | MIT | Python; transformers, llama.cpp, exllama2, OpenAI | **nicht nötig** | Tut, was Ollama/llama-server schon serverseitig können; eine Python-Abhängigkeit mehr im Kern. |
| [567-labs/instructor](https://github.com/567-labs/instructor) | Schema-Zwang (Validierung + Retry) | 14,0k | MIT | Python, Pydantic, `from_provider("ollama/…")` | **nur Muster** | Das Muster „validieren, Fehler in den Prompt, erneut“ ist in zwanzig Zeilen selbst geschrieben; keine Abhängigkeit. |
| [huggingface/smolagents](https://github.com/huggingface/smolagents) | Agent schreibt Code | 28,8k | Apache-2.0 | Python, ~1 000 Zeilen Kern; Ollama; `LocalPythonExecutor` „keine Sicherheitsgrenze“ | **nicht** | Ein Agent, der Code ausführt – SEDRA hat dafür Brain, Guard und Sandbox schon; ein zweiter Agentenkern daneben wäre genau der zweite Weg. |
| [OpenHands](https://github.com/All-Hands-AI/OpenHands) | Agent (SDK) | 90k | MIT | Docker-Sandbox, LiteLLM | **nicht** | Braucht Docker, ist ein ganzes System. |
| [open-interpreter](https://github.com/OpenInterpreter/open-interpreter) | Agent | 68,6k | Apache-2.0 | neu in Rust, auf gehostete Modelle optimiert | **nicht** | Richtung weg von lokal. |
| aider | Agent (CLI) | – | Apache-2.0 | Python, Ollama | **nicht** | Terminal-Werkzeug, kein Einbettungsvertrag. |

Nicht bewertet (nicht abgerufen): Open WebUI Artifacts, tldraw make-real, screenshot-to-code, Adaptive Cards. Keines davon
ändert das Bild: alle erzeugen freies HTML/JS oder brauchen React.

## 2. Das Bild, das daraus entsteht

Die Prompt-zu-UI-Welt teilt sich in zwei Lager:

1. **„Das Modell schreibt Code“** (OpenUI, bolt, dyad, screenshot-to-code, smolagents). Mächtig, aber für SEDRA der falsche
   Weg: Code aus einem Modell ist fremder Code, und fremder Code geht durch das Gate (Captain, 14.10.). Ein Creator, der bei
   jeder Shell ein Gate mit Durchsicht braucht, ist kein Werkzeug für Einzelpersonen.
2. **„Das Modell wählt aus einem Katalog“** (A2UI, json-render). Das Modell liefert **Daten** – eine flache Liste von Bausteinen
   aus einem vorab freigegebenen Katalog –, ein Renderer baut daraus die Oberfläche. Kein Code entsteht, nichts geht durch
   das Gate, und die Ausgabe ist gegen ein Schema prüfbar. **Das ist exakt die Vorgabe-Spec** (`SPEC_SHELL_AUS_VORGABE_v1`):
   `shell.vorgabe.yaml` ist der Katalog-Output, `ui/frame.js` der Renderer, die sechs Inhalte sind der Katalog.

Die eine Mechanik, die der Spec fehlt und die die Recherche liefert: **Schema-Zwang beim lokalen Modell.** Ollama
(`format`) und llama-server (`json_schema`/`response_format`) erzwingen serverseitig, dass die Antwort unserem
`vorgabe.schema.json` entspricht – kein Parsen von Fließtext, kein „das Modell hat ein Feld erfunden“. Dazu das
Instructor-Muster: Schema-Fehler als Satz zurück an das Modell, höchstens drei Runden, danach ehrlich „ich konnte keine gültige
Vorgabe bauen“. Für llama.cpp muss das Schema flach bleiben (kein `patternProperties`, keine verschachtelten `$ref`).

## 3. „Benötigte Programme und Funktionen in der Shell abbilden und bauen“

Das ist der zweite Teil der Frage, und er ist ehrlich zu trennen:

| Ebene | Was der Creator tun kann | Woher |
|---|---|---|
| **Anordnung** | Aus „links Aufgaben, rechts das Gespräch, keine Instrumente“ eine Vorgabe machen – ohne Code | Vorgabe-Spec Schritt 1–3 + Schema-Zwang |
| **Funktion aus dem Bestand** | Welche der 23 Werkzeuge in welcher Zone liegen, welche Orte, welche Verben; Werkzeuge an/aus | Katalog = `/api/uix/modules` + Ortskunde |
| **Neue Funktion** | Ein Werkzeug, das es noch nicht gibt („zeig mir die GPU-Temperatur als Kurve“) – **das ist Code**, und Code ist fremd | Der Creator legt ein Gerüst aus der Vorlage an (gibt es), lässt GUPPI den Vorschlag schreiben, und **dann kommt das Gate** mit Durchsicht – genau wie bei jeder Lieferung von außen. Kein Repo ändert das; das ist die Regel 2 des Captains. |

Also: Anordnung und Bestand **ohne Gate**, neue Funktion **mit Gate**. Ein Creator, der das sauber trennt, ist ein richtiges
Werkzeug; einer, der es verwischt, ist OpenUI.

## 4. Drei Empfehlungen, in dieser Reihenfolge

1. **Schema-Zwang in den Modellaufruf (klein, zuerst).** `ModelRouter.chat` bekommt ein optionales `schema=`; die Adapter
   reichen es als `format` (Ollama) bzw. `response_format` (llama-server/OpenAI-kompatibel) durch. Validierung + Retry-Satz
   im Router (Instructor-Muster, ≤ 3 Runden). Geht durch den Inhaltsschutz wie jeder Aufruf. Nützt sofort überall, wo GUPPI heute
   JSON aus Fließtext kratzt.
2. **Der Rahmen aus der Vorgabe** (Spec Schritt 1), mit dem FlexLayout-Modell als Vorbild für `raster:` (Zeilen, Spalten,
   Gewichte) und dem A2UI-Prinzip *flache Liste, IDs, Katalog*. Abnahme: eine Vorgabe baut das Cockpit nach, 27/27.
3. **Der Creator als Werkzeug** (Spec Schritt 2–3): im Einstieg und im Werkzeug Module ein Gesprächsfeld „Beschreib deine
   Oberfläche“; GUPPI → Vorgabe (Schema-Zwang) → Vorschau → „So anlegen“ (Audit, kein Gate). Fehlt eine Funktion, sagt der
   Creator es und bietet das Gerüst mit Gate an. Dazu `uix_check --shell <id>` automatisch nach dem Anlegen.

**Was nicht kommen sollte:** dockview oder GrapesJS als Fremdbibliothek im Vertrag (Build-Schritt, DOM-Hoheit, Größe), ein
zweiter Agentenkern (smolagents, OpenHands), und jeder Weg, auf dem das Modell HTML/JS liefert.
