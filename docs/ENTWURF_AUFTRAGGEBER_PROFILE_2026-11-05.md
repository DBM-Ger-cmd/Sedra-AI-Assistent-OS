# Entwurf: Die Harness für spätere Auftraggeber zuschneiden (05.11.2026)

Entscheidung des Captains (05.11.2026): **Sedra XP und der Retro-Desktop werden nicht weiterentwickelt.** Die Harness wird der zentrale Punkt, die Funktionen der anderen Shells wandern in sie. Damit sie sich wie die KMU-Shell für einen Auftraggeber zuschneiden lässt, ohne jedes Mal eine eigene Shell zu bauen, gibt es **Profile**.

## 1. Drei Ebenen, sauber getrennt

| Ebene | Was sie ändert | Wer ändert sie | Stand |
|---|---|---|---|
| **Profil** (Zuschnitt) | was im Start-Menü und in der Taskleiste erscheint, in welcher Gruppe und Reihenfolge, Name und Akzentfarbe | der Captain im Desktop Builder, ohne Gate (eine Wahl, keine Erlaubnis) | **gebaut** (diese Seite) |
| **Richtlinie** (Rechte) | erlaubte Apps (Positivliste), Obergrenze der Berechtigungen, Grundfunktionen nach Rolle | der Betreiber, Datei unter `local_config/`, nur über Gate | Stufe 4 des Apps-Modells (`ENTWURF_APPS_MODELL_2026-11-03.md` §2.2b), noch nicht gebaut |
| **Eigene Shell** | ein grundlegend anderes Aussehen (wie `gateway-kmu` mit Hero-Grafik) | der Entwickler | nur, wenn ein Profil nicht reicht |

Ein Profil **schützt nichts**: wer eine App im Menü ausblendet, nimmt sie nicht weg. Wer sie wirklich sperren will, braucht die Richtlinie. Das sagt die Oberfläche im Desktop Builder ausdrücklich.

## 2. Was ein Profil enthält

`runtime_data/harness/profile/<kennung>.json` (kennung: a–z, 0–9, Bindestrich, 2 bis 40 Zeichen):

```json
{"name": "Muster GmbH", "auftraggeber": "Muster", "beschreibung": "Sachbearbeitung",
 "start":  {"ausblenden": ["wissen"], "zuordnung": {"models": "system"}},
 "zellen": {"ausblenden": ["scheduler"], "reihenfolge": ["state", "model"]},
 "marke":  {"name": "Muster GmbH", "akzent": "#2266aa"}}
```

Die **Wahl**, die gerade gilt, steht in `runtime_data/harness/desktop.json` (dasselbe ohne Name, dazu `profil`: welches Profil gerade gilt). Leer heißt: die Vorgabe der Shell (`start_gruppen.json`, die Zellen der Taskleiste). Die Oberfläche legt die Wahl über die Vorgabe (`desktop.js` → `startmenue.js`, `taskleiste.js`).

## 3. Grundfunktionen bleiben erreichbar

Nach `ENTWURF_APPS_MODELL` §2.2a lassen sich **Posteingang, Aufgaben und die Zelle Freigaben nie ausblenden**, weder in der Oberfläche noch im Server (`desktop_grundfunktion`), auch nicht durch einen importierten Profil-Text. Der Desktop Builder selbst ist ein fester Eintrag der Gruppe System und lässt sich ebenfalls nicht ausblenden (sonst käme man nicht zurück).

## 4. So richtest du einen neuen Auftraggeber ein

1. Start → System → **Desktop Builder**.
2. Reiter **Start-Menü** und **Taskleiste**: Apps und Zellen aus- und einblenden, Gruppen und Reihenfolge wählen, speichern.
3. Reiter **Profile und Marke**: Name und Akzentfarbe, dann „Als Profil speichern“ (Kennung, Name, Auftraggeber).
4. Weitergeben: „Exportieren“ zeigt das Profil als Text; auf der anderen Maschine „Profil aus dem Text importieren“, dann „Anwenden“.
5. Zurück zur Vorgabe: je Reiter „Auf Vorgabe zurücksetzen“.

Der Reiter **Module** zeigt die Landkarte der Oberfläche (jedes Modul mit Selektor und Dateien) und legt ein ganzes Modul mit „Im Chat anpassen“ als Entwurf ins Eingabefeld; derselbe Weg gilt per Rechtsklick auf jede Stelle der Oberfläche (`kontext.js`).

## 5. Nächste Stufen (Vorschlag, nicht gebaut)

- **Logo, Schrift und Startseite** je Profil (heute: Name und Akzentfarbe).
- **Profil beim Start wählen** oder an ein Projekt binden; Profile als Datei aus einem Ordner laden, nicht nur aus dem Text.
- **Rollen und Richtlinie** (Stufe 4): Positivliste der Apps und Obergrenzen mit Gate; das Profil zeigt dann nur, was die Richtlinie erlaubt.
- **Funktionen der anderen Shells** (Cockpit, Translator, Gateway, Paperclip, Wissensbasis, Minimal) als Apps in die Harness holen und über dieselben Profile ein- und ausblenden.
