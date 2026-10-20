# 04 – Offenes und Entscheidungen

| Punkt | Stand | Wer entscheidet |
|---|---|---|
| Präsentations-Shell (Folien, Timer, Präsentationsmodus, Sprechernotizen, Demo-Bereich) | nicht gebaut. Vorlagen (V4a/V4b-Texte, Dashboard-HTML) liegen nicht im Archiv. | Captain |
| Weitere Folienbilder in der Oberfläche | nur in `assets/`; Rechte laut Klaus geklärt | Captain (Einsatzort) |
| Demo-Adresse der SEDRA-Umgebung | nicht eingetragen; die Shell startet keinen Server und prüft keine Adresse | Captain |
| Echte Demo-Screenshots | keine vorhanden | Team |
| Folienschrift | nicht eingebettet; Lizenz ungeklärt | Captain |
| Cloud | historische B6-Simulation, kein Nachweis realer Cloud-Verarbeitung | Captain |
| Shell-Umschalter-Name | „KI Gateway für KMU“ im Umschalter | Captain |
| Gemeinsame Änderungen (Tokens, Abnahme-Profil, Test-Liste) | nicht committet; Patch liegt bei | Hauptsitzung |
| Menü des KI GateWay | in der Hauptsitzung in Arbeit (uncommitted); diese Shell fasst es nicht an | Hauptsitzung |
| Baum-Test `test_the_tree_shows_every_zone_and_marks_what_waits` | rot, wegen uncommitteter `tree.js` | Hauptsitzung |
| `start_sedra.sh` mit CRLF statt LF | bestand schon vorher; Test `test_uix_start` meldet das | Hauptsitzung / Captain |
| Schutz-Werkzeug: Routen `/api/guard/group` und `/api/guard/demo` | im Server nicht registriert; die Aufrufe im Werkzeug laufen ins Leere | Hauptsitzung |

**Vor einer Veröffentlichung** (öffentliches Repository): die Lizenzaussage zu den Folienbildern schriftlich festhalten,
den Patch auf dem Zielstand prüfen und die Tests laut `03_EINBINDUNG.md` ausführen.
