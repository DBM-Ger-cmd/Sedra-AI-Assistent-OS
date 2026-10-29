# Harness-Shell Stufe 3, N8: der Fortschritt eines Laufs aus den letzten Zeilen seiner Ausgabe (SPEC_HARNESS_SHELL_v1 HS-31, G2 Stufe 3 §6.3).
# Gebaut von SEDRA als erster Bau eines Agenten UNTER EINEM VORARBEITER über die Harness (Pilot, 29.10.2026: Vorarbeiter-Sitzung, Aufgaben-Freigabe T-E0A4F78E,
# Lauf devvm_build, Qwen3.6-35B-A3B, versteckt 12/12, Kandidat runtime_data/devvm_candidates/harness_lauf_fortschritt/attempt_01_20261029_135259).
# Übernommen (Captain 29.10.2026: „Ohne toten Code“) mit EINER Änderung von Claude: die ungenutzte Funktion `_gültige_regel` ist entfernt (Eingriff im Logbuch).
# Sonst unverändert; die Referenz von Claude steht in benchmarks/devvm_refs/harness_lauf_fortschritt, test_harness_lauf_fortschritt_vergleich hält beide gleich.
import re


def _gültige_zeilen(zeilen):
    if not isinstance(zeilen, list):
        return []
    ergebnis = []
    for z in zeilen:
        if not isinstance(z, str):
            continue
        gestrippt = z.strip()
        if gestrippt == "":
            continue
        ergebnis.append(gestrippt)
    return ergebnis


def _kürze_text(line):
    if len(line) <= 80:
        return line
    return line[:79] + "…"


def fortschritt_aus(zeilen, regel):
    if not isinstance(regel, dict):
        return None
    if "art" not in regel:
        return None
    art = regel["art"]
    if art not in ("text", "zeilen", "prozent"):
        return None

    if art != "text":
        if "regex" not in regel:
            return None
        regex_str = regel["regex"]
        if not isinstance(regex_str, str):
            return None
        try:
            compiled = re.compile(regex_str)
        except re.error:
            return None
    else:
        compiled = None

    zeilen = _gültige_zeilen(zeilen)

    if art == "text":
        if not zeilen:
            return {"prozent": None, "text": ""}
        letzte = zeilen[-1]
        return {"prozent": None, "text": _kürze_text(letzte)}

    if art == "zeilen":
        if compiled.groups != 2:
            return None
        for zeile in reversed(zeilen):
            m = compiled.search(zeile)
            if m is None:
                continue
            try:
                done = int(m.group(1))
                total = int(m.group(2))
            except (ValueError, TypeError):
                continue
            if total <= 0:
                continue
            prozent = int(done / total * 100)
            prozent = max(0, min(100, prozent))
            return {"prozent": prozent, "text": _kürze_text(zeile)}
        return None

    if art == "prozent":
        if compiled.groups != 1:
            return None
        for zeile in reversed(zeilen):
            m = compiled.search(zeile)
            if m is None:
                continue
            gruppe = m.group(1)
            try:
                zahl = float(gruppe)
            except (ValueError, TypeError):
                continue
            prozent = int(zahl)
            prozent = max(0, min(100, prozent))
            return {"prozent": prozent, "text": _kürze_text(zeile)}
        return None

    return None
