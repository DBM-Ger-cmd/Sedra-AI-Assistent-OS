# Vergleich neuer Coding-Modelle: Plan und Referenz (2026-10-09)

Anlass: Der Captain lädt Modelle für das Coden herunter und ist mit der allgemeinen Geschwindigkeit nicht zufrieden. Als Referenz gilt der letzte erfolgreiche GUPPI-Bau (am008_meter).

## Referenz (gemessen am 2026-10-08, Qwen3-Coder-30B-A3B, `n_cpu_moe 44`, Kontext 32k, `check_first` + `tidy`, rework 2)

| Größe | Wert |
|---|---|
| Spec | `am008_meter` (4 Stufen: daily, heatmap, cards, all) |
| Ergebnis | alle 4 versteckten Kriterien bestanden, im Judge bestätigt |
| Gesamtzeit | 4740 s (79 min) |
| Agentenläufe / Aufrufe | 16 / 252 |
| Tokens (Summe der Agentenläufe) | etwa 108.700 |
| Durchsatz gesamt | etwa 22,6 Token/s (inklusive Werkzeug- und VM-Zeit) |
| Zeit je Stufe | daily 961 s, heatmap 1015 s, cards 831 s, all 1926 s |
| Verschwendung | 2 starke Coder-Läufe endeten mit Stoppgrund `time` (je etwa 600 s, 17.000 Tokens) |
| Zweite Referenz (schwer, Misserfolg) | `am009_collector`: 3 von 3 Kriterien durchgefallen, 7362 s, `am007_crews`: 2 von 7 bestanden, 14437 s |

## Messregeln für jedes neue Modell

1. Ein Rezept anlegen (Datei, Quantisierung, `n_cpu_moe`, Kontext, `ubatch`). VRAM bis höchstens 11,5 GB laut `nvidia-smi` (Entscheidung des Captains vom 2026-10-08). Das Modell hält die GPU-Lease.
2. Kurzer Geschwindigkeitstest mit festem Prompt: Token/s beim Prompt-Einlesen und beim Erzeugen, VRAM-Spitze, sicherer Kontext.
3. Bau von `am008_meter` mit denselben Optionen (`--coder <schlüssel>`, `check_first`, `tidy`, 32k, rework 2). Gemessen werden Gesamtzeit, Tokens, Token/s, bestandene Stufen, Nacharbeitsrunden, `time`-Stopps.
4. Wenn das Modell die Referenz schlägt (schneller bei gleicher Qualität): zweiter Lauf mit der schweren Spec `am009_collector`.
5. Ergebnis als Tabelle ins Logbuch. Nichts wird integriert oder zum Standard erklärt, bevor der Captain entscheidet.

## Hinweise aus den bisherigen Läufen

- 90 % der Zeit ist Token-Erzeugung. Mehr Experten auf der GPU (`n_cpu_moe` senken) und ein schnelleres Modell wirken direkt.
- Tool-Aufrufe brauchen ein Modell, dessen Rezept `jinja: true` zulässt (gpt-oss ist als Werkzeug-Agent nicht nutzbar).
- Die starken Coder-Läufe laufen in ein Zeitlimit von etwa 600 s. Ein schnelleres Modell oder ein höheres Limit spart dort am meisten.
