# Inventar SEDRA-MOD-01: App-Verträge (tool.yaml Manifeste)

**Auftrag:** A-004  
**Branch:** hermes-a004  
**Worktree:** `<benutzer>/wc_hermes_a004`  
**Datum:** 2026-11-14  
**Quellen:**  
- `docs/ROADMAP_ONE_SEDRA_APPS_KERN_SHELL_2026-11-05.md` Abschnitt 5 (Manifest-Skizze v1.1)  
- `docs/SPEC_APPS_v1_AM1_ZELLEN_UND_SHELLS.md` (Vertrag 1.1, AM1)  
- `docs/SPEC_APPS_v1_AM0_HAERTUNG.md`, `docs/SPEC_APPS_v1_AM3_BERECHTIGUNG.md`, `docs/SPEC_APPS_v1_AM8_VERZEICHNIS.md` (weitere Vertragsfelder)  

**Suchpfade:**  
- `runtime/src/sedra_runtime/uix/shells/` – keine `tool.yaml` vorhanden (nur `shell.yaml`, `arbeitsplatz.yaml`)  
- `runtime/src/sedra_runtime/uix/tools/` – **53 Manifeste** gefunden (Ordner `_template` ausgeschlossen)  
- `architecture/...` und `runtime/tests/fixtures/...` – nicht Teil der Laufzeit, ignoriert  

---

## 1. Übersicht

| Metrik | Wert |
|--------|------|
| **Gefundene Manifeste (tool.yaml)** | **53** |
| Davon `kind: instrument` | 14 |
| Davon `kind: object` | 38 |
| Davon `kind: panel` | 1 |
| `trust: CORE` | 52 |
| `trust: CAPTAIN` | 1 (`rahmen-probe`) |
| Manifeste mit `zelle` | 14 (alle Instrumente) |
| Manifeste mit `shells` | 5 (nur Harness-spezifische Instrumente) |
| Manifeste mit `gruppe` | 2 (`scenario`, `workflow`) |
| Manifeste mit `profile` | **0** |
| Manifeste mit `rechte` | **0** |
| Manifeste mit `woerter` | **0** |
| Manifeste mit `abhaengig_von` | **0** |
| Manifeste mit `update` | **0** |

---

## 2. Vollständige Tabelle aller Manifeste

Legende: ✓ = Feld vorhanden, – = Feld fehlt, n/a = nicht anwendbar (z. B. `zelle` nur bei `kind: instrument`)

| # | id | kind | trust | gruppe | zelle | shells | profile | rechte | woerter | abhaengig_von | update |
|---|----|------|-------|--------|-------|--------|---------|--------|---------|---------------|--------|
| 1 | agentfenster | object | CORE | – | – | – | – | – | – | – | – |
| 2 | board | object | CORE | – | – | – | – | – | – | – | – |
| 3 | boundaries | object | CORE | – | – | – | – | – | – | – | – |
| 4 | candidate | object | CORE | – | – | – | – | – | – | – | – |
| 5 | costs | object | CORE | – | – | – | – | – | – | – | – |
| 6 | crew | object | CORE | – | – | – | – | – | – | – | – |
| 7 | decisions | object | CORE | – | – | – | – | – | – | – | – |
| 8 | entwurf | object | CORE | – | – | – | – | – | – | – | – |
| 9 | files | object | CORE | – | – | – | – | – | – | – | – |
| 10 | fundstelle | object | CORE | – | – | – | – | – | – | – | – |
| 11 | gateway | object | CORE | – | – | – | – | – | – | – | – |
| 12 | gauge-cloud | instrument | CORE | – | ✓ | – | – | – | – | – | – |
| 13 | gauge-decisions | instrument | CORE | – | ✓ | – | – | – | – | – | – |
| 14 | gauge-gpu | instrument | CORE | – | ✓ | – | – | – | – | – | – |
| 15 | gauge-mode | instrument | CORE | – | ✓ | – | – | – | – | – | – |
| 16 | gauge-model | instrument | CORE | – | ✓ | – | – | – | – | – | – |
| 17 | gauge-ram | instrument | CORE | – | ✓ | ✓ `[harness]` | – | – | – | – | – |
| 18 | gauge-scheduler | instrument | CORE | – | ✓ | ✓ `[harness]` | – | – | – | – | – |
| 19 | gauge-server | instrument | CORE | – | ✓ | ✓ `[harness]` | – | – | – | – | – |
| 20 | gauge-slots | instrument | CORE | – | ✓ | – | – | – | – | – | – |
| 21 | gauge-state | instrument | CORE | – | ✓ | – | – | – | – | – | – |
| 22 | gauge-tasks | instrument | CORE | – | ✓ | – | – | – | – | – | – |
| 23 | gauge-temp | instrument | CORE | – | ✓ | ✓ `[harness]` | – | – | – | – | – |
| 24 | gauge-vram | instrument | CORE | – | ✓ | ✓ `[harness]` | – | – | – | – | – |
| 25 | gauge-wissen | instrument | CORE | – | ✓ | – | – | – | – | – | – |
| 26 | intent | object | CORE | – | – | – | – | – | – | – | – |
| 27 | labor | object | CORE | – | – | – | – | – | – | – | – |
| 28 | library | object | CORE | – | – | – | – | – | – | – | – |
| 29 | live | object | CORE | – | – | – | – | – | – | – | – |
| 30 | logbook | object | CORE | – | – | – | – | – | – | – | – |
| 31 | meter | object | CORE | – | – | – | – | – | – | – | – |
| 32 | modules | object | CORE | – | – | – | – | – | – | – | – |
| 33 | nachrichten | object | CORE | – | – | – | – | – | – | – | – |
| 34 | org | object | CORE | – | – | – | – | – | – | – | – |
| 35 | planung | object | CORE | – | – | – | – | – | – | – | – |
| 36 | rahmen-probe | instrument | CAPTAIN | – | – | – | – | – | – | – | – |
| 37 | rekorder | object | CORE | – | – | – | – | – | – | – | – |
| 38 | routines | object | CORE | – | – | – | – | – | – | – | – |
| 39 | scenario | object | CORE | ✓ `arbeit` | – | – | – | – | – | – | – |
| 40 | schutz | object | CORE | – | – | – | – | – | – | – | – |
| 41 | slots | object | CORE | – | – | – | – | – | – | – | – |
| 42 | system | object | CORE | – | – | – | – | – | – | – | – |
| 43 | talk | panel | CORE | – | – | – | – | – | – | – | – |
| 44 | task | object | CORE | – | – | – | – | – | – | – | – |
| 45 | team | object | CORE | – | – | – | – | – | – | – | – |
| 46 | tests | object | CORE | – | – | – | – | – | – | – | – |
| 47 | transkript | object | CORE | – | – | – | – | – | – | – | – |
| 48 | translator | object | CORE | – | – | – | – | – | – | – | – |
| 49 | uebersetzer | object | CORE | – | – | – | – | – | – | – | – |
| 50 | uebersicht | object | CORE | – | – | – | – | – | – | – | – |
| 51 | wissen | object | CORE | – | – | – | – | – | – | – | – |
| 52 | workflow | object | CORE | ✓ `arbeit` | – | – | – | – | – | – | – |
| 53 | workshop | object | CORE | – | – | – | – | – | – | – | – |

---

## 3. Detail: Vorhandene Vertragsfelder (Auszug)

### 3.1 `zelle` (14 Manifeste, alle `kind: instrument`)

| id | zelle.feld | zelle.label | zelle.ort | zelle.aktion | zelle.quelle |
|----|------------|-------------|-----------|--------------|--------------|
| gauge-cloud | cloud | "Online-KI" | – | – | – |
| gauge-decisions | decisions | "Freigaben" | – | freigaben | – |
| gauge-gpu | gpu | "GPU" | hardware | – | – |
| gauge-mode | mode | "Modus" | boundary | – | – |
| gauge-model | model | "Modell" | models | modellmenue | – |
| gauge-ram | ram | "RAM frei" | hardware | – | – |
| gauge-scheduler | scheduler | "Scheduler" | slots | – | – |
| gauge-server | server | "Modellserver" | models | modellmenue | – |
| gauge-slots | slots | "Slots" | slots | – | – |
| gauge-state | state | "Zustand" | machine | "einstellungen:system" | – |
| gauge-tasks | tasks | "Aufgaben" | tasks | – | – |
| gauge-temp | temp | "Temp" | hardware | – | gpu |
| gauge-vram | vram | "VRAM belegt" | hardware | – | gpu |
| gauge-wissen | wissen | "Wissen" | wissen | – | – |

### 3.2 `shells` (5 Manifeste)

| id | shells |
|----|--------|
| gauge-ram | `[harness]` |
| gauge-scheduler | `[harness]` |
| gauge-server | `[harness]` |
| gauge-temp | `[harness]` |
| gauge-vram | `[harness]` |

### 3.3 `gruppe` (2 Manifeste)

| id | gruppe |
|----|--------|
| scenario | `arbeit` |
| workflow | `arbeit` |

### 3.4 `grundfunktion` (7 Manifeste – Vorläufer von `rechte`/`profile`)

| id | grundfunktion |
|----|---------------|
| boundaries | `modus_grenzen` |
| decisions | `entscheidungen` |
| logbook | `logbuch` |
| modules | `module_berechtigungen` |
| system | `einstellungen_zustand` |
| talk | `gespraech` |
| task | `aufgaben` |

### 3.5 `gedaechtnis` (2 Manifeste – Vertrag 1.1)

| id | gedaechtnis |
|----|-------------|
| fundstelle | `[sitzung]` |
| wissen | `[sitzung, ablage]` |

### 3.6 `instanzen` (4 Manifeste)

| id | instanzen |
|----|-----------|
| agentfenster | `viele` |
| scenario | `viele` |
| team | `viele` (App-Platzhalter) |
| workflow | `viele` |

### 3.7 `zweck` (1 Manifest)

| id | zweck |
|----|-------|
| rahmen-probe | `pruefung` |

### 3.8 `needs.ui` Versionen

| Version | Anzahl |
|---------|--------|
| `">=1.0 <2"` | 48 |
| `">=1.1 <2"` | 5 (gauge-ram, gauge-scheduler, gauge-server, gauge-temp, gauge-vram) |

---

## 4. Abweichungen vom Vertrag v1.1 (Roadmap Abschnitt 5, SPEC_APPS_v1_AM1)

### 4.1 Die fünf wichtigsten Abweichungen

| # | Abweichung | Betroffene Manifeste | Schwere | Begründung / Hinweis |
|---|------------|----------------------|---------|----------------------|
| **1** | **`profile` fehlt komplett** (0/53) | Alle 53 | **Kritisch** | Vertrag v1.1 verlangt `profile: [standard, kmu, stick]` als zweites Feld neben `shells` (Roadmap Entscheidung 1: "`profile:` kommt als zweites Feld dazu"). Ohne `profile` kann keine App-Zuordnung zu Profilen (Standard, KMU, Stick) erfolgen. Blockiert A2 (Orte/Grundfunktionen) und A8 (KMU-Profil). |
| **2** | **`rechte` fehlt komplett** (0/53) | Alle 53 | **Kritisch** | Vertrag v1.1 (AM3) verlangt `rechte: [datei_lesen, modell_nutzen, ...]` als Berechtigungsliste (Stufe A/B/C). Fehlt in allen Manifeste. `grundfunktion` (7×) ist nur Vorläufer für Grundfunktionen, keine Rechte. Ohne `rechte` keine Berechtigungsseite (A4), kein Entzug, keine Freigabe-Klassen. |
| **3** | **`woerter` fehlt komplett** (0/53) | Alle 53 | **Hoch** | Vertrag v1.1 verlangt `woerter: [übersetze, translate]` für Chat-Trigger (AM2: Orte und Wörter aus Manifesten). Ohne `woerter` kann der Chat keine Apps über natürliche Sprache ansprechen. |
| **4** | **`abhaengig_von` fehlt komplett** (0/53) | Alle 53 | **Mittel** | Vertrag v1.1 verlangt `abhaengig_von: []` für Manifest-Abhängigkeiten (AM8: `needs.kern`, `needs.dateien`). Fehlt → keine Abhängigkeitsauflösung, kein Verzeichnis (A5). |
| **5** | **`update` fehlt komplett** (0/53) | Alle 53 | **Mittel** | Vertrag v1.1 verlangt `update: {weg: diff}` für Update-Strategie (AM9: Betrieb/Updater). Fehlt → kein Diff-basiertes Update, keine Prüfsummen-Validierung beim Stick-Bau (A9). |

### 4.2 Weitere Abweichungen (Detail)

| Feld | Soll (Vertrag v1.1) | Ist | Abweichung |
|------|---------------------|-----|------------|
| `shells` | Bei allen Manifeste (Default: alle Shells) | Nur 5/53 (nur Harness-Instrumente) | 48 Manifeste haben kein `shells` – per Vertrag Default "alle Shells", aber explizite Deklaration fehlt. |
| `zelle` | Bei allen `kind: instrument` Pflicht (AM1-05) | 14/14 ✓ | **Konform** – alle 14 Instrumente haben `zelle`. |
| `shells` bei Instrumenten mit `zelle` | Erwartet (AM1-01) | 5/14 haben `shells` | 9 Instrumente (cloud, decisions, gpu, mode, model, slots, state, tasks, wissen) haben `zelle` aber kein `shells` → Default "alle Shells", aber Cockpit/ Rahmen sollten sie per AM1-16 nicht zeichnen. |
| `trust` Werte | `CORE`, `SEDRA_BUILT`, `COMMUNITY`, `CAPTAIN` | `CORE` (52), `CAPTAIN` (1) | Kein `SEDRA_BUILT`, kein `COMMUNITY` – alle Laufzeit-Werkzeuge sind `CORE`. |
| `kind` Werte | `app`, `instrument`, `dienst`, `object`, `panel` | `object` (38), `instrument` (14), `panel` (1) | Kein `app`, kein `dienst` – Apps (translator, team, uebersicht) sind als `object` mit `api: []` modelliert. |
| `order` | Pflicht | 52/53 (1 fehlt: `schutz`) | `schutz` hat kein `order` – wird alphabetisch einsortiert. |
| `slot` | Bei `object` Pflicht (`inhalt` \| `nachweis`) | 25/38 `object` haben `slot` | 13 `object` ohne `slot` – Default unklar. |
| `instanzen` | Optional (`eine` \| `viele`) | 4/53 | Nur bei `agentfenster`, `scenario`, `team`, `workflow` gesetzt. |
| `tests` | Array von Testdateien | 36/53 | 17 Manifeste ohne `tests` (u. a. `nachrichten`, `planung`, `rahmen-probe`, `schutz`, `transkript`, `translator`, `uebersetzer`, `uebersicht`, `wissen`, `workflow`). |

### 4.3 Schreibweisen / unbekannte Werte

| Feld | Gefundene Werte | Vertrag-konform? | Hinweis |
|------|-----------------|------------------|---------|
| `kind` | `object`, `instrument`, `panel` | Teils | `app`, `dienst` fehlen (Apps als `object` modelliert) |
| `trust` | `CORE`, `CAPTAIN` | Teils | `SEDRA_BUILT`, `COMMUNITY` nicht genutzt |
| `shells` | `[harness]` | Ja | Nur ein Wert genutzt; `cockpit`, `minimal`, `gateway-kmu`, `sedra-xp`, `paperclip`, `fisch`, `wissensbasis`, `start` nie referenziert |
| `zelle.aktion` | `freigaben`, `modellmenue`, `routermenue`, `"einstellungen:system"` | Ja | Entspricht AM1-11 |
| `zelle.ort` | `hardware`, `models`, `boundary`, `slots`, `tasks`, `machine`, `wissen`, `slots` | Ja | Entspricht `ui/places.js` |
| `zelle.quelle` | `gpu` (bei `gauge-temp`, `gauge-vram`) | Neuer Wert | Nicht in AM1-05 spezifiziert; Erweiterung für abgeleitete Werte |
| `needs.ui` | `">=1.0 <2"`, `">=1.1 <2"` | Ja | Version 1.1 für neue Harness-Instrumente (RAM, Server, Scheduler, Temp, VRAM) |
| `grundfunktion` | 7 verschiedene Werte | Vorläufer | Nicht im Vertrag v1.1; wird durch `rechte` + `profile` ersetzt |

---

## 5. Zusammenfassung & Bewertung

| Kriterium | Status |
|-----------|--------|
| **Manifeste gesamt** | 53 |
| **Vertrag v1.1 konform** | **Nein** – Kernfelder `profile`, `rechte`, `woerter`, `abhaengig_von`, `update` fehlen **in allen** Manifesten |
| **AM1 (Zellen/Shells)** | **Teilkonform** – `zelle` bei allen Instrumenten ✓, `shells` nur bei 5/14 Instrumenten |
| **AM3 (Berechtigungen)** | **Nicht begonnen** – `rechte` fehlt überall |
| **AM8 (Verzeichnis/Abhängigkeiten)** | **Nicht begonnen** – `abhaengig_von` fehlt überall |
| **AM9 (Update/Stick)** | **Nicht begonnen** – `update` fehlt überall |
| **Apps als `app`/`dienst`** | **Nein** – Alle als `object` (Apps: `translator`, `team`, `uebersicht`) |

**Empfehlung:** Die Manifeste entsprechen dem Stand **vor** der Manifest-v1.1-Umstellung (AM1 teilweise, AM0/AM3/AM8/AM9 offen). Für One Sedra (A3 Apps) müssen **alle 53 Manifeste** um die fehlenden Vertragsfelder ergänzt werden. Priorität: `profile` + `rechte` (A2/A4), dann `woerter` (AM2), dann `abhaengig_von` + `update` (A5/A9).

---

## 6. Anhang: Dateilisten

### 6.1 Alle 53 Manifest-Dateien (relativ zu `runtime/src/sedra_runtime/uix/tools/`)

```
agentfenster/tool.yaml
board/tool.yaml
boundaries/tool.yaml
candidate/tool.yaml
costs/tool.yaml
crew/tool.yaml
decisions/tool.yaml
entwurf/tool.yaml
files/tool.yaml
fundstelle/tool.yaml
gateway/tool.yaml
gauge-cloud/tool.yaml
gauge-decisions/tool.yaml
gauge-gpu/tool.yaml
gauge-mode/tool.yaml
gauge-model/tool.yaml
gauge-ram/tool.yaml
gauge-scheduler/tool.yaml
gauge-server/tool.yaml
gauge-slots/tool.yaml
gauge-state/tool.yaml
gauge-tasks/tool.yaml
gauge-temp/tool.yaml
gauge-vram/tool.yaml
gauge-wissen/tool.yaml
intent/tool.yaml
labor/tool.yaml
library/tool.yaml
live/tool.yaml
logbook/tool.yaml
meter/tool.yaml
modules/tool.yaml
nachrichten/tool.yaml
org/tool.yaml
planung/tool.yaml
rahmen-probe/tool.yaml
rekorder/tool.yaml
routines/tool.yaml
scenario/tool.yaml
schutz/tool.yaml
slots/tool.yaml
system/tool.yaml
talk/tool.yaml
task/tool.yaml
team/tool.yaml
tests/tool.yaml
transkript/tool.yaml
translator/tool.yaml
uebersetzer/tool.yaml
uebersicht/tool.yaml
wissen/tool.yaml
workflow/tool.yaml
workshop/tool.yaml
```

### 6.2 Nicht berücksichtigte `tool.yaml` (außerhalb Laufzeit-Pfad)

```
architecture/SEDRA_Architecture_v1.17_RUNTIME_SYNC/tools/filesystem/tool.yaml
architecture/SEDRA_Architecture_v1.17_RUNTIME_SYNC/tools/git/tool.yaml
architecture/SEDRA_Architecture_v1.17_RUNTIME_SYNC/tools/hardware-manager/tool.yaml
architecture/SEDRA_Architecture_v1.17_RUNTIME_SYNC/tools/model-runtime/tool.yaml
architecture/SEDRA_Architecture_v1.17_RUNTIME_SYNC/tools/sandbox/tool.yaml
architecture/SEDRA_Architecture_v1.17_RUNTIME_SYNC/tools/shell/tool.yaml
architecture/SEDRA_Architecture_v1.20_SELF_DEVELOPMENT/tools/filesystem/tool.yaml
architecture/SEDRA_Architecture_v1.20_SELF_DEVELOPMENT/tools/git/tool.yaml
architecture/SEDRA_Architecture_v1.20_SELF_DEVELOPMENT/tools/hardware-manager/tool.yaml
architecture/SEDRA_Architecture_v1.20_SELF_DEVELOPMENT/tools/model-runtime/tool.yaml
architecture/SEDRA_Architecture_v1.20_SELF_DEVELOPMENT/tools/sandbox/tool.yaml
architecture/SEDRA_Architecture_v1.20_SELF_DEVELOPMENT/tools/shell/tool.yaml
architecture/SEDRA_Architecture_v1.20_SELF_DEVELOPMENT/tools/web/tool.yaml
runtime/tests/fixtures/rahmen_angriff/tool.yaml
```

---

*Erstellt im Worktree `hermes-a004` (Branch von `main`), ohne Code-Änderungen, nur Lesen und Dokumentieren. Nicht committet.*