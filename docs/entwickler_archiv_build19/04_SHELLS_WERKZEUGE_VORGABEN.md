# 04 – Shells, Werkzeuge und Vorgaben

Die Oberfläche von SEDRA besteht aus **Shells** (ganze Arbeitsflächen) und **Werkzeugen** (Teile, die in einer Shell sitzen). Beide folgen einem Vertrag, der in `docs/SHELL_WERKZEUG_VERTRAG_v1.md` steht, mit Nachträgen zu Build 17 und 19.

## 1. Begriffe

| Begriff | Bedeutung |
|---|---|
| **Shell** | Eine komplette Oberfläche. Liegt in `uix/shells/<id>/` mit `shell.yaml`. Der Nutzer wählt sie im Einstieg. |
| **Werkzeug** | Ein Baustein mit eigener Oberfläche, in `uix/tools/<id>/` mit `tool.yaml`, `tool.js`, `tool.css`, `README.md`. Eine Shell zeigt Werkzeuge in Slots. |
| **Vorgabe** | Eine Datei `shell.vorgabe.yaml` mit der Aufteilung einer Shell (welche Zonen wo stehen). Der Rahmen baut daraus die Shell, ohne Code. |
| **Rahmen** | `uix/ui/frame.js` und `frame.css`. Vertragscode, der aus einer Vorgabe die Zonen baut. |
| **Objekt** | Etwas, das ein Werkzeug zeigt (Aufgabe, Entscheidung, Vorgang, Modell, Modul). Objekttypen stehen in `OBJECT_TYPES` (`desk/gateway.py`). |

## 2. Eine Shell mit Code

Vorlage: `uix/shells/_template/` (Dateien `shell.yaml`, `shell.js`, `shell.css`, `README.md`). Ausschnitt aus der Vorlage:

```yaml
shell:
  id: beispiel
  name: "Beispiel-Shell"
  description: "Ein Satz: welche Form sie dem Bildschirm gibt."
  version: 1.0.0
  entry: {js: shell.js, css: shell.css}
  provides: [dock, talk]     # welche Slots sie anbietet
  layout: {persist: browser}
  api:
    - GET /api/strip
    - GET /api/decisions
  trust: CAPTAIN
  needs: {ui: ">=1.0 <2"}
```

Die Shell-Datei `shell.js` arbeitet über den Vertrag mit dem Hub; sie ruft nur die in `api` genannten Routen auf. Eine Shell ohne Code, also aus einer Vorgabe, hat keine `entry`-, `provides`- und `api`-Angaben (Abschnitt 3).

**Regeln für eine Shell:**

- Die `id` gleicht dem Ordnernamen.
- Farben und Abstände nur über Token aus `ui/tokens.css`. Keine Hex-Werte im Werkzeug.
- Keine Keyframes, keine externen Skripte.
- Selektoren mit einem Präfix (`.t-<name>`), damit sich Werkzeuge nicht überschreiben.

## 3. Eine Shell aus einer Vorgabe (Build 17)

Eine Shell kann ohne Code entstehen, mit einer Vorgabe. Die Datei `shell.yaml` verweist auf `shell.vorgabe.yaml`:

```yaml
shell:
  id: gateway-studio
  name: "KI GateWay Studio"
  vorgabe: shell.vorgabe.yaml
  trust: CORE
```

Die Vorgabe (`shell.vorgabe.yaml`) beschreibt das **Raster** und einige Optionen. So sieht die Vorgabe des KI GateWay Studio aus (`uix/shells/gateway-studio/shell.vorgabe.yaml`):

```yaml
id: gateway-studio
name: "KI GateWay Studio"
raster: [leiste, "orte|werkstueck", gespraech]
leiste: {einblenden: rand}
orte: {einblenden: rand, breite: 220, liste: [gateway, decisions, tasks, boundary, logbook, modules]}
werkstueck: {nachweise: seitenleiste, nachweis_breite: 380}
gespraech: {art: zone, hoehe: 96}
entscheidungen: karte       # karte | werkzeug
suche: strg-k               # strg-k | feld | keine
start: {type: gateway, id: alle, title: KI GateWay}
```

Mögliche Werte: `nachweise` = `seitenleiste | umschalter | spalten | keine`; `gespraech.art` = `zone | schublade`; `einblenden` = `fest | rand`; `orte.liste` nur aus den bekannten Orten (`tasks`, `intents`, `boundary`, `decisions`, `models`, `library`, `crew`, `meter`, `logbook`, `hardware`, `machine`, `modules`, `project`, `gateway`).

**Zonen:** `leiste` (Status und Messwerte), `orte` (Ortskunde links), `werkstueck` (die Arbeit), `gespraech` (Chat unten), `entscheidungen` (wartende Entscheidungen), `leer` (Platzhalter). `werkstueck` muss vorkommen; jede Zone höchstens einmal. Zeilen werden von oben nach unten gelesen, Spalten mit `|` von links nach rechts.

**Der Rand (`einblenden: rand`):** Die Zone steht nicht im Raster. Sie liegt verborgen am Rand und fährt heraus, wenn der Zeiger den Rand anfährt (10 px links, 8 px oben) oder die Tastatur hineinkommt. Sie fährt zurück, wenn der Zeiger sie verlässt.

**Das Schema:** `uix/ui/schema/vorgabe.schema.json` beschreibt die Vorgabe als flache Teilmenge von JSON Schema. Dasselbe Schema erzwingt das lokale Modell beim Shell-Creator (Abschnitt 5), und `desk/vorgabe.check` prüft die Datei mit demselben Schema.

**Was eine Vorgabe nicht darf:** `entry`, `api` und `provides` in der Datei werden abgewiesen. Der Vermittler leitet `provides` ab und setzt `FRAME_API` selbst.

## 4. Werkzeuge

Ein Werkzeug hat `tool.yaml` mit Id, Name, Trust-Stufe, Slots, Objekttypen und Routen. Die Routen trennen lesend (GET) und schreibend (POST). Ein Werkzeug darf nur Routen nutzen, die in seinem Manifest stehen.

**Trust-Stufen:**

| Stufe | Bedeutung |
|---|---|
| `CORE` | Teil des Pakets, geprüft, darf alle Objekttypen nutzen |
| `CAPTAIN` | vom Captain gebaut oder freigegeben |
| `COMMUNITY` | von außen; Schreibrouten nur nach einem eigenen Gate (`/api/uix/trust`, Build 15) |

Ein Werkzeug, das nicht `CORE` ist und nicht aus dem Paket kommt, darf einen **eigenen Objekttyp** mitbringen (`own_types` im Manifest, Build 15). Die Shells öffnen jeden Typ über die Registrierung. Die Ortskunde und die Palette kennen ihn nicht, außer er ist eingetragen; das Werkzeug „Module“ sagt das dazu.

**Die Werkzeuge im Paket (Auswahl):**

| Werkzeug | Zweck |
|---|---|
| `gateway` | KI GateWay: die vier Stationen des Vorgangs (CORE, Build 19) |
| `schutz` | KI GateWay · Schutz: Nachweis, Schärfe, Zählungen, „Selbst ausprobieren“ (CORE, Build 19) |
| `decisions` | die eine Entscheidungsliste, auch für Inhaltsschutz-Entscheidungen |
| `task`, `intent`, `logbook`, `meter`, `costs` | Aufgaben, Absichten, Logbuch, Messwerte, Kosten |
| `modules` | Module anlegen, vorlegen, entfernen; Shell aus Vorgabe (Build 17) |
| `boundaries`, `live`, `system` | Grenzen, Live-Lage, Systemzustand |

Die vollständige Liste zeigt `uix/tools/` im Quellcode; jede Datei `README.md` erklärt das Werkzeug.

## 5. Der Shell-Creator (Build 17)

Der Creator macht aus einem **Satz** eine Vorgabe:

1. Der Nutzer schreibt, was die Oberfläche können soll („Ich will links meine Aufgaben, rechts die Entscheidungen …“), oder wählt eine von drei Vorlagen (Reiter, Fenster, Seiten).
2. `POST /api/uix/vorgabe` ruft das lokale Modell **mit Schema-Zwang** auf (`desk/vorgabe.py`, `propose`). Die Antwort muss das Schema erfüllen, sonst wird sie mit einem Fehlersatz wiederholt (höchstens drei Runden).
3. Die Vorgabe wird geprüft und als Vorschlag angezeigt. Es wird **nichts angelegt**. Der Audit-Eintrag `UIX_VORGABE_PROPOSED` enthält keinen Text.
4. „So anlegen“ legt die Shell an (Gerüst mit `vorgabe`). Eine neue **Funktion** bleibt Code und braucht ein Gerüst mit Gate.

Der Creator sitzt im Einstieg und im Werkzeug „Module“. Ohne Modell bleiben die Vorlagen nutzbar.

## 6. Prüfen: `uix_check`

`uix_check` prüft Shells und Werkzeuge im Browser-Modus gegen den Vertrag:

- `uix_check --shell <id>` prüft eine Shell; bei einer Shell aus Vorgabe leitet das Werkzeug das Profil selbst ab (`frame_profile`).
- `uix_check --vorgabe <datei>` prüft eine Vorgabe vor dem Anlegen.
- `uix_check --tool <id>` prüft ein Werkzeug mit eigener Sammlung.

Ergebnisse aus Build 19: Studio 29/29, Cockpit, Minimal und Paperclip je 29/29, GUPPI XP 3/3 (ehrlich: nur das Laden, Rest nicht geprüft). Das Ergebnis nennt jede nicht geprüfte Stelle.

## 7. Das Muster: Shell mit Rahmen, Werkzeug mit Verträgen

Ein typischer neuer Teil:

1. Werkzeug anlegen (`uix/tools/_template` kopieren), `tool.yaml` mit Routen ausfüllen.
2. Routen im Hub ergänzen (`uix_server.py`, Tabelle), jede mit Kommentar: lesend oder schreibend.
3. Shell anlegen: aus `_vorgabe` mit einer Vorgabe-Datei oder aus `_template` mit Code.
4. Tests: `test_uix_frame` für den Rahmen, `test_uix_shell_start` für den Einstieg, `uix_check` für Shell und Werkzeug.
5. Eintrag im `CHANGELOG`.

## 8. Der Einstieg

Die Start-Shell (`uix/shells/start/`) ist der Einstieg. Sie zeigt eine Karte je Oberfläche mit Bild, „Diese Oberfläche nehmen“, „Eigene anlegen“ (Vorlage, Audit) und „Von außen vorlegen“ (Gate). Das Gespräch liegt unten, die Entscheidungen rechts, sobald eine wartet. Der Einstieg öffnet keine Objekte.

Die Oberfläche **GUPPI XP** (`shells/guppi-xp/`) ist der alte Retro-Desktop als wählbare Karte. Sie führt auf `/retro` und baut nichts nach. Sie ist „archiviert“, aber über den Einstieg erreichbar (Build 18).

Ein Name hinter `START_SEDRA.bat` gilt nur für diesen Start. Die dauerhafte Wahl steht in `local_config/uix.yaml`; `START_SEDRA.bat --gewaehlt` startet sie.
