# Befund: test_k5 (Cockpit-Baum) unter Last (29.10.2026)

Auftrag (Vorarbeiter-Sitzung): Ursache von `test_k5` finden, Testproblem im Test beheben, Cockpit-Defekt nur melden.
Branch `harness/k5` (von `spec/agenten-orchestrierung`, d9b8f97). Keine Dateien geändert, nichts gepusht, kein Modell geladen.

## Ergebnis

- Die Ursache liegt **nicht im Cockpit-Baum und nicht im Sichtbarkeitscheck des Tests**. Sie liegt in der Erreichbarkeit des
  lokalen UIX-Servers unter Parallellast.
- Reproduktion: acht parallele Prozesse von `test_uix_cockpit_baum` (Chromium je Prozess). In ein bis zwei von acht Läufen
  fallen `test_k5` oder `test_k8` aus. Allein und in den Gruppenläufen (drei vollständige Läufe) bleibt alles grün.
- Beleg aus dem fehlgeschlagenen Lauf (Konsole der Seite): die Skripte `/uix/ui/dom.js`, `sprache.js`, `places.js`, `vorgabe.js`,
  `lifecycle.js`, `stand.js` kommen mit `net::ERR_CONNECTION_REFUSED` nicht an. Folge: `registerTool`, `PLACES`, `registerShell`
  sind undefiniert, die Shell startet nicht (`sedraBoot.ctx` fehlt, kein `.ck-tree`, Wurzel leer). Der Test wartet dann vergeblich.
- Wahrscheinliche Ursache: `uix_server.make_server` nutzt `ThreadingHTTPServer` mit dem Standard-Backlog von 5
  (`request_queue_size`). Eine Seite lädt viele Skripte gleichzeitig; bei acht Browsern gleichzeitig läuft der Backlog über,
  Windows lehnt die Verbindung ab.

## Einordnung

- Das ist kein Defekt im Cockpit-Code (`uix/shells/cockpit/`), dort wurde nichts geändert.
- Der Server liegt in `src/guppi_runtime/uix_server.py`, die Testhilfe in `benchmarks/uix_check.py`. Beide sind außerhalb der
  erlaubten Schreibbereiche (`runtime/tests/`, `docs/`) dieses Auftrags.
- Ein echter Nutzer am PC öffnet die Seite einzeln. Ob das Backlog von 5 auch dort reicht, ist offen; es ist eine kleine
  Produktfrage, kein Test-Artefakt.

## Vorschlag (zur Entscheidung)

1. Bevorzugt: in `uix_server.make_server` `ThreadingHTTPServer.request_queue_size` auf z. B. 64 setzen. Eine Zeile, betrifft
   die Produktion (Freigabe nötig: Schreibbereich `src/`).
2. Alternativ nur für Tests: in `benchmarks/uix_check.py` (`start_server`) dieselbe Einstellung vor dem Start, dann bleibt
   `src/` unberührt (Freigabe nötig: `benchmarks/`).
3. Ergänzend: `Basis.seite()` wartet nach dem Neuladen fest 1,2 s und `wait_until_started` schluckt Timeouts. Ein Test, der
   den Startzustand prüft (z. B. `sedraBoot.ctx` plus `.ck-tree`), würde den Fehler klarer melden.

Nach Freigabe von 1 oder 2 wird `test_k5` und `test_k8` unter Last erneut mit acht Prozessen geprüft.

## Nebenbefund (nicht Teil dieses Auftrags)

- `test_uix_shell_start` erwartet die alte Shell-Liste (ohne `harness` und `wissensbasis`); 2 Tests rot seit der Übernahme
  von Stufe 1/2 ins `spec`. Eigener Punkt.
- Bekannt rot: `test_uix_flows.Build24` (in `known_red.txt`).

## Verworfen

- Längere Wartezeit im Test: würde nur verdecken, dass die Shell nicht startet.
- Veränderung am Baum oder am Fokus-Code: der Fokus-Test ist allein grün, die Baumlogik ist nicht die Ursache.
