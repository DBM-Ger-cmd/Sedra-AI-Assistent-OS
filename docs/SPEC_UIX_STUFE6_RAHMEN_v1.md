# SPEC UIX Stufe 6 – Rahmen, Gespräch, Stimmigkeit, kleine Bildschirme v1 (27.10.2026)

Stand: Zweig `uix-stufe1-vertrag` auf `origin/main` = `4ecd343` (Stufen 1–5 neu aufgesetzt, Tests wie vorher).
Auftrag des Captains 27.10.2026, 08:27: „lass uns auf der Grundlage weiter am UIX arbeiten“; gewählt: A, B, C, D – erst Spec, dann bauen.
Befund aus einer Durchsicht aller Shells bei 1400×860 und 1024×700 (Chromium, Prüfprojekt). Keine Konsolenfehler, kein waagerechtes Rollen.

## 1. Befund

| Nr | Befund | Wo |
|---|---|---|
| A1 | **Die Leiste ist voll.** 11 Zellen (Zustand, Modell, Online-KI, GPU, Entscheidungen, Aufgaben, Modus, Wissen, Slots, Rahmen-Probe, „?“). Bei 1024 px ist fast jeder Wert abgeschnitten („Modell kein…“, „Online-KI Cl…“, „Modus nicht…“). Bei 1400 px sind es noch drei. | `cockpit/strip.js`, `ui/frame.js` (Leiste), paperclip Dashboard |
| A2 | **Ein Prüfwerkzeug ist für den Captain sichtbar.** „Rahmen-Probe“ (Stufe C, prüft den abgeschotteten Rahmen) steht als Zelle in jeder Leiste und als Kachel im Paperclip-Dashboard, in Serifenschrift („Jeder verbotene …“). | `tools/rahmen-probe`, `kind: instrument` |
| A3 | **Schwebende Knöpfe überdecken den Inhalt.** „Rekorder“ und der Shell-Umschalter liegen fest rechts unten über dem Werkstück: in der Wissensbasis über der Fundstelle, in Minimal über dem Gesprächsfenster, in paperclip zusätzlich über „Mit SEDRA sprechen“. | `ui/wechsel.js`, `.sx-host` |
| A4 | Die Zelle „SEDRA READY“ schneidet ihr Bild oben ab (seit die Leiste in Rahmen-Shells fest hoch ist). | `gauge-state` |
| B1 | **„Leeren“ im Gespräch löscht den ganzen Verlauf mit einem Klick** – direkt neben „Senden“, ohne Rückfrage, auch auf dem Server. | `tools/talk` |
| B2 | **„Grüne zuerst“** ist ohne Erklärung nicht verständlich (es sortiert die Modelle mit grüner Ampel nach oben). Der Knopf steht in jeder Shell neben „Senden“. | `tools/talk/tool.js` |
| C1 | **Zwei Zahlen für „offen“.** Werkzeug Aufgaben: „3 offen“; Baum: „2 offen“. Ein Freigabe-Antrag (z. B. „Wissensquelle freigeben … – angenommen“) zählt im Werkzeug als Aufgabe, im Baum nicht. | `tools/task`, `cockpit/tree.js`, `desk/objects.py` |
| C2 | Cockpit-Baum: Kopf „Projekt PROJECT“ (Name doppelt, in Großbuchstaben); der Knopf „Baum ausblenden“ überdeckt die Notiz im Kopf „KI GateWay · Anfragen · Schutz“. | `cockpit/tree.js`, `rahmen.js` |
| D1 | **Wissensbasis bei 1024 px:** die Fundstelle hat fest 400 px; die Suche bekommt 390 px, Feld und Knöpfe brechen um. Ohne gewählten Treffer steht die Spalte leer da. | `ui/frame.js` (`nachweis_breite`), Vorgabe |
| D2 | **KI Gateway für KMU bei 1024×700:** das Titelbild nimmt zwei Drittel der Höhe, vom Arbeitsbereich sieht man zwei Zeilen. Kompakt wird der Kopf erst beim Rollen. | `shells/gateway-kmu` |

## 2. Plan

### 2.1 Leiste ordnen (A1, A4)
- **Wichtigkeit statt Reihenfolge allein.** Jede Zelle hat schon `order`. Neu: Passt nicht alles hinein, wandern die Zellen mit dem höchsten `order` in eine letzte Zelle **„+3 ▾“**; ein Klick öffnet die übrigen als Liste (Wert, Hinweis, Klick öffnet den Ort wie die Zelle). Gemessen wird bei Start und bei Größenänderung, gebündelt (500 ms).
- **Nie versteckt, was wartet:** Eine Zelle mit Ton `warn` oder `bad` bleibt immer sichtbar (sie schiebt eine ruhige Zelle in „+n“). Die Zelle „+n“ trägt selbst den schärfsten Ton der Zellen darin.
- Zellen werden **schmaler, nicht abgeschnitten:** Beschriftung oben klein, Wert darunter; der Hinweis (dritte Zeile) fällt unter 1200 px weg und steht im `title`.
- Gilt für das Cockpit (`strip.js`) und den Rahmen (`ui/frame.js`); paperclip zeigt Instrumente als Kacheln und bleibt, wie es ist.
- `gauge-state`: das Bild passt in die Zellenhöhe (A4).

### 2.2 Prüfwerkzeuge nur im Prüfbetrieb (A2)
- Neues Manifestfeld **`zweck: pruefung`** (Vorgabe `betrieb`). Ein Werkzeug mit `zweck: pruefung` wird nur geladen, wenn der Schalter **`entwicklung`** an ist (`local_config/switches.yaml`) oder ein Test es ausdrücklich verlangt.
- `rahmen-probe` bekommt `zweck: pruefung`. Der Test der Stufe C schaltet `entwicklung` im Prüfprojekt ein; `uix_check.py` ebenso (Parameter).
- Im Werkzeug „Module“ steht ein Prüfwerkzeug mit Marke „Prüfung“, damit man sieht, dass es da ist.

### 2.3 Schwebende Knöpfe (A3) – siehe Entscheidung S6-E1
- Shells **mit Leiste** (Cockpit, Rahmen mit `leiste`): Rekorder und Shell-Umschalter werden zwei kleine Knöpfe **rechts in der Leiste** (neben „?“), nichts schwebt mehr über dem Werkstück. Alt+S bleibt.
- Shells **ohne Leiste** (gateway-kmu, fisch, start, Minimal mit eigener Menüleiste): Minimal und gateway-kmu haben eine eigene Kopf-/Menüleiste – dort gehen die Knöpfe hinein (`sedraWechsel.inLeiste(host)`). Wo es keine gibt, bleibt der schwebende Knopf, aber **eingeklappt** zu einem runden „S“ (40 px) und mit `inset`, das den Gesprächsbereich freihält.
- Das Rekorder-Feld zeigt beim Aufnehmen weiter Zeit und roten Punkt – in der Leiste als Zelle mit Ton `bad`.

### 2.3a Mini-Hub (Captain 27.10.2026, 11:02 – ersetzt §2.3)
- Rekorder und Umschalter sind **ein eigenes, schwebendes Fenster** in jeder Shell (außer der Übersicht): Titelzeile „SEDRA · <Shell>“,
  darunter jede Oberfläche als Knopf (die aktuelle markiert, ein Klick wechselt), unten Rekorder und „⋯“ (Übersicht, Darstellung, Schrift,
  Menüseite, Gedächtnis leeren; Alt+S wie bisher).
- **Ziehen** an der Titelzeile, Doppelklick setzt nach unten rechts zurück; **„–“** klappt zu einem runden „S“ (eine laufende Aufnahme
  zeigt einen roten Punkt). Lage und Zustand merkt sich der Browser (`sedra.hub`), begrenzt aufs Fenster.
- Panels öffnen zur freien Seite und sind nie höher als der Platz dort.

### 2.4 Gespräch (B1, B2) – siehe Entscheidung S6-E2
- **„Leeren“ mit Rückfrage im Feld:** erster Klick → der Knopf heißt „Wirklich leeren?“ (rot) für 4 s, zweiter Klick leert; Esc oder Warten bricht ab. Kein `confirm()`. Wie „Gedächtnis leeren“ im Umschalter.
- „Leeren“ rückt nach rechts hinter ein Trennzeichen, weg von „Senden“.
- „Grüne zuerst“ entfällt als Knopf: Die Modellauswahl sortiert **immer** die geprüften schnellen Modelle oben in eine Gruppe „Geprüft schnell ✓“, die übrigen darunter in „Weitere“. Die Ampel neben der Auswahl bleibt.

### 2.5 Stimmigkeit (C1, C2) – siehe Entscheidung S6-E3
- **Eine Definition von „offen“** an einer Stelle (`uix_server._compact_mission`, Felder `offen` und `antrag` in `/api/missions`; das Objekt `task` bleibt, wie es aufgezeichnet ist – Golden-Test): offen ist eine Aufgabe, die läuft oder auf den Captain wartet. **Freigabe-Anträge sind keine Aufgaben** – sie stehen im Posteingang; nach der Entscheidung sind sie dort weg und tauchen auch unter Aufgaben nicht auf. Baum, Werkzeug Aufgaben, Instrument Aufgaben und Arbeitsplatz-Wissen lesen dieses Feld, statt selbst zu zählen.
- Baum: Kopf „Projekt“ mit dem Namen als Notiz in normaler Schrift („Projekt · Prüfprojekt“); der Knopf zum Ausblenden sitzt am Rand des Baums **unter** der Leiste, nicht auf dem ersten Kopf (eigene 24-px-Zeile über dem Baum).

### 2.6 Kleine Bildschirme (D1, D2)
- **Rahmen:** Die Nachweis-Spalte ist höchstens 34 % der Werkstückbreite (mindestens 280 px, höchstens `nachweis_breite`). Unter 1100 px Werkstückbreite wird `seitenleiste` automatisch zu `umschalter` (Reiter „Werkstück · Fundstelle“), ein gewählter Treffer schaltet auf „Fundstelle“ um. Gilt für jede Shell aus Vorgabe.
- **Leere Nachweise klappen ein:** Ein Nachweis-Werkzeug, das nichts zeigt, meldet `leer` (neuer freiwilliger Haken `leer()` bzw. Ereignis); die Spalte wird dann zu einem 32-px-Streifen mit dem Namen senkrecht, ein Klick klappt auf.
- **KI Gateway für KMU:** Der Kopf ist kompakt, sobald das Fenster weniger als 820 px hoch ist oder ein Vorgang offen ist; das Titelbild höchstens 40 % der Höhe. Beim Start ohne Vorgang bleibt der große Kopf (er ist die Visitenkarte).

## 3. Entscheidungen des Captains (27.10.2026, vormittags – alle wie vorgeschlagen)

| Nr | Frage | Entscheidung |
|---|---|---|
| S6-E1 | Wohin mit Rekorder und Shell-Umschalter? **Geändert 27.10.2026, 11:02:** „wieder als eigenes Fenster schwebend in den Shells – dient als Mini-Hub, auch zum Wechseln der Shells“ (§2.3a) | In die Leiste bzw. Kopfleiste der Shell; schwebend nur noch, wo es keine gibt, und dann eingeklappt (§2.3). |
| S6-E2 | „Grüne zuerst“ | Knopf weg, Auswahl immer sortiert mit Gruppe „Geprüft schnell ✓“ (§2.4). |
| S6-E3 | Sind Freigabe-Anträge Aufgaben? | Nein – nur im Posteingang (§2.5). |
| S6-E4 | Prüfwerkzeuge (Rahmen-Probe) | Nur mit Schalter `entwicklung` (§2.2). |
| S6-E5 | Nachweis-Spalte bei schmalem Fenster | automatisch Umschalter unter 1100 px, leer → eingeklappt (§2.6). |

## 4. Abnahme

| ID | Prüfung | Wie |
|---|---|---|
| R1 | Bei 1024 px ist kein Wert einer sichtbaren Zelle abgeschnitten; „+n“ enthält die übrigen; eine Zelle mit `warn` ist nie in „+n“ | Browser-Test Cockpit und Wissensbasis, Node-Test der Verteilung (rein) |
| R2 | Ohne Schalter `entwicklung` lädt `rahmen-probe` nicht; mit Schalter ist der Stufe-C-Test grün | Python-Test Manifest, `test_stufe_c_rahmen` |
| R3 | In keiner Shell liegt ein schwebender Knopf über Werkstück, Nachweis oder Gespräch (Schnitt der Rechtecke = 0) bei 1400 und 1024 px | Browser-Test über alle Shells |
| R4 | „Leeren“: ein Klick leert nicht; zweiter Klick binnen 4 s leert; Esc bricht ab | Schein-DOM-Test talk, Browser |
| R5 | Auswahl: geprüfte Modelle in der Gruppe oben, kein Knopf „Grüne zuerst“ | Schein-DOM-Test talk |
| R6 | Baum, Werkzeug Aufgaben und Instrument zeigen dieselbe Zahl „offen“; ein entschiedener Antrag erscheint nirgends als Aufgabe | Python-Test `objects`, Browser |
| R7 | Wissensbasis bei 1024 px: Suchfeld, Treffer und Knöpfe in einer Zeile; Fundstelle als Reiter; leere Fundstelle eingeklappt | Browser-Test |
| R8 | gateway-kmu bei 1024×700: Arbeitsbereich mindestens 55 % der Höhe | Browser-Test |
| R9 | Bestehende Abnahmen bleiben grün (nur die 4 Altfunde von `main`) | Gesamtlauf, `uix_check` je Shell |

## 5. Reihenfolge im Bau
1. §2.4 Gespräch und §2.5 Stimmigkeit (klein, sofort spürbar).
2. §2.2 Prüfwerkzeuge, dann §2.1 Leiste.
3. §2.3 Knöpfe aus dem Schweben.
4. §2.6 kleine Bildschirme.
