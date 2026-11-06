---
name: selbstabbild-erweitern
description: Einen weiteren Ablauf von SEDRA als Prozessmodell im Selbstabbild aufnehmen (runtime/config/selbstabbild.yaml) und den Abweichungstest grün halten. Nutzen, wenn ein SEDRA-Ablauf dokumentiert, abgebildet oder ein Prozess aus den Quellen erzeugt werden soll.
---

# Selbstabbild erweitern

Das Selbstabbild zeigt SEDRAs eigene Abläufe in den Prozess-Apps. Es ist reine Darstellung: alle Knoten deaktiviert, Menschen nur als Rolle, nie ausführbar.

## Neuen Ablauf anlegen
1. In `runtime/config/selbstabbild.yaml` unter `ablaeufe` einen Eintrag mit `id`, `name`, `zweck`, `schritte` ergänzen.
2. Je Schritt: `id`, `name` (Verb + Substantiv), `art` (`start`, `task`, `decision`, `end`), `arbeitsweise` (`manual`, `assisted`, `automatable`), `rolle`, `lieferant`, `eingabe`, `ergebnis`, `empfaenger`, `nachweis`, `abschluss`, `quelle`, `weiter`.
3. **Quelle ist Pflicht:** `quelle: {datei: <Pfad im Projekt>, suche: '<Text, der wörtlich in der Datei steht>'}`. Ein Funktionsname (`def laufen(`) eignet sich gut.
4. Genau ein `start`. Eine `decision` hat in `weiter` genau zwei Schritte (Ja, Nein). Ein `end` hat kein `weiter`. Höchstens 32 Schritte.
5. Menschliche Entscheidungen (Captain) als `manual` mit Rolle, nie als technischer Schritt.
6. Flow-Zeilen mit Doppelpunkt oder Fragezeichen im Text maschinell schreiben (`yaml.safe_dump`), nicht von Hand, sonst bricht das YAML.

## Prüfen
- `PYTHONPATH=../src:. python -m unittest test_selbstabbild` im Ordner `runtime/tests`. Der Test `test_quellen_stimmen_mit_dem_stand_ueberein` schlägt fehl, sobald eine Quelle fehlt oder ihr Text nicht mehr in der Datei steht. Dann Quelle oder Abbild anpassen, nie den Test lockern.
- In den Apps: Startseite, "Selbstabbild prüfen", dann "Abläufe von SEDRA anlegen oder aktualisieren". Zweiter Lauf ändert nichts (`unveraendert`), eine geänderte Quelle erzeugt nur eine neue Revision.
- Anlegen verweigert sich bei abweichenden Quellen (`selbstabbild_quellen_abweichend`).

## Entwürfe durch SEDRA
Das Harness-Werkzeug `prozess_beantragen` stellt nur einen Antrag im Posteingang. Der Entwurf (`Entwurf · <Name>`) entsteht erst nach dem Ja des Captains als erste Revision. Aus der App heraus startet "Von SEDRA entwerfen lassen" eine Sitzung mit der Vorlage `prozessmodellierer`.
