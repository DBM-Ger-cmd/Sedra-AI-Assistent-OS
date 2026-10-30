"""Aufteilung eines MoE-Modells zwischen Grafikkarte und Arbeitsspeicher (SPEC_DYNAMISCHE_REZEPTE_v1 DR-01 bis DR-05, G2 §3).

Rein, ohne Dateizugriff. **Referenz von Claude** – der Bau `modelle_aufteilung` ist der zweite SEDRA-Bau unter einem Vorarbeiter; übernimmt der Captain ihn, ersetzt er diese Datei.
`bedarf` rechnet VRAM und RAM für eine Einstellung (Lagen im RAM, Kontext), `waehlen` nimmt die kleinste Lagenzahl, die in den freien Speicher passt."""

GRUND = "kleinste Lagenzahl, die in den freien Speicher passt"


def _zahl(wert, name):
    if isinstance(wert, bool) or not isinstance(wert, (int, float)) or wert != wert or wert in (float("inf"), float("-inf")):
        raise ValueError(name)
    return float(wert)


def _ganz(wert, name):
    if isinstance(wert, bool) or not isinstance(wert, int):
        raise ValueError(name)
    return wert


def _punkte(dyn):
    try:
        spanne = dyn["n_cpu_moe"]
        roh = dyn["tabelle"]["punkte"]
        punkte = sorted(((_ganz(p["lagen"], "lagen"), _zahl(p["vram_gb"], "vram_gb"), p.get("tokens_s")) for p in roh), key=lambda p: p[0])
        kontext = _ganz(dyn["tabelle"]["bei_kontext"], "bei_kontext")
        fix = _zahl(dyn["vram_fix_gb"], "vram_fix_gb")
        aufschlag = _zahl(dyn["ram_aufschlag_gb"], "ram_aufschlag_gb")
        boden = _zahl(dyn["ram_untergrenze_gb"], "ram_untergrenze_gb")
        von, bis = _ganz(spanne["min"], "min"), _ganz(spanne["max"], "max")
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("dynamisch_ungueltig") from exc
    if len(punkte) < 2 or von > bis or kontext <= 0 or len({p[0] for p in punkte}) != len(punkte):
        raise ValueError("dynamisch_ungueltig")
    return punkte, kontext, fix, aufschlag, boden, von, bis


def _linie(punkte, lagen, index):
    if lagen <= punkte[0][0]:
        (x0, *w0), (x1, *w1) = punkte[0], punkte[1]
    elif lagen >= punkte[-1][0]:
        (x0, *w0), (x1, *w1) = punkte[-2], punkte[-1]
    else:
        i = max(k for k, p in enumerate(punkte) if p[0] <= lagen)
        (x0, *w0), (x1, *w1) = punkte[i], punkte[i + 1]
    if w0[index - 1] is None or w1[index - 1] is None:
        return None
    return w0[index - 1] + (w1[index - 1] - w0[index - 1]) * (lagen - x0) / (x1 - x0)


def bedarf(dyn, lagen, kontext, kv_rate_gb_je_1k, groesse_gb, slots=1):
    punkte, bei, fix, aufschlag, boden, von, bis = _punkte(dyn)
    lagen = _ganz(lagen, "lagen")
    kontext = _ganz(kontext, "kontext")
    slots = _ganz(slots, "slots")
    if not von <= lagen <= bis or kontext <= 0 or slots <= 0:
        raise ValueError("ausserhalb")
    rate = 0.0 if kv_rate_gb_je_1k is None else _zahl(kv_rate_gb_je_1k, "kv_rate")
    groesse = _zahl(groesse_gb, "groesse_gb")
    tabelle = _linie(punkte, lagen, 1)
    unterschied = rate * (kontext * slots - bei) / 1000
    unterschied = max(unterschied, -fix)
    return {"vram_gb": round(tabelle + unterschied, 3), "ram_gb": round(max(boden, groesse - (tabelle - fix) + aufschlag), 3)}


def waehlen(dyn, kontexte, frei_vram_gb, frei_ram_gb, reserve_vram_gb, reserve_ram_gb, kv_rate_gb_je_1k, groesse_gb, slots=1, gemessen=None):
    punkte, bei, fix, aufschlag, boden, von, bis = _punkte(dyn)
    budget_vram = _zahl(frei_vram_gb, "frei_vram") - _zahl(reserve_vram_gb, "reserve_vram")
    budget_ram = _zahl(frei_ram_gb, "frei_ram") - _zahl(reserve_ram_gb, "reserve_ram")
    if not isinstance(kontexte, (list, tuple)) or not kontexte:
        return {"ok": False, "fehlt": None, "beste": None, "vorschlag": "Kein Kontext zur Auswahl."}
    gemessen = gemessen if isinstance(gemessen, dict) else {}
    beste = None
    for kontext in kontexte:
        for lagen in range(von, bis + 1):
            wert, quelle = gemessen.get((lagen, kontext)), "gemessen"
            if wert is None:
                wert, quelle = bedarf(dyn, lagen, kontext, kv_rate_gb_je_1k, groesse_gb, slots), "gerechnet"
            vram, ram = float(wert["vram_gb"]), float(wert["ram_gb"])
            fehlt_vram, fehlt_ram = max(0.0, vram - budget_vram), max(0.0, ram - budget_ram)
            if fehlt_vram == 0 and fehlt_ram == 0:
                tempo = _linie(punkte, lagen, 2)
                return {"ok": True, "lagen": lagen, "kontext": kontext, "vram_gb": round(vram, 3), "ram_gb": round(ram, 3),
                        "tokens_s": None if tempo is None else round(tempo, 2), "quelle": quelle, "grund": GRUND}
            mangel = max(fehlt_vram, fehlt_ram)
            if beste is None or mangel < beste[0]:
                beste = (mangel, kontext, lagen, vram, ram, fehlt_vram, fehlt_ram)
    _, kontext, lagen, vram, ram, fehlt_vram, fehlt_ram = beste
    satz = (f"Es fehlen {fehlt_vram:.2f} GB VRAM und {fehlt_ram:.2f} GB RAM bei {lagen} Lagen im RAM und {kontext} Kontext; "
            "Programme mit Grafikspeicher beenden oder ein kleineres Rezept wählen.")
    return {"ok": False, "fehlt": {"vram_gb": round(fehlt_vram, 3), "ram_gb": round(fehlt_ram, 3)},
            "beste": {"kontext": kontext, "lagen": lagen, "vram_gb": round(vram, 3), "ram_gb": round(ram, 3)}, "vorschlag": satz}
