# Entwurf Prototyp Experten-Bau (eine Seite, 12.11.2026)

Zum Konzept `docs/KONZEPT_EXPERTEN_SCHLEIFEN_2026-11-12.md`. Nichts gebaut, zur Durchsicht des Captains. Ziel: prüfen, ob die Vorschläge der Experten den Bau von `dashboard_index` verbessern, mit möglichst wenig neuem Code und ohne Eingriff in `devvm_build.py`.

## Was schon da ist und genutzt wird

| Baustein | Quelle | Nutzung |
|---|---|---|
| Stufenweiser Bau mit Fortsetzung | `devvm_build.py --only <Stufe> --seed <Ordner>` | je Runde eine Stufe, Start auf dem gesicherten Stand der Vorrunde |
| Sicherung je Stufe | `devvm_snapshots/<spec>/<Zeit>/after_<Stufe>` | Stand der Runde, Regression, Rückfall |
| Notizen im Arbeitsbereich | `NOTES` der Spec, als `NOTES.md` abgelegt | hier kommen die gewählten Expertenpunkte hinein |
| Experten-Abfrage, Messung | `benchmarks/experten_runde.py` (Fragen, Überlappung, Ausführbarkeit) | Vorlauf jeder Runde |
| Versteckte Tests, Stempel | `spec_check.py --vm` | nur Bewertung und Rückmeldung wie bisher |

## Ablauf Version 0 (Experten-Vorlauf, sonst unverändert)

Neues Skript `benchmarks/experten_bau.py`, rund 150 Zeilen, ein Aufruf je Arm.

```
für Runde in [scan, index, dashboard]:
  1. Server Power-Modus (1 Kanal, 25 Lagen, MTP) startet            (experten_runde.py)
  2. vier Experten mit Fallenliste -> je 5 Punkte mit Befehl          (Vorschläge in <ausgabe>/runde_n/)
  3. Auswahl durch das Modell mit festen Kriterien -> höchstens 8 Punkte
     (deckt den Vertrag der Stufe? ein Befehl, der auf Windows und Linux läuft? widerspruchsfrei?)
  4. abgeleitete Spec dashboard_index_exp_<n>: gleiche Stufen und Tests,
     NOTES um den Abschnitt "Vorgaben aus der Expertenrunde" ergänzt; Stempel mit spec_check --vm
  5. Server beenden; devvm_build --only <Runde> --seed <Stand der Vorrunde> --profile standard
  6. Sicherung der Runde; versteckte Tests der Runde UND aller früheren auf VM und Host
  7. Besteht die Runde nicht: nicht weiterbauen, melden (Regel von sedra-bau-starten)
```

Verglichen wird mit Arm A (heute: ein `devvm_build` über alle Stufen, 3.828 s, Stufen 2/3, Endstand kaputt).

## Was Version 0 noch nicht kann (Version 1, nur nach dem Ergebnis)

- **Läufer als Werkzeug:** die Befehle der Experten und die Vertragsbeispiele werden nach jedem Bau auf Host und VM ausgeführt, Fehler mit Ort gehen als Nacharbeit an den Coder. Der Coder selbst bekommt weiter kein Laufwerkzeug.
- **Prüfer A und B:** Befunde nach der Fehlerliste, das zweite Modell (LFM3 nur ohne Denken, mechanische Checks).
- **Architekt-Runde 0:** Gerüst und Vertrag vor Stufe 1.

## Messplan Version 0

| Frage | Kennzahl |
|---|---|
| Helfen die Expertenpunkte überhaupt? | bestandene Stufen am Ende, Endstand gegen alle Stufentests auf VM und Host |
| Kostet es viel? | Zeit je Runde, Modellaufrufe, Nacharbeiten gegenüber Arm A |
| Kommen die Fallen im Code an? | Durchsicht mit `REVIEW_VORLAGE.md` (Dateiknoten, Neuschreiben, Pfadtrenner) |
| Streuung | Wiederholung: Arm B2 und Arm B3 mit anderem Seed der Vorschläge |

Aufwand je Lauf rund eine Stunde (wie Arm A) plus drei Vorläufe von je etwa 40 s. Zwei Läufe von Arm B bedeuten etwa zwei Stunden GPU. Mit einem Lauf je Arm ist das Ergebnis ein Hinweis, kein Beleg.

## Risiken

- Ein Lauf je Arm ist statistisch dünn; der Bau von heute hatte schon starke Streuung zwischen Nacharbeiten.
- Die gewählten Punkte können den Coder verwirren, wenn sie viel verlangen (kleine Fenster, 32k). Darum höchstens 8 Punkte, Fenster wie in Arm A.
- Das abgeleitete Spec braucht je Runde einen Stempel (etwa 1,5 min je Runde).

## Entscheidungen des Captains

1. Version 0 bauen (Experten-Vorlauf zuerst, Läufer später)? Empfehlung ja, weil es die Wirkung der Expertenpunkte allein misst.
2. Ein oder zwei Läufe von Arm B?
3. Das Hauptmodell im Wechsel: Server für die Experten und Server für den Bau sind verschieden (Power-Modus gegen Bau-Profil `standard`, 32k Fenster); der Wechsel kostet je Runde etwa eine Minute Ladezeit. Akzeptiert?
