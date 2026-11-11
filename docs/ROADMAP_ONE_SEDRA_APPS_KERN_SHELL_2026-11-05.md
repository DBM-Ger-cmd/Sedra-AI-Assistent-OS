# Roadmap One Sedra – Ausbau der App-Idee: Kern, Shells, Apps (Stand 05.11.2026)

Dritter Teil neben `ROADMAP_ONE_SEDRA_RENEW_2026-11-05.md` und `ROADMAP_ONE_SEDRA_UIX_WERKZEUGE_2026-11-05.md`. Grundlage: `ENTWURF_APPS_MODELL_2026-11-03.md`, `KONZEPT_APPS_UND_ERWEITERUNGEN_v1.md` (Bausteine AM0–AM9) und die Entscheidung vom 05.11.: **One Sedra ist die Zentrale.**

## 1. Leitbild (bleibt, Android)

- **Kern:** Laufzeit, Harness, Freigaben, Modell-Routing, Audit-Log, Schutz. Nur der Kern ist `trust: CORE`.
- **Apps:** Pakete mit Manifest (`tool.yaml`), laufen außerhalb des Kerns (heute: iframe mit `sandbox="allow-scripts"` hinter der Nachrichtenbrücke `uix/ui/bruecke.js`).
- **Berechtigungen** in Schutzstufen: A normal, B gefährlich (nur auf Antrag), C nur Kern.
- **Shells** sind Oberflächen auf demselben Kern. Neu: **One Sedra ist die einzige Hauptshell**; die anderen Shells liefern Funktionen als Apps, Zuschnitt läuft über Profile.
- **Grundfunktionen** (Entscheidungen, Gespräch, Aufgaben, Logbuch, Modus und Grenzen, Module und Berechtigungen, Einstellungen, Posteingang, Freigaben) sind in jedem Profil vorhanden, nie ausblendbar, sichtbar nach Rolle.

## 2. Was sich durch One Sedra ändert

| Bisher | Jetzt |
|---|---|
| Shells als gleichwertige Oberflächen (`shells:` im Manifest) | Eine Zentrale; **`shells:` bleibt** (Beschluss 05.11.: wird evtl. für VM/Agenten gebraucht), **`profile:` kommt daneben** (welche Apps in welchem Profil) |
| Apps pro Shell fest verdrahtet (Taskleiste, Orte, Start-Gruppen) | Zellen, Orte und Start-Menü-Gruppen **aus Manifesten**, im Desktop Builder anordenbar |
| KMU-Shell als eigene Shell (Stufe 4) | KMU = **Profil** mit Rollen und Betreiber-Richtlinie |
| Minimal-Stick mit 4 Shells | Stick = **Profil „Stick“** von One Sedra |
| Shell-Funktionen nur dort erreichbar | Cockpit, Translator, Gateway, Paperclip, Wissensbasis als **Apps** in One Sedra |

## 3. Stufen (Bausteine AM0–AM9 in neuer Reihenfolge)

| Stufe | Baustein | Ziel | Ergebnis, an dem man es sieht |
|---|---|---|---|
| **A0 Lücken zu** | AM0 (`SPEC_..._AM0_HAERTUNG.md`, F4–F11) | Vor jedem fremden Code: gleiche CSP der Rahmenseite prüfen, `uix/**` unter die harten Vorbehalte der Harness, Pakete können nie `CORE` werden | Tests rot, wenn ein Modell ein Werkzeug als „Paket“ mit CORE ablegt |
| **A1 Zellen aus Manifesten** | AM1 | Manifest v1.1 (`zelle`, `shells` bleibt, `profile` kommt dazu); Taskleiste und Leiste lesen Manifeste statt fester Listen (`taskleiste.js`) | Neue App erscheint ohne Codeänderung in der Taskleiste |
| **A2 Orte und Grundfunktionen** | AM2 | Orte (Start-Gruppen, Wörter für den Chat) aus Manifesten; Grundfunktionen erklärt und geprüft; **App-Rahmen** einheitlich | Start-Menü-Gruppen kommen aus Manifesten; Test: Grundfunktion nie ausblendbar |
| **A3 Shell-Funktionen als Apps** | (Unterchats U1–U3) | Inventur, dann Translator, Wissensbasis, Cockpit, Paperclip, Gateway als Apps in One Sedra | Je Shell eine App, die alte Shell bleibt bis zum Gleichstand unverändert |
| **A4 Berechtigung** | AM3 | `rechte` im Manifest, Gewährung, Aktivierung, Update mit Diff, Ereignisklassen, Berechtigungsseite | Seite „Module und Berechtigungen“ zeigt je App, was erlaubt ist; Entzug sofort wirksam |
| **A5 Verzeichnis** | AM8 | Ein Verzeichnis aller Erweiterungen (E1–E8), gemeinsame Wirkungsklassen, Auslieferungsprofile | Ein Blick zeigt, was installiert ist und was es darf |
| **A6 Dienste** | AM4 | Dienste außerhalb des Prozesses, MCP-Zugang des Desk mit Berechtigung | Dienst startet/stoppt nur mit Freigabe |
| **A7 Langdock** | AM5, AM6 | Langdock als Modellquelle (Region `eu` fest, durch den Inhaltsschutz), dann Agenten nur ausgehend | Cloud nur über den Schalter, nie still |
| **A8 Unternehmen** | AM7 | Rollen, Betreiber-Richtlinie (Positivliste), Konten-Modell, getrennte Profile je Rolle | KMU-Profil blendet nach Rolle Apps und Rechte ein/aus |
| **A9 Werkstatt/Betrieb** | AM9 | Betrieb läuft aus freigegebenem Stand, Änderungen nur über die Übernahme des Updaters; Stick als Profil | Stick-Paket aus Profil gebaut, Prüfsummen stimmen |

Reihenfolge (Beschluss 05.11.: **gleich mit den Apps anfangen**): A3 mit der ersten App sofort (U1 → U2/U3); A0 und A1 laufen daneben als eigener Unterchat und werden vor der ersten *fremden* App fertig. Danach A2 → A3 weiter (laufend, je App) → A4 → A5 → A6 → A7 → A8; A9 nach A2 und A4 (Stick früher möglich, wenn nur lokale Apps).
Begründung: A0 ist Voraussetzung für alles mit fremdem Code; A1/A2 bringen sichtbaren Nutzen ohne neue Rechte; A4 ist die Mitte; A8 ist der größte Schritt.

## 4. App-Rahmen (neu, kleiner Baustein in A2)

Jede App in One Sedra bekommt denselben Rahmen: Titel, App-Menü, Rechtsklick-Modul („Im Chat anpassen“), Zustand speichern/laden, Fehleranzeige, Verweis auf die Berechtigung. Eine App liefert nur Inhalt und Manifest, der Rahmen kommt vom Kern. So bleiben Aussehen, Freigaben und Rechtsklick einheitlich, und der Desktop Builder kann jede App anordnen.

## 5. Manifest-Skizze (v1.1 mit Profilen)

```yaml
id: translator
name: Übersetzer
kind: app            # app | instrument | dienst
trust: PACKAGE       # CORE nur Kern
gruppe: werkzeuge                    # Platz im Start-Menue (besteht)
zelle: {feld: ram, label: "RAM frei", ort: hardware}   # Taskleisten-Zelle eines Instruments (Vertrag 1.1, AM1)
shells: [harness]                 # bleibt
profile: [standard, kmu, stick]   # neu, daneben
rechte: [datei_lesen, modell_nutzen]   # Stufe A; B nur auf Antrag
woerter: [übersetze, translate]
abhaengig_von: []
update: {weg: diff}
```

## 6. Zuordnung zu Unterchats

| Unterchat | Stufe |
|---|---|
| U1 Shell-Inventur | A3 Vorbereitung |
| U2 App Translator, U3 App Wissensbasis | A3 |
| neu **U12 Härtung AM0 + Manifest v1.1 (A0, A1)** | A0, A1 – `uix/ui/`, `tool.yaml`-Prüfung, `taskleiste.js`, Tests; läuft **nach** dem Start von U2/U3, nicht davor |
| neu **U13 App-Rahmen und Orte (A2)** | A2 – `uix/shells/harness/`, `start_gruppen`, `places` |
| U5/U6 Freigaben S4, Rechte | A4, A8 |
| U8 Stick aus Profil | A9 |

U12 und U13 berühren teils dieselben Dateien (`taskleiste.js`, Start-Menü): nacheinander starten, nicht gleichzeitig.

## 7. Entscheidungen des Captains (05.11.2026)

1. **`shells:` bleibt.** Nicht durch `profile:` ersetzen; die Shell-Zuordnung wird eventuell für VM/Agenten gebraucht. `profile:` kommt als zweites Feld dazu.
2. **Gleich mit den Apps anfangen** (U1 Inventur, dann U2 Translator / U3 Wissensbasis). Härtung und Manifest (U12) laufen daneben.
3. **Fremde Apps:** noch nicht entschieden. Bis dahin gilt als Voreinstellung: nur eigene Pakete, keine Dritten, bis A0 und A4 stehen.
