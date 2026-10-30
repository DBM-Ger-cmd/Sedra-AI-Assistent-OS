# Messbericht Dynamische Rezepte R6 (30.10.2026)

RTX 4070 Ti (12 GB), Engine b11160, Qwen3.6-35B-A3B (`coder.local_primary`), Flash Attention an, KV q8_0, ubatch 512, 1 Slot, Fenster 32768, Prompt rund 11 850 Token (`benchmarks/moe_sweep.py`). Das Rezept ist im Cockpit mit dem Block `profile.dynamisch` geladen worden (Abschnitt 2).

## 1. Tabelle neu gemessen (ubatch 512)

VRAM belegt = 12,0 GiB minus frei nach der Antwort (wie in der Tabelle vom 9.10., also einschließlich der rund 0,4 GiB, die Windows selbst belegt). RAM belegt = freier RAM vor dem Laden minus nach der Antwort.

| Lagen im RAM | Erzeugen (Token/s) | Einlesen (Token/s) | VRAM belegt (GiB) | RAM belegt (GiB) | Tabelle vom 9.10. (ubatch 1024): VRAM / Erzeugen |
|---|---|---|---|---|---|
| 24 | 39,0 | 184,9 | 9,0 | 9,7 | – |
| 28 | 40,0 | 168,6 | 7,6 | 10,2 | 10,5 / 45,0 |
| 32 | 33,6 | 141,8 | 6,2 | 12,2 | 9,1 / 41,7 |
| 36 | 30,0 | 126,7 | 4,8 | 14,3 | 7,6 / 38,5 |
| 40 | nicht gelaufen | – | – | – | 6,1 / 35,5 |

- **ubatch 512 braucht rund 2,9 GiB weniger VRAM als ubatch 1024** bei gleicher Lagenzahl. Die Tabelle des Rezepts überschätzt den Bedarf damit um diesen Betrag.
- **Das Tempo liegt unter den Werten vom 9.10.**, weil diese Messung mit einem Prompt von 11 850 Token läuft und die Erzeugung bei langem Kontext langsamer ist. Verglichen werden darf deshalb nur innerhalb dieser Tabelle.
- **Unter 28 Lagen gewinnt man kein Tempo mehr** (24 Lagen: 39,0 gegen 40,0), braucht aber 1,4 GiB mehr VRAM.
- **40 Lagen im RAM** ließen sich nicht starten: Der Server brach beim Laden mit `CUDA error: out of memory` ab (Exit 3221226505). Vermutlich fehlt der Platz im Hauptspeicher für die gepinnten Puffer (freier RAM vor dem Laden rund 16 GiB, Bedarf bei 40 Lagen rund 16 GiB). Der Grund ist nicht bewiesen; zweimal derselbe Abbruch. `moe_sweep` bricht nach einem Fehler ab und lässt die übrigen Stufen aus, deshalb wurden 36, 32, 28 und 24 einzeln gestartet.

## 2. Das Cockpit mit dem Rezeptblock

Beim Laden von `coder.local_primary` über `/api/model/load` wählte das Cockpit **28 Lagen im RAM, 65 536 Kontext (2 Slots)**; gerechnet 10,5 GB VRAM und 10,23 GB RAM, gemessen rund 8,4 GB VRAM und rund 10,1 GB RAM. Das Laden dauerte 42 s. Der VRAM wurde in diesem Fall um rund 2 GB zu hoch gerechnet, wie in Abschnitt 1 zu erwarten.

Zwei Fehler dabei gefunden und behoben (Commit 8bdecd9):

1. **Der Lader zog die eigene Reservierung ab.** Der Modell-Scheduler reserviert vor dem Start, der Lader wählte danach mit dem Rest und lehnte mit „Es fehlen 5,31 GB VRAM“ ab. `ResourceScheduler.stand(ignore=…)`, der Lader übergibt `server:<Rezept>`.
2. **Im Weg mit Scheduler wurde nichts gemessen.** `model_messwerte.json` blieb leer. `_load_via_scheduler` merkt jetzt den Unterschied (`stand(nur_messung=True)`, ohne Ledger).

## 3. Modelltest

- Harness-Abnahme Teil 1 mit Modell besteht (Werkzeugzeile, erstes Wort ohne Verzug, Stopp).
- `@runtime/README_RUNTIME.md`: Qwen ruft `datei_lesen` selbst auf und fasst die Datei richtig zusammen.
- GPU-Zelle: zeigt die RTX 4070 Ti („40 °C · 9,0/12 GB“). LibreHardwareMonitor läuft nicht, die Board-Sensoren fehlen deshalb.

## 4. KV-Rate

Aus `MESSBERICHT_SLOTS_2026-10-23.md` (freier VRAM bei mehr Gesamtkontext): rund 0,011 bis 0,014, im Mittel **0,0125 GiB je 1000 Token** (Summe über alle Slots). Sie steht **nicht** im Rezept: Mit der zu hohen Tabelle zusammen würde sie den Bedarf noch weiter aufblähen.

## 5. Vorschlag für das Rezept (noch nicht eingetragen)

```yaml
dynamisch:
  n_cpu_moe: {min: 24, max: 36}
  tabelle:
    bei_kontext: 32768
    punkte:
      - {lagen: 24, vram_gb: 9.0, tokens_s: 39.0}
      - {lagen: 28, vram_gb: 7.6, tokens_s: 40.0}
      - {lagen: 32, vram_gb: 6.2, tokens_s: 33.6}
      - {lagen: 36, vram_gb: 4.8, tokens_s: 30.0}
  vram_fix_gb: 1.5
  ram_aufschlag_gb: 0.0
  ram_untergrenze_gb: 8
```

`ram_aufschlag_gb` 0,0: Die Formel ergibt damit 10,2 / 11,6 / 13,0 / 14,4 GiB RAM für 24 / 28 / 32 / 36 Lagen gegen gemessen 9,7 / 10,2 / 12,2 / 14,3, also immer leicht darüber. Mit dem Aufschlag 1,5 lag sie 1,5 GiB zu hoch.

Mit der Tabelle wählt die Auswahl bei freiem Speicher **24 Lagen** (die kleinste Lagenzahl, die passt), obwohl 28 Lagen gleich schnell sind und 1,4 GiB VRAM weniger brauchen. Die Entscheidung dazu liegt beim Captain: entweder `min: 28` im Rezept oder die Regel „kleinste Lagenzahl“ ändern.

## 6. Offen

- Der Rezeptblock bleibt, wie er ist, bis der Captain den Vorschlag aus Abschnitt 5 freigibt.
- Nicht gemessen: das Laden bei knappem Speicher mit echtem Modell (ohne fremde Last auf der GPU nicht herstellbar; die Auswahl ist mit den echten Zahlen in `test_dynamische_rezepte` geprüft) und 40 Lagen im RAM.
- Der Messspeicher `model_messwerte.json` füllt sich erst nach einem Neustart des Cockpits mit dem Fix; danach ersetzen Messwerte die Rechnung.
