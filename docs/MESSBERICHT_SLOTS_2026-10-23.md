# Messbericht: parallele Slots (Spec 2, Messung S2.1)

Gemessen in der Nacht 22./23.10.2026 auf der RTX 4070 Ti (12 GB), Engine b11160, Flash Attention an, KV q8_0, Rezepte unverändert. Werkzeug: `benchmarks/slot_measurement.py` (ein Befehl, eine Lease, Abbruchkriterien, Rezepte und Konfiguration nur gelesen). Rohdaten (nicht im Repo): `slot_messung_2026-10-23_lauf1.json` und `slot_messung_2026-10-23.json` im Messordner des Projekts. Kein Abbruch, keine Treiberereignisse, nie über 11,5 GiB (größter Wert 11,21 GiB).

## Ablauf und ein Fehler der Messung

- **Lauf 1** (Slots 1 bis 4, Hauptmodell und Hilfsmodell, 1 h 25 min): Für 1 Slot vollständig. Für 2 bis 4 Slots brach jede Kontextleiter an der ersten Stufe mit `context_mismatch` ab. Ursache war eine falsche Annahme des Werkzeugs: Bei `-np N` teilt Build b11160 den Gesamtkontext `-c` auf die Slots auf, und `/props` meldet das Fenster **je Slot**, nicht die Summe. Der Server war in Ordnung.
- **Lauf 2** (Slots 2 bis 4, nach der Korrektur, 1 h 28 min): vollständig durchgelaufen. Die Werte für 1 Slot stammen aus Lauf 1.
- **Zweite Einschränkung:** Das Werkzeug wertete es als Fehler, wenn die Enden der gleichzeitigen Anfragen weit auseinanderlagen. Der Server arbeitet aber das Vorladen (Prompt) der Slots nacheinander ab, deshalb liegen die Enden bei großen Prompts naturgemäß auseinander. Alle Antworten waren in diesen Fällen richtig (`ok`). Die Leitern für 2 bis 4 Slots sind daher an der **ersten so gewerteten Stufe** beendet worden; die „sicheren“ Fenster unten sind **Untergrenzen**. Das Werkzeug ist korrigiert (Enden-Abstand wird nur noch gemeldet, `ends_close`); eine Nachmessung der abgebrochenen Stufen steht aus.

## Ergebnisse

Fenster je Slot = was die Leiter als sicher bestanden hat (Nadel-im-Heuhaufen bei 85 % Füllung, mindestens 1 GiB VRAM frei, keine Treiberereignisse). Token/s gesamt = erzeugte Token durch die Wanddauer des Laufs (mit Vorladen); Token/s je Slot = Median der Serverangabe. VRAM-Spitze = belegter Speicher der ganzen Karte (enthält etwa 2,2 GiB, die der Desktop belegt).

Hauptmodell Qwen3.6-35B-A3B (`coder.local_primary`, MoE mit Experten im Hauptspeicher, kein MTP):

| Slots | Fenster je Slot (sicher) | Gesamtkontext | Token/s gesamt | Token/s je Slot | VRAM-Spitze (GiB) | Durchsatz gegen 1 Slot |
|---|---|---|---|---|---|---|
| 1 | 131072 | 131072 | 31,6 | 42,3 | 8,76 | – |
| 2 | mindestens 49152 | mindestens 98304 | 36,9 | 25,7 | 8,26 | +17 % |
| 3 | mindestens 16384 | mindestens 49152 | 44,9 | 19,1 | 8,05 | +42 % |
| 4 | mindestens 8192 | mindestens 32768 | 49,9 | 15,4 | 7,93 | +58 % |

Durchsatz bei 3 Slots mit Fenster 16384, bei 4 Slots mit 8192 gemessen (sicheres Fenster der Leiter, höchstens 32768).

Hilfsmodell Qwen3.5-9B Q6_K mit MTP (`coder.llama_qwen35`):

| Slots | Fenster je Slot (sicher) | Token/s gesamt (ohne MTP) | Token/s je Slot (ohne MTP) | VRAM-Spitze GiB (ohne MTP) |
|---|---|---|---|---|
| 1 | 98304 (131072 nicht bestanden) | 70,0 (56,5) | 76,2 | 8,77 |
| 2 | mindestens 24576 | 117,7 (100,2) | 65,7 (54,8) | 8,97 (8,22) |
| 3 | mindestens 8192 | 147,9 (135,5) | 56,9 (51,2) | 8,58 (7,78) |
| 4 | nicht bestimmt (Leiter an 8192 abgebrochen) | 155,7 (162,6) | 47,6 (46,8) | **11,21** (9,98) |

CPU (Hilfsmodell, `n_gpu_layers=0`): 1 Slot 7,6 Token/s, 2 Slots 9,7 Token/s gesamt (je Slot 6,6).

S0 (Verbindungsprüfung) bestand bei jeder Einstellung. `/slots` antwortet und zeigt N Einträge. Alle Läufe mit MTP und mehreren Slots blieben stabil (je 3 Läufe ohne Fehler).

## Auswertung und Empfehlung

- **Das Hauptmodell gewinnt wenig durch Slots.** Der Durchsatz steigt nur um 17 % (2 Slots) bis 58 % (4 Slots), während jeder Slot langsamer wird (42 auf 26, 19, 15 Token/s). Grund: Die Experten liegen im Hauptspeicher, das Tempo hängt an dessen Bandbreite, nicht an der GPU. **Empfehlung: 2 Slots als Standard**, Fenster 32768 je Slot (nachgewiesen bis 49152). Der Unterarbeiter und die Agenten warten dann seltener hintereinander, ohne dass ein Lauf unter 25 Token/s fällt. 3 und 4 Slots erst nach der Nachmessung (32768 je Slot ist bei 3 und 4 Slots noch nicht belegt), und der Gewinn bleibt klein.
- **Das Hilfsmodell skaliert gut:** +68 % bei 2 Slots, +111 % bei 3 Slots (MTP an). **Empfehlung: 2 Slots als Standard** (Fenster bis 24576 belegt), 3 Slots sobald die Nachmessung 16384 oder mehr belegt. Mit MTP bei 4 Slots ist es nicht empfohlen: kein Gewinn gegenüber ohne MTP und 11,21 GiB Spitze, das ist über der nutzbaren Grenze (10,8 GB einschließlich Reserve). **MTP ab 4 Slots aus.**
- **Hauptmodell und Hilfsmodell gleichzeitig** wurde nicht gemessen und passt nicht in die Karte (ein Server, ein Modell).
- **CPU-Betrieb lohnt nicht** (unter 10 Token/s).
- **Kontextgrenze:** Die Leiter-Untergrenzen für 3 und 4 Slots liegen unter dem Standardfenster 32768 des Profils `standard`. Bis zur Nachmessung ist 2 Slots die einzige Einstellung, die dieses Fenster belegt.

## Folgen für das Design (Spec 2)

- **D2.5 und B-4 korrigieren:** Der Loader vergleicht das **Fenster je Slot** mit `contextLength` aus `/props`; es gibt keine Summe zu bilden. `-c` bleibt `Slots × Fenster`.
- **OP-S2-01 beantwortet** (`-c` wird geteilt, `/props` je Slot), **OP-S2-03 beantwortet** (`/slots` vorhanden), **OP-S2-07 beantwortet** (MTP mit mehreren Slots stabil; lohnt bis 3 Slots, bei 4 nicht).
- **`slot_ttl`/Obergrenze:** ein Lauf mit 65536 Token Prompt braucht rund 9 Minuten Vorladen je Slot beim Hauptmodell; `wait_max_s` (Vorgabe 600 s) und der Herzschlag-Abstand sind darauf abzustimmen.

## Offen: Nachmessung

Die Stufen, die nur wegen des Enden-Abstands abgebrochen wurden, sollten mit dem korrigierten Werkzeug nachgemessen werden (`slot_measurement.py … --slots 2,3,4` läuft noch einmal alles; gezielter wäre `context_ladder.py … --parallel N --from <Stufe>` je Fall). Betroffen: Hauptmodell 2 Slots ab 65536, 3 Slots ab 24576, 4 Slots ab 16384; Hilfsmodell 2 Slots ab 32768, 3 Slots ab 16384, 4 Slots ab 8192.
