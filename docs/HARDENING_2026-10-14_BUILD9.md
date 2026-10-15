# Härtungsrunde 2026-10-14 (abends, auf Build 9)

Gezielt auf die Fläche, die mit Build 7–9 dazugekommen ist: die Andockstelle `desk/` (Gateway, Grenzen, Vorhaben,
Installation) und die neuen Routen des Vermittlers. Die erste Härtungsrunde (`HARDENING_2026-10-14.md`) bleibt gültig; was
dort geprüft wurde, ist hier nicht noch einmal aufgeführt.

**Der Kern wurde nicht angefasst.** Alle Änderungen liegen in `desk/` und `uix_server.py`, alle alten Routen bleiben.

## 1. Was geprüft wurde und in Ordnung ist

| Bereich | Befund |
|---|---|
| Unsichere Muster (`shell=True`, `pickle`, `yaml.load`, `os.system`) im ganzen Paket | keine. Die vier Treffer für `exec(` sind die Testläufer in der microVM und den Benchmark-Specs – so gewollt. `compileall` fehlerfrei. |
| YAML im Desk (`uix.yaml`, `boundaries.yaml`, `intents.yaml`, Manifeste) | durchgehend `yaml.safe_load`, Schreiben über Temp-Datei + `replace`. |
| Markup in der neuen Oberfläche (`uix/ui`, `shells`, `tools`) | **kein** `innerHTML`, `insertAdjacentHTML`, `document.write`, `new Function`, `eval` – alles geht über `textContent`/`el()`. Die Durchsicht beim Einbau prüft genau darauf. |
| Token des Vermittlers | Vergleich mit `hmac.compare_digest`, Zugriffe werden nicht protokolliert (`log_message` stumm), Token im Fragment bzw. – nur für `EventSource` – als Query auf Loopback. |
| Allowlist je Modul | ein fremdes Modul bekommt als `COMMUNITY` nur Leserouten; `uix_check` prüft mit 15 echten 403-Proben, dass die Sperre greift. |
| Freigabeweg der Grenzen und des Einbaus | derselbe Einmal-Token und dieselbe Inhaltsbindung (`request_binding`) wie bei den Schaltern; `install_apply` prüft jede Datei gegen den Hash aus dem Gate. |

## 2. Was geändert wurde

| Nr. | Härtung | Datei | Test |
|---|---|---|---|
| **H7** | **Keine Verknüpfung kommt beim Einbau mit.** Eine Datei-Verknüpfung in einem fremden Modul (`beute.js` → `~/.ssh/id_rsa`) wurde bisher gelesen, gehasht und beim Anwenden als echte Datei kopiert – das Gateway hätte sie danach ausgeliefert, weil der Name auf `.js` endet. Jetzt weist `read_module` jede Verknüpfung ab (`symlink_refused`), auch die auf einen **Ordner**: `rglob` steigt in einen verknüpften Ordner gar nicht hinab, die Dateien hätten also stumm im Gate gefehlt. | `desk/install.py` | `test_a_link_out_of_the_module_is_refused_not_followed`, `…_linked_folder_…` |
| **H8** | **Das Gateway liefert keine Verknüpfung aus** – zweite Sperre für Ordner, die von Hand entstehen, nicht über das Gate. Geprüft wird die Datei *und* ihr Ordner, und dass der aufgelöste Pfad im Modul bleibt. | `desk/gateway.py` | Probe (unten) |
| **H9** | **Ein Blockkommentar versteckt keinen Fund mehr.** `*/ eval(x)` beginnt mit einem Stern und war damit für die Durchsicht ein Kommentar – es ist aber Code. Dasselbe galt für `#feld = eval(x)` (privates Feld in JS). Neu: `is_comment()` überspringt eine Fortsetzungszeile nur, solange der Block auf ihr nicht endet, und `#` gilt nicht mehr als Kommentar. Nach `//` wird weiterhin **nicht** abgeschnitten – in `'https://…'` steckt der Fund selbst. | `desk/install.py` | `test_a_block_comment_does_not_hide_a_finding`, `test_a_url_survives_the_comment_rule` |
| **H10** | **Geprüft ist, was jetzt dort steht.** Der Einbau kopiert erst in einen Ordner `*.im-bau` daneben, hasht **nach** dem Kopieren noch einmal und rückt ihn dann an seinen Platz. Vorher konnte zwischen Prüfung und Kopie eine Datei wechseln, und ein Abbruch mitten im Kopieren ließ ein halbes Modul liegen, das beim nächsten Öffnen geladen worden wäre. | `uix_server.py` | `test_what_is_copied_is_hashed_again` |
| **H11** | **Eine Einmal-Erlaubnis verfällt** nach zehn Minuten (`ONCE_SECONDS`), mit Audit `BOUNDARY_ONCE_EXPIRED`. Vorher lag ein nicht verbrauchtes „einmal“ bis zum Neustart bereit – ein „ja“ von heute früh hätte am Abend für eine Handlung gegolten, an die beim Zustimmen niemand mehr dachte. | `uix_server.py` | `test_an_unused_once_permission_expires` |
| **H12** | **Dieselbe Handlung ist eine Entscheidung, nicht zehn.** Eine Überschreitung mit derselben Grenze und demselben Satz liefert die bereits offene Entscheidung zurück (`again: true`); mehr als `MAX_OPEN_CROSSINGS` (50) offene Grenzfragen werden abgelehnt. Vorher konnte ein Werkzeug in einer Schleife die Liste des Captains und den Speicher füllen. | `uix_server.py` | `test_the_same_action_asks_once_not_ten_times` |
| **H13** | **Die Datei der Vorhaben wächst nicht unbegrenzt** (`MAX_INTENTS` 500) – Anlegen braucht keine Freigabe, also braucht es eine Grenze. | `desk/intents.py` | `test_the_file_of_vorhaben_does_not_grow_without_end` |
| **H14** | `install_remove` räumt keinen verknüpften Ordner aus, sondern weist ihn ab (`module_folder_is_a_symlink`). | `uix_server.py` | — (eine Zeile, über H7/H8 mit abgedeckt) |

Dynamisch geprüft (laufender Hub): eine echte Datei im Modulordner wird ausgeliefert, die Verknüpfung daneben nicht, und
`../../uix.yaml` ebenfalls nicht. `uix_check.py` 26/26, volle Suite grün (siehe unten).

## 3. Bewusst nicht geändert, aber notiert

- **Der Einbau liest einen beliebigen absoluten Ordner.** Das ist gewollt – der Captain zeigt auf den Ordner. Durch H7 und
  die Typ-/Größengrenzen (`.js .css .yaml .json .md .svg .png .html`, 60 Dateien, 2 MB) bleibt die Durchsicht auf diesen
  Ordner beschränkt.
- **`_most_expensive_task()` liest bei jedem Blick alle Missionen.** Bei vielen Aufgaben wird jede Grenzfrage spürbar
  langsamer; ein Zwischenspeicher gehört zum selben Thema wie der Zwischenspeicher für `live.py`.
- **Die offenen Grenzfragen liegen im Arbeitsspeicher.** Ein Neustart des Vermittlers lässt sie verfallen – das ist die
  sichere Richtung (nichts gilt weiter), aber der Captain sieht nach einem Neustart nicht mehr, was gefragt war.
- **`boundaries.yaml` und `intents.yaml` werden ohne `fsync` geschrieben** (Temp + `replace`) – wie `buildflow_store`;
  dieselbe Notiz wie in der ersten Runde.
- **Netz und Löschen kreuzt weiterhin kein Verb der Oberfläche.** Die Prüfung steht, aber wer sie für wirksam hält, irrt –
  deshalb steht es auch in `BUILD_9_GRENZEN_2026-10-14.md`.
