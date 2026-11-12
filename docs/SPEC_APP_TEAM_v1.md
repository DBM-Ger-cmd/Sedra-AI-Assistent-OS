# SPEC App „Team“ (A3, Paperclip als App) – 12.11.2026

Teil der Inventur `docs/INVENTUR_SHELLS_ONE_SEDRA_2026-11-05.md` (Paperclip, Zeile „Dashboard“). Gebaut nach dem Muster der App Translator (`docs/SPEC_APP_TRANSLATOR_v1.md`). Die alte Shell `paperclip` bleibt unverändert, bis der Captain den Gleichstand abnimmt.

## Was gebaut ist

| ID | Anforderung | Stand |
|---|---|---|
| TM-01 | Ein Objekttyp `team` (Ort `team`, Wörter „team“, „paperclip“), ein Platzhalter-Werkzeug `team`; die Shell zeichnet die App über `app.flaeche` – kein zweiter Einhängeweg | gebaut |
| TM-10 | **Überblick**: Posteingang, Issues, Organigramm, Kosten zugleich in einem Raster; jede Zelle ist ein vorhandenes Werkzeug | gebaut |
| TM-11 | Weitere Modi mit je einem Werkzeug: Issues · Vorhaben · Organigramm · Routinen · Kosten | gebaut |
| TM-20 | Ein Modus wird beim ersten Öffnen eingehängt und beim Wechsel nur versteckt; Eingaben bleiben | gebaut |
| TM-21 | Der letzte Modus wird je Browser gemerkt, nie ein Inhalt | gebaut |
| TM-30 | Start-Menü: nur „Team“; Organigramm, Routinen, Vorhaben und Issues stehen nicht mehr einzeln im Menü, bleiben über Chat-Wörter und `open` erreichbar | gebaut |
| TM-40 | Andere Shells: Knöpfe, die die Werkzeuge einzeln öffnen | gebaut |
| TM-50 | Die alte Shell `paperclip` ist unberührt | Test |

## Nicht gebaut

- Agentenfenster-Stapel am rechten Rand (≤ 4, gemerkt, ältestes wird Reiter).
- Firmenwörter (Umbenennen der Orte je Profil), Hinweise auf `agent.changed`, `issue.changed`, `budget.warning`.
- Übergabe wie beim Translator: ein `open` auf `issue`/`agent` geht weiter in einen eigenen Reiter, nicht in den offenen Team-Reiter.
- Nicht im Browser mit echten Daten geprüft; der Test nutzt die leere Entwicklungsumgebung.
