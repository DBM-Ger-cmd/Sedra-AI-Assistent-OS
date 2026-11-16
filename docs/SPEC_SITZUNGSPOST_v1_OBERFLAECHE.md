# Sitzungspost – Vorlage für die Oberfläche (Stufe 3) – 16.11.2026

Zu `docs/SPEC_SITZUNGSPOST_v1.md` (SP-07, SP-17, SP-18). Dies ist die Vorlage für einen Auftrag des UIX-Koordinators. Gebaut wird in `uix/shells/harness` **nur** auf dessen Auftrag; die Sitzung Sitzungspost fasst `uix/` nicht an. Stand der API: Branch `claude/optimistic-murdock-04aae8`, Commit `6904507`.

## 1. Schnittstelle (fertig, nur nutzen)

| Was | Form |
|---|---|
| Post senden | `POST /api/harness/sitzungen/<ziel>/post` mit `{text, via?, antworten?}` → `{post_id, sitzung_id, antwort?}`. `text` 1 bis 4000 Zeichen. `via` = ID der Sitzung, aus der der Captain weiterleitet. `antworten: true` startet danach den Zug der Zielsitzung (`antwort` enthält dann das Ergebnis von `nachricht`, auch `{status: 'kein_modell', …}`). Der Absender ist immer der Captain (der Server setzt ihn). |
| Fehler | HTTP 400, Text beginnt mit dem Code: `text_required`, `selbst_nicht` (nur Werkzeugweg), `projekt_fremd` (nur Werkzeugweg), `post_bremse` (zu viel ungelesene Post im Ziel), `post_aus` (Schalter `sitzungspost: aus`); 404 `sitzung_unbekannt`. |
| Liste | `GET /api/harness/sitzungen` → jede Zeile hat `post_ungelesen` (Zahl, 0 wenn keine). |
| Verlauf | `GET /api/harness/sitzungen/<id>` → `eintraege`: `{typ: 'post', post_id: 'P-XXXXXXXX', von: 'captain' \| 'sitzung:S-…', von_titel?, via?, text, zeit, hops}`. Ein Eintrag `typ: 'captain'` trägt `post_ids: [P-…]`, wenn er die Post im Zug gelesen hat. Eine Post ist **ungelesen**, solange ihre `post_id` in keinem `post_ids` steht. |
| Ereignis | `harness.sitzung` mit `{id, was: 'post'}` – der Name und das Pflichtfeld `id` passen zu `ui/bus.js`; die Shell lädt die Liste bei jedem `harness.sitzung` neu (`shell.js`), der Zähler aktualisiert sich damit von selbst. Geprüft: das Feld `was` ist zusätzlich erlaubt (nur `id` ist Pflicht). |
| Post aus dem Modell | Werkzeug `sitzung_nachricht` (Karte, Klasse N): erscheint wie jede Karte im Posteingang; die Oberfläche braucht dafür nichts Neues. |

## 2. Anforderungen Oberfläche

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| SP-U1 | Rechtsklick im Chat-Fenster (Modul in `kontext.js`) und im Menü einer Sitzung in der Seitenleiste: Eintrag „Nachricht an Sitzung …“ / „Message to session …“. | Sichtprüfung |
| SP-U2 | Der Eintrag öffnet einen Dialog (siehe §3). Esc und „Abbrechen“ schließen ihn ohne Senden; Fokus geht danach zurück. | Sichtprüfung, Tastatur |
| SP-U3 | Senden ruft den Weg aus §1 und zeigt den Fehlercode als lesbaren Text (nicht den Rohcode allein); bei Erfolg Hinweis „Post abgelegt“ (nicht modal). Mit „und antworten lassen“ und `kein_modell` im Ergebnis: „Post abgelegt, Modell fehlt – sie wird beim nächsten Zug gelesen.“ | Sichtprüfung mit Attrappe |
| SP-U4 | Verlauf: ein Eintrag `typ: post` erscheint als eigene Zeile, nie als Captain- oder SEDRA-Eintrag: Kopf „Von Sitzung ‹von_titel›“ bzw. „Vom Captain (aus ‹Titel von via›)“, Zeit, Text ab etwa 6 Zeilen eingeklappt. Solange die Post in keinem `post_ids` steht, trägt die Zeile „wird beim nächsten Zug gelesen“. Der Text wird als Text eingesetzt (kein HTML). | Sichtprüfung, Test mit `<b>`-Text |
| SP-U5 | Seitenleiste: je Sitzung ein Zähler „Post“ aus `post_ungelesen` (versteckt bei 0, `aria-label` „3 ungelesene Nachrichten von Sitzungen“). Er gehört **in die Zustandsanzeige je Sitzung** (`docs/SPEC_SEITENLEISTE_ZUSTAND_v1_ENTWURF.md`, Pi), keine Sonderzeile; Anforderung dorthin übernehmen. | Sichtprüfung, Spec-Abgleich |
| SP-U6 | Alle Texte DE/EN in den Textdateien, Farben und Abstände nur als Tokens, keine Datei über 400 Zeilen, nichts aus dem Netz. | Test der Textdateien, Vertragsprüfung |
| SP-U7 | Ohne `post_ungelesen` in der Antwort (älterer Server) oder mit `sitzungspost: aus` zeigt die Oberfläche nichts Neues und keinen Fehler. | Test mit Attrappe ohne Feld |

## 3. Dialog „Nachricht an Sitzung“ (Vorlage A)

```
┌ Nachricht an Sitzung ──────────────────────────── [×] ┐
│ An        [ Sitzung wählen ▾ ]   (Projekt: ‹Name›)     │
│ Nachricht [ …markierter Text oder letzte Antwort… ]    │
│           [                                       ]    │
│           0 / 4000                                      │
│ [ ] und antworten lassen                                │
│ Hinweis: Die Post ist Text zum Lesen für die andere     │
│ Sitzung, keine Anweisung des Captains.                  │
│                         [ Abbrechen ]  [ Senden ]       │
└─────────────────────────────────────────────────────────┘
```

- **Ziele:** `GET sitzungen` des Projekts; die eigene Sitzung (falls aus ihr geöffnet) fehlt in der Liste; sortiert wie die Seitenleiste; Titel „Ohne Titel“ als Beschriftung, dazu die ID klein. Laufende Sitzungen bleiben wählbar (Post startet keinen Zug).
- **Vorbelegung:** markierter Text im Chat, sonst leer. Wird aus einer Sitzung geöffnet, geht deren ID als `via` mit.
- **Senden** gesperrt bei leerem Ziel, leerem oder zu langem Text; Zähler der Zeichen zählt rückwärts ab 4000.
- **„Und antworten lassen“** standardmäßig aus; wenn an, steht daneben „startet einen Zug in der Zielsitzung (braucht ein geladenes Modell)“.
- Standard-Fokus: Zielwahl; Strg+Enter sendet.
- Texte (DE / EN), Vorschlag: „Nachricht an Sitzung“ / „Message to session“; „An“ / „To“; „Nachricht“ / „Message“; „und antworten lassen“ / „and let it answer“; „Senden“ / „Send“; „Abbrechen“ / „Cancel“; „Post abgelegt“ / „Message stored“; Fehler `post_bremse` → „Die Zielsitzung hat zu viel ungelesene Post.“ / „The target session has too much unread mail.“; `post_aus` → „Sitzungspost ist ausgeschaltet.“ / „Session mail is switched off.“; `text_required` → „Text fehlt oder ist zu lang.“ / „Text missing or too long.“

## 4. Was die Sitzung Sitzungspost nicht tut

- Keine Änderung in `uix/` aus diesem Branch in die Worktrees des UIX-Koordinators; das Ergebnis kommt als Auftrag und Merge über den Captain.
- `kontext.js` und `verlauf.js` werden erst auf den Auftrag des UIX-Koordinators angefasst (Vorab-Meldung bei `verlauf.js`, wegen des Startbild-Problems).
