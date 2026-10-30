"""Dynamische Rezepte (SPEC_DYNAMISCHE_REZEPTE_v1 DR-01 bis DR-05, G2 §3): die Aufteilung eines MoE-Modells zwischen Grafikkarte und Arbeitsspeicher – der zweite Bau eines
SEDRA-Agenten UNTER EINEM VORARBEITER über die Harness (nach lauf_fortschritt).
Claude schrieb diese Datei, die versteckten Prüfungen (CHECKS, 12 Zeilen, L3 ≤ 20) und die Referenz (benchmarks/devvm_refs/modelle_aufteilung).
SEDRA baut `aufteilung.py` nach der Aufgabe unten; besteht der Bau und übernimmt der Captain ihn, ersetzt er models/aufteilung.py. Scheitert er, gilt V4: die Referenz
bleibt, der Befund steht im Bericht.
Bau nur auf Ansage des Captains (es lädt ein Modell): spec_check.py modelle_aufteilung --vm --project <projekt>, dann über die Vorarbeiter-Sitzung (Aufgaben-Freigabe,
Lauf devvm_build) – nicht von Hand."""

NOTES = '''# Notes for aufteilung
Pure Python 3 standard library only (no imports are needed). One file `aufteilung.py`. Never modify the arguments. No comments and no docstrings; small private
helpers instead of copied code. Names are German on purpose (the rest of SEDRA uses them): keep them exactly, also the dict keys and the error text.
Numbers in the results are rounded with round(x, 3) (tokens_s with round(x, 2)).
'''

TASK = '''Write `aufteilung.py` with two functions: how a MoE model is split between the graphics card (VRAM) and the main memory (RAM).

`dyn` is a dict:
  {"n_cpu_moe": {"min": int, "max": int},                      # allowed number of layers whose experts stay in RAM (inclusive range)
   "tabelle": {"bei_kontext": int, "punkte": [{"lagen": int, "vram_gb": float, "tokens_s": float (optional)}, ...]},   # measurements at context `bei_kontext`
   "vram_fix_gb": float, "ram_aufschlag_gb": float, "ram_untergrenze_gb": float}
A `dyn` that is not a dict of this shape (missing key, wrong type, fewer than 2 points, duplicate `lagen`, min above max, bei_kontext not above 0, a bool or a non-finite number
where a number is expected) raises ValueError("dynamisch_ungueltig"). Points may come in any order.

Function `bedarf(dyn, lagen, kontext, kv_rate_gb_je_1k, groesse_gb, slots=1)` returns {"vram_gb": float, "ram_gb": float}.
- `lagen`, `kontext`, `slots` must be ints (not bool); `lagen` inside min..max, `kontext` > 0, `slots` > 0; otherwise ValueError. `kv_rate_gb_je_1k` may be None (counts as 0.0).
- `tabelle_vram(lagen)`: linear interpolation of vram_gb between the two neighbouring points (sorted by `lagen`); outside the first and last point continue the line of
  the nearest two points (so the first two for lagen below the first point, the last two above the last point).
- `unterschied = kv_rate * (kontext * slots - bei_kontext) / 1000`, but never below `-vram_fix_gb`.
- vram_gb = round(tabelle_vram(lagen) + unterschied, 3).
- gewichte_im_vram = tabelle_vram(lagen) - vram_fix_gb; ram_gb = round(max(ram_untergrenze_gb, groesse_gb - gewichte_im_vram + ram_aufschlag_gb), 3).

Function `waehlen(dyn, kontexte, frei_vram_gb, frei_ram_gb, reserve_vram_gb, reserve_ram_gb, kv_rate_gb_je_1k, groesse_gb, slots=1, gemessen=None)`:
- budget_vram = frei_vram_gb - reserve_vram_gb; budget_ram = frei_ram_gb - reserve_ram_gb.
- `kontexte` is a list of contexts, largest first. For each context in the given order, try every `lagen` from min to max (smallest first). A combination fits when
  vram <= budget_vram and ram <= budget_ram. The FIRST fitting combination wins: return
  {"ok": True, "lagen": int, "kontext": int, "vram_gb": float, "ram_gb": float, "tokens_s": float or None, "quelle": "gerechnet" or "gemessen",
   "grund": "kleinste Lagenzahl, die in den freien Speicher passt"} (exactly these keys).
  tokens_s is the linear interpolation of the points' `tokens_s` at `lagen` (same line rules as above, rounded to 2 decimals), None when a needed point has no tokens_s.
- `gemessen` (dict or None): a key (lagen, kontext) with a value {"vram_gb": x, "ram_gb": y} replaces the calculation for exactly that combination (quelle "gemessen").
- Nothing fits: for every tried combination the shortfall is fehlt_vram = max(0, vram - budget_vram) and fehlt_ram = max(0, ram - budget_ram); the best one is the one with the
  smallest max(fehlt_vram, fehlt_ram); on a tie the first tried one. Return {"ok": False, "fehlt": {"vram_gb": x, "ram_gb": y}, "beste": {"kontext": int, "lagen": int,
  "vram_gb": float, "ram_gb": float}, "vorschlag": str} with the best's rounded numbers; `vorschlag` is a German sentence that contains the best combination's
  lagen and kontext as numbers.
- An empty or non-list `kontexte`: {"ok": False, "fehlt": None, "beste": None, "vorschlag": "Kein Kontext zur Auswahl."}. An invalid `dyn` raises ValueError.
'''

HEAD = '''
from aufteilung import bedarf, waehlen
DYN = {"n_cpu_moe": {"min": 24, "max": 40}, "vram_fix_gb": 1.5, "ram_aufschlag_gb": 1.5, "ram_untergrenze_gb": 8,
       "tabelle": {"bei_kontext": 32768, "punkte": [{"lagen": 36, "vram_gb": 7.6, "tokens_s": 38.5}, {"lagen": 28, "vram_gb": 10.5, "tokens_s": 45.0},
                                                    {"lagen": 40, "vram_gb": 6.1, "tokens_s": 35.5}, {"lagen": 32, "vram_gb": 9.1, "tokens_s": 41.7}]}}
G, K = 17.73, 0.04
def nahe(a, b, e=0.01):
    return abs(a - b) <= e
def werft(f, *a, **k):
    try:
        f(*a, **k)
    except ValueError:
        return True
    return False
def preis(lagen, kontext, slots=1):
    return bedarf(DYN, lagen, kontext, K, G, slots)
'''

CHECKS = HEAD + '''
assert preis(28, 32768)["vram_gb"] == 10.5 and nahe(preis(28, 32768)["ram_gb"], 10.23) and preis(40, 32768)["vram_gb"] == 6.1 and nahe(preis(40, 32768)["ram_gb"], 14.63)
assert nahe(preis(30, 32768)["vram_gb"], 9.8) and nahe(preis(30, 32768)["ram_gb"], 10.93) and nahe(preis(34, 32768)["vram_gb"], 8.35)
assert nahe(preis(24, 32768)["vram_gb"], 11.9) and nahe(bedarf(DYN, 40, 32768, K, G)["vram_gb"], 6.1)
assert nahe(preis(28, 65536)["vram_gb"], 11.811) and nahe(preis(28, 16384)["vram_gb"], 9.845) and nahe(bedarf(DYN, 28, 1024, 0.1, G)["vram_gb"], 9.0)
assert preis(28, 16384, 2) == preis(28, 32768) and bedarf(DYN, 28, 32768, None, G) == preis(28, 32768) and bedarf(DYN, 30, 32768, K, 2.0)["ram_gb"] == 8.0
assert all(werft(bedarf, DYN, *a) for a in ((23, 32768, K, G), (41, 32768, K, G), ("x", 32768, K, G), (True, 32768, K, G), (30, 0, K, G), (30, 32768, K, G, 0)))
assert werft(bedarf, {}, 30, 32768, K, G) and werft(bedarf, dict(DYN, tabelle={"bei_kontext": 32768, "punkte": [{"lagen": 28, "vram_gb": 10.5}]}), 30, 32768, K, G) and werft(waehlen, {}, [32768], 10, 10, 0, 0, K, G)
a = waehlen(DYN, [32768], 10.65, 14.3, 0.7, 1.5, K, G)
assert a["ok"] and a["lagen"] == 30 and a["kontext"] == 32768 and nahe(a["vram_gb"], 9.8) and nahe(a["ram_gb"], 10.93) and nahe(a["tokens_s"], 43.35) and a["quelle"] == "gerechnet"
assert set(a) == {"ok", "lagen", "kontext", "vram_gb", "ram_gb", "tokens_s", "quelle", "grund"} and a["grund"] == "kleinste Lagenzahl, die in den freien Speicher passt"
b = waehlen(DYN, [65536, 32768], 10.65, 14.3, 0.7, 1.5, K, G)
c = waehlen(DYN, [65536, 32768], 10.65, 12.5, 0.7, 1.5, K, G)
assert (b["kontext"], b["lagen"]) == (65536, 34) and (c["kontext"], c["lagen"]) == (32768, 30)
assert waehlen(DYN, [32768], 10.65, 14.3, 0.7, 1.5, K, G, gemessen={(30, 32768): {"vram_gb": 11.0, "ram_gb": 10.0}})["lagen"] == 31
d = waehlen(DYN, [32768], 10.65, 14.3, 0.7, 1.5, K, G, gemessen={(28, 32768): {"vram_gb": 9.0, "ram_gb": 9.0}})
assert d["lagen"] == 28 and d["quelle"] == "gemessen" and d["vram_gb"] == 9.0
e = waehlen(DYN, [32768, 16384], 5.0, 8.0, 0.7, 1.5, K, G)
assert e["ok"] is False and e["fehlt"]["vram_gb"] > 0 and 24 <= e["beste"]["lagen"] <= 40 and str(e["beste"]["lagen"]) in e["vorschlag"] and str(e["beste"]["kontext"]) in e["vorschlag"]
assert waehlen(DYN, [], 10, 10, 0, 0, K, G) == {"ok": False, "fehlt": None, "beste": None, "vorschlag": "Kein Kontext zur Auswahl."} and waehlen(DYN, "x", 10, 10, 0, 0, K, G)["ok"] is False
'''

STAGES = [
    {"name": "aufteilung", "no_own_check": False, "task": TASK, "hidden": {"hidden_aufteilung.py": CHECKS}},
]
