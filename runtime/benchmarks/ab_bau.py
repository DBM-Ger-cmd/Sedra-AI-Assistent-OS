"""Standard-Vergleich von Bau-Einstellungen (A/B), zum Beispiel mit und ohne Arbeitsanweisung oder deutsch und englisch.

  python benchmarks/ab_bau.py <spec> [--paare 3] [--arme ohne,bau_coder:de] [--projekt <ordner>] [--rezept <id> [--kontext <n>]]
      Ohne --start wird nur der PLAN gezeigt und geprueft (Stempel, GPU, Prozesse, RAM). Nichts laeuft.
  python benchmarks/ab_bau.py <spec> ... --start
      Nur mit dem Ja des Captains: die Laeufe starten, abwechselnd (Paar 1: Arm A, Arm B; Paar 2: ...), nacheinander auf der einen GPU.

Arme: `ohne` (keine Arbeitsanweisung) oder `<typ>` / `<typ>:de` / `<typ>:en` (Arbeitsanweisung; `:en` bricht ab, wenn die englische Fassung nicht gilt,
damit kein stiller Rueckfall auf Deutsch den Vergleich verfaelscht).

Gemessen wird je Lauf: Stufen bestanden, Dauer, Modellaufrufe, Nacharbeiten, Token. Dazu der DIFFERENZTEST gegen die Referenz, wenn es
benchmarks/ab_diff/<spec>.py gibt (MODUL und faelle(ref)): bestandene Tests beweisen wenig, Abweichungen bei Randfaellen zeigen die Qualitaet.
Ergebnis: <projekt>/runtime_data/ab_bau/<spec>_<zeit>/ (ergebnis.json, bericht.md, ein Log je Lauf).

Ein Unterschied bei wenigen Laeufen ist ein Indiz, kein Beweis. Der Bericht nennt n und warnt unter 5 Laeufen je Arm. Keine Tests oder Messungen parallel."""
import argparse
import copy
import functools
import importlib.util
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
BENCH = RUNTIME / "benchmarks"
PY = RUNTIME / ".venv" / "Scripts" / "python.exe"
if not PY.exists():
    PY = Path(sys.executable)
GPU_RUHIG_MIB = 3072
RAM_MIN_GB = 12.0        # darunter Sperre; die Nachtkette verlangt 14, der Bau selbst lief am 11.11. bei 13,3 und 13,9 GB frei sauber
RAM_WARN_GB = 14.0       # darunter nur ein Hinweis
ARM = re.compile(r"ohne|[a-z0-9_]{1,60}(:(de|en))?")


def projekt_standard():
    return RUNTIME.parent / "workspace" / "SEDRA_OS"


def arme_lesen(text):
    arme = [a.strip() for a in text.split(",") if a.strip()]
    if len(arme) < 2 or len(set(arme)) != len(arme) or not all(ARM.fullmatch(a) for a in arme):
        raise SystemExit(f"--arme: mindestens zwei verschiedene Arme aus 'ohne' oder '<typ>[:de|:en]', gegeben {text!r}")
    return arme


def befehl_fuer(projekt, spec, arm, pidfile, profil, rezept, kontext):
    b = [str(PY), "benchmarks/devvm_build.py", str(projekt), "--spec", spec, "--profile", profil, "--pidfile", str(pidfile), "--no-logbook"]
    if rezept:
        b += ["--coder", rezept] + (["--context", str(kontext)] if kontext else [])
    if arm != "ohne":
        typ, _, sprache = arm.partition(":")
        b += ["--arbeitsanweisung", typ, "--anweisung-sprache", sprache or "auto"]
    return b


def vorpruefung(projekt, spec):
    """Liste der Gruende, die einen Start verbieten (leer = frei). Nur lesend, ausser dem Stempel (der schreibt nur seine Stempeldatei)."""
    probleme = []
    if not (BENCH / "devvm_specs" / f"{spec}.py").is_file():
        return [f"Spec {spec} gibt es nicht"]
    lauf = subprocess.run([str(PY), "benchmarks/spec_check.py", spec, "--vm", "--project", str(projekt)], cwd=str(RUNTIME), capture_output=True, text=True, errors="replace")
    if lauf.returncode != 0:
        probleme.append("spec_check --vm nicht ok: " + " | ".join(z.strip() for z in lauf.stdout.splitlines()[-3:]))
    try:
        belegt = int(subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout.split()[0])
        if belegt > GPU_RUHIG_MIB:
            probleme.append(f"GPU belegt: {belegt} MiB (ruhig ist hoechstens {GPU_RUHIG_MIB})")
    except (OSError, ValueError, IndexError):
        probleme.append("GPU-Stand nicht lesbar (nvidia-smi)")
    if "llama-server.exe" in subprocess.run(["tasklist", "/FI", "IMAGENAME eq llama-server.exe", "/NH"], capture_output=True, text=True, errors="replace").stdout:
        probleme.append("ein llama-server laeuft (der Bau beendet ihn; das braucht das Ja des Captains)")
    if (Path(projekt) / "runtime_data" / "bau_schleife.lock").exists():
        probleme.append("bau_schleife.lock vorhanden: ein Bau laeuft oder lief ab")
    try:
        import psutil
        frei = psutil.virtual_memory().available / 2 ** 30
        if frei < RAM_MIN_GB:
            probleme.append(f"freier RAM {frei:.1f} GB (Sperre unter {RAM_MIN_GB} GB)")
        elif frei < RAM_WARN_GB:
            print(f"  Hinweis: freier RAM {frei:.1f} GB (die Nachtkette verlangt {RAM_WARN_GB} GB); kein Hindernis, aber andere Programme schliessen hilft dem Tempo")
    except ImportError:
        pass
    return probleme


def kennzahlen(text):
    ok = len(re.findall(r"stage S\d+: hidden PASSED", text))
    schlecht = len(re.findall(r"stage S\d+: hidden FAILED", text))
    ag = re.findall(r"agent (.+?)\s+\S+\s+\S+\s+(\d+) calls\s+[\d.]+ s (\d+) tokens, (\d+) prompt", text)
    return {"stufen_ok": ok, "stufen_gesamt": ok + schlecht, "aufrufe": sum(int(a[1]) for a in ag), "nacharbeiten": sum(1 for a in ag if "rework" in a[0]),
            "tokens_antwort": sum(int(a[2]) for a in ag), "tokens_prompt": sum(int(a[3]) for a in ag),
            "anweisung": (re.findall(r"work instruction \S+ \((de|en)\)", text) or [None])[0]}


def modul_laden(pfad, name):
    spec = importlib.util.spec_from_file_location(name, pfad)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def aufrufbar(cfg, mod, fn):
    """Die Funktion `fn` des Moduls, oder eine Hilfsfunktion aus cfg.HILFEN (Signatur h(modul, *args)), wenn die Fallliste Dateien, Zeit oder Zustand braucht."""
    hilfen = getattr(cfg, "HILFEN", {})
    return functools.partial(hilfen[fn], mod) if fn in hilfen else getattr(mod, fn)


def _ruf(f, *a):
    vorher = copy.deepcopy(a)
    try:
        r = f(*a)
        if a != vorher:
            return ("MUTIERT", None)
        return ("ok", json.dumps(r, sort_keys=True, default=str))
    except Exception as e:  # noqa: BLE001 - jede Art Fehler zaehlt als Verhalten
        return ("fehler", f"{type(e).__name__}:{e}")


def differenz(spec, kandidat):
    """Abweichungen des Kandidaten von der Referenz bei den Randfaellen aus ab_diff/<spec>.py. None, wenn es dafuer keine Faelle gibt."""
    datei = BENCH / "ab_diff" / f"{spec}.py"
    if not datei.is_file():
        return None
    cfg = modul_laden(datei, f"ab_diff_{spec}")
    ref = modul_laden(BENCH / "devvm_refs" / spec / f"{cfg.MODUL}.py", "ref_" + spec)
    ziel = Path(kandidat) / f"{cfg.MODUL}.py"
    if not ziel.is_file():
        return {"faelle": 0, "abweichungen": ["Kandidat hat " + ziel.name + " nicht"]}
    kand = modul_laden(ziel, "kand_" + spec)
    faelle = cfg.faelle(ref)
    abw, n = [], 0
    for fn, liste in faelle.items():
        for args in liste:
            n += 1
            soll, ist = _ruf(aufrufbar(cfg, ref, fn), *args), _ruf(aufrufbar(cfg, kand, fn), *args)
            if soll != ist:
                abw.append(f"{fn}{tuple(map(repr, args))} -> Referenz {soll[1] if soll[0] == 'ok' else soll}, Kandidat {ist[1] if ist[0] == 'ok' else ist}"[:300])
    return {"faelle": n, "abweichungen": abw}


def bericht(spec, arme, ergebnisse, paare):
    zeilen = [f"# A/B-Bau {spec}", "", f"Arme: {', '.join(arme)} | Paare: {paare} | {datetime.now():%Y-%m-%d %H:%M}", ""]
    if paare < 5:
        zeilen += [f"**Achtung:** nur {paare} Laeufe je Arm. Unterschiede sind ein Indiz, kein Beweis.", ""]
    zeilen += ["| Arm | n | alle Stufen bestanden | Dauer (Mittel) s | Aufrufe | Nacharbeiten | Prompt-Token | Abweichungen je Lauf | Laeufe ohne Abweichung |", "|---|---|---|---|---|---|---|---|---|"]
    for arm in arme:
        rs = [r for r in ergebnisse if r["arm"] == arm]
        if not rs:
            continue
        n = len(rs)
        mittel = lambda k: sum(r[k] for r in rs) / n  # noqa: E731
        ok = sum(1 for r in rs if r["bestanden"])
        dif = [r["diff"] for r in rs if r.get("diff")]
        abw = f"{sum(len(d['abweichungen']) for d in dif) / len(dif):.1f}" if dif else "-"
        rein = f"{sum(1 for d in dif if not d['abweichungen'])}/{len(dif)}" if dif else "-"
        zeilen.append(f"| {arm} | {n} | {ok}/{n} | {mittel('sekunden'):.0f} | {mittel('aufrufe'):.0f} | {mittel('nacharbeiten'):.1f} | {mittel('tokens_prompt'):.0f} | {abw} | {rein} |")
    zeilen += ["", "## Laeufe", ""]
    for r in ergebnisse:
        d = r.get("diff")
        zeilen.append(f"- {r['lauf']} ({r['arm']}): {'bestanden' if r['bestanden'] else 'NICHT bestanden'}, {r['sekunden']} s, Kandidat {r['kandidat']}"
                      + (f", Abweichungen {len(d['abweichungen'])}/{d['faelle']}" if d else ""))
        for a in (d["abweichungen"][:5] if d else []):
            zeilen.append(f"    - {a}")
    return "\n".join(zeilen) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("--paare", type=int, default=3)
    ap.add_argument("--arme", default="ohne,bau_coder:de")
    ap.add_argument("--projekt", default=str(projekt_standard()))
    ap.add_argument("--profil", default="standard")
    ap.add_argument("--rezept")
    ap.add_argument("--kontext", type=int)
    ap.add_argument("--start", action="store_true", help="wirklich starten (nur mit dem Ja des Captains)")
    a = ap.parse_args()
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,60}", a.spec) or not 1 <= a.paare <= 20:
        raise SystemExit("spec oder --paare ungueltig (1 bis 20)")
    arme, projekt = arme_lesen(a.arme), Path(a.projekt)
    print(f"Plan: {a.spec}, {a.paare} Paare, Arme {arme} -> {a.paare * len(arme)} Laeufe, Projekt {projekt}")
    probleme = vorpruefung(projekt, a.spec)
    for p in probleme:
        print("  VERBOTEN:", p)
    if probleme:
        return 2
    if not a.start:
        print("Vorpruefung ok. Nichts gestartet (ohne --start nur der Plan).")
        return 0
    ziel = projekt / "runtime_data" / "ab_bau" / f"{a.spec}_{datetime.now():%Y%m%d_%H%M%S}"
    ziel.mkdir(parents=True)
    ergebnisse = []
    for i in range(1, a.paare + 1):
        for arm in (arme if i % 2 else arme[::-1]):        # die Reihenfolge wechselt je Paar: kein Arm laeuft immer zuerst (Waerme, Cache)
            name = f"{i}_{arm.replace(':', '-')}"
            log = ziel / f"{name}.log"
            t0 = time.monotonic()
            with log.open("w", encoding="utf-8") as f:
                subprocess.run(befehl_fuer(projekt, a.spec, arm, ziel / f"{name}.pid", a.profil, a.rezept, a.kontext), cwd=str(RUNTIME), stdout=f, stderr=subprocess.STDOUT)
            text = log.read_text(encoding="utf-8", errors="replace")
            treffer = re.findall(r"-> (\S.*?attempt_\d+_\d+_\d+)", text)
            kandidat = str((RUNTIME / treffer[-1]).resolve()) if treffer else None
            k = kennzahlen(text)
            r = {"lauf": name, "arm": arm, "sekunden": round(time.monotonic() - t0), "kandidat": kandidat, "ende": "# run ended" in text,
                 "bestanden": k["stufen_gesamt"] > 0 and k["stufen_ok"] == k["stufen_gesamt"] and "# run ended" in text, **k}
            if kandidat:
                try:
                    r["diff"] = differenz(a.spec, kandidat)
                except Exception as e:  # noqa: BLE001
                    r["diff"] = {"faelle": 0, "abweichungen": [f"Differenztest nicht lauffaehig: {type(e).__name__}: {e}"]}
            ergebnisse.append(r)
            (ziel / "ergebnis.json").write_text(json.dumps(ergebnisse, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"  {name}: {'bestanden' if r['bestanden'] else 'NICHT bestanden'}, {r['sekunden']} s")
    (ziel / "bericht.md").write_text(bericht(a.spec, arme, ergebnisse, a.paare), encoding="utf-8")
    print(f"Bericht: {ziel / 'bericht.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
