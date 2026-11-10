---
name: sedra-messlauf
description: Modellserver-Einstellungen von SEDRA messen (Lagen im RAM n_cpu_moe, Kanäle, Kontext, MTP, KV-Typ, Threads) mit eigenem llama-server, Tempo und VRAM je Stufe, und die Ergebnisse in Rezepte und Profile übertragen. Nutzen, wenn der Captain Einstellungen vergleichen, Profile anlegen, ein neues Modell oder eine neue Hardware abstimmen oder "messen" sagt.
---

# Messlauf Modellserver

Ziel: Zahlen statt Vermutung, bevor ein Rezept (`local_config/role_routing.yaml`) oder ein Profil (`local_config/routing_profiles.yaml`) geändert wird. Das Werkzeug ist `runtime/benchmarks/messlauf.py` (Aufruf und Format der Stufendatei stehen in seinem Kopf).

## Vor dem Lauf (nur lesen, sonst Skill `sedra-schnellpruefung`)
1. GPU frei: höchstens 3,5 GiB belegt, kein `llama-server` (`nvidia-smi`, `tasklist`). Ein fremder Server gehört einer anderen Sitzung oder dem Router: **nie beenden ohne Ja des Captains**. Der Messlauf verweigert den Start bei belegter GPU und bricht eine Stufe als "gestört" ab, wenn mitten drin ein fremder Server auftaucht (sonst sind die Werte falsch; so entstand 10.11. ein wertloser Lauf).
2. Der Lauf dauert 1 bis 3 Minuten je Stufe (Modell laden, Aufwärmlauf, 3 Runden). Im Hintergrund starten (Monitor, `until`-Schleife auf "GPU frei", dann Lauf), nicht abfragen.
3. Wartet die GPU auf einen anderen Lauf, Wächter setzen statt zu raten; Ergebnisse stufenweise melden.

## Stufendatei schreiben
- Nur **eine Größe pro Messreihe** ändern (Lagen, Kanäle, MTP oder KV-Typ), alles andere gleich halten, sonst ist der Vergleich wertlos.
- Immer die Referenzstufe mitmessen (heutige Einstellung), im selben Lauf.
- Rezeptwerte übernehmen: `-fa on`, KV q8_0, `-ub 512`, `--jinja`, `--reasoning off`; Threads `--threads 12 --threads-batch 20` (Threads sind bei MoE-Modellen mit Experten im RAM egal, der Hebel ist `--n-cpu-moe`).
- MTP: `--spec-type draft-mtp` und die **MTP-Modelldatei** (anderes Repo); ohne MTP-Kopf in der Datei passiert nichts.
- Kanäle: `kanaele` und `kontext` je Kanal angeben, das Werkzeug setzt `-c` = Kanäle × Kontext und `-np`.

## Auswerten
- **Frei (MiB) ist die Entscheidungsgröße.** Gemessen 10.11.2026 am Ryzen 9 9900X mit 12 GB VRAM: unter etwa 0,45 GiB frei bricht das Tempo ein (Lagen zu niedrig → VRAM-Überlauf, 21 bis 30 statt 65 bis 90 Token/s). Die Reserve des Resource-Schedulers ist 0,7 GiB; 0,37 bis 0,5 GiB sind nur nach einem Dauertest (Kontext schrittweise bis 78k füllen, VRAM-Spitze mitschreiben) akzeptabel, den der Captain freigibt.
- Windows-Grundlast im Leerlauf ist etwa 0,26 GiB; sie ist in "belegt" enthalten. Für Tabellenwerte der dynamischen Auswahl (`vram_gb` je Lagenzahl) die Grundlast abziehen.
- Tempo je Strom und zusammen getrennt nennen. Mehr Kanäle senken das Tempo je Strom stark (MoE mit Experten im RAM), die Summe steigt nur um etwa das 1,5-Fache.
- Kleine Standardbauten (z. B. `bench_std`) zeigen keinen Tempogewinn, weil die microVM-Tests den Großteil der Zeit brauchen. Der Tempogewinn zeigt sich bei großen Bauten.

## Ergebnis übertragen
1. **Rezept und Profil nur mit Ja des Captains ändern**, vorher Sicherung der Datei (`*.bak-<Datum>-<Grund>`), danach `test_role_routing` und `test_models_aufteilung` laufen lassen.
2. **Bau-Läufe nehmen `n_cpu_moe` fest aus dem Server-Block des Rezepts**, die dynamische Auswahl (Tabelle `dynamisch`) gilt nur im Router. Beides muss zum Profil passen; sonst läuft der Bau mit alten Werten (erkannt an der VRAM-Spitze).
3. Messdateien nicht ins Repo; die Zahlen kommen in die Wissensdatei (Skill `chat-sichern`), mit Datum und Einstellung.
4. Keine Pfade von Laufwerken in eingecheckten Dateien (`<modelle>` in der Stufendatei).

## Grenzen
- Das Werkzeug misst Erzeugungstempo mit Code-Aufgaben, **keine Qualität**. Für Qualität einen Standardbau mit dem Rezept laufen lassen (`devvm_build.py ... --spec bench_std`, echtes Projekt, gültiger Stempel).
- Es startet nur einen Server auf Port 8110 (änderbar mit `--port`) und schreibt nur die Ausgabedatei und Server-Logs daneben.
