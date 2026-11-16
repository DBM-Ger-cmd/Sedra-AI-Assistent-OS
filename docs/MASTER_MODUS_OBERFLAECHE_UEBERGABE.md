# Master-Modus: Übergabe an den UIX-Koordinator (A6, 16.11.2026)

Bezug: `docs/SPEC_MASTER_MODUS_v1_ENTWURF.md` §5. Die Harness ist fertig (Wege, Audit, Ereignis); **die Shell ist nicht angefasst.** Dieses Blatt sagt, was die Oberfläche bekommt und tun muss.

## Wege (Basis `/api/harness`)

| Weg | Wirkung |
|---|---|
| `GET sitzungen/<id>/master` | `{sitzung_id, aktiv, seit, bis, aufrufe, gesperrt, projekt, muster, moeglich, sperrliste}`. `moeglich` = das Projekt hat das Feld `master`; `sperrliste` = ein Satz Klartext für die Anzeige vor dem Einschalten. |
| `POST sitzungen/<id>/master` `{an: true}` | **Einschalten, Klasse H.** Läuft hinter der Tür: der Server antwortet mit einem Fehler `wartet_auf_bestaetigung … Kennung B-…` (Ja im Fenster von SEDRA oder `FREIGABE.bat freigeben <Kennung>`). Erst danach ist der Master an: die Oberfläche fragt `GET …/master` ab oder hört auf das Ereignis. Fehler `master_nicht_moeglich` bei einem Projekt ohne Feld `master`. |
| `POST sitzungen/<id>/master` `{an: false}` | **Ausschalten, Klasse N**, sofort, ohne Tür. Antwort wie `GET`, dazu `war_an` und `gestoppte_laeufe`. Ein laufender `befehl` und Läufe unter dem Master enden. |

Ereignis: `harness.master` `{sitzung_id, aktiv}` (wie `harness.aufgabe`).

## Anzeige, die die Spec verlangt

- **Schild** (`eingabe.js`, heute „⛨ Captain gibt frei · Katalog n Regeln“): bei aktivem Master dauerhaft **„⛨ MASTER · <Projekt> · <aufrufe> Aufrufe“** in Warnfarbe, nicht wegklappbar, mit **Aus-Knopf** direkt daran (ein Klick, keine Rückfrage). `bis` als „noch n h“ im Tooltip.
- **Taskleiste:** Eintrag „Master an · <Sitzung>“, Klick = Aus.
- **Einschalten:** Knopf im Schild-Menü, nur wenn `moeglich`; vorher Projekt, `muster` und `sperrliste` im Klartext zeigen; danach auf die Bestätigung außerhalb des Browsers hinweisen.
- **Karte bei Sperre:** der Grund steht schon im Feld `begruendung` der Karte („Master-Modus deckt nicht: Netz (curl) …“); nur anzeigen.
- **Verlauf:** Werkzeugaufrufe unter dem Master haben im Ereignis `werkzeug.ende` `stufe: 'master'` und `regel: 'master:<sitzung>'`; mit einem Zeichen „master“ kennzeichnen.
- Texte in `strings_de*.js` und `strings_en*.js`.

## Offen mit dem UIX-Koordinator

Platz des Knopfs, Farbe/Token der Warnanzeige, ob die Taskleiste den Eintrag zeigt, ob das Schild-Menü die Sperrliste einklappbar zeigt.

## Grenzen, die die Oberfläche kennen muss

- Der Schalter gilt nur für die eine Sitzung und endet mit ihr, nach 24 Stunden und mit dem Neustart des Servers; die Oberfläche darf ihn nie „merken“ oder beim Start wieder einschalten.
- Löschbefehle, ungesehener Code (G4), Code der Oberfläche und alle festen Vorbehalte bleiben Karte (O-1, O-2 der Spec).
