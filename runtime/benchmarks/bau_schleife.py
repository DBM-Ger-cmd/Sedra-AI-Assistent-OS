"""Neuer Standard fuer den Bau: Stufe fuer Stufe, mit Schleife ueber Versuche.

Ablauf je Stufe (S1 bis S4 der Spec factory_sdk_grundlage_v5):
  1. Versuch: devvm_build --only <Stufe> --seed <Startstand> [--review <Fehlerbericht>] --coder <Modell>
     (Solo-Modus, Nacharbeiten mit Hidden-Test-Bericht laufen im Versuch selbst, siehe devvm_build.py)
  2. Erfolg (Zeile "stage <Stufe>: hidden PASSED"): naechste Stufe, Startstand = Kandidat dieses Versuchs.
  3. Fehlschlag durch den Modellkandidaten: Fehlerbericht aus der microVM (Lint und versteckter Test der Stufe,
     letzte Ausgaben), Vorlage Aufgabe / Was ist schiefgegangen / Was tun. Naechster Versuch baut auf dem
     gescheiterten Kandidaten weiter und bekommt den Bericht als --review.
  4. Infrastrukturfehler (Modellserver bricht ab, ConnectionResetError, SERVER CRASH): zaehlt NICHT als
     Versuch, wird bis INFRA_MAX mal wiederholt, danach Eskalation.
Modellfolge: MODELLE. Nach allen Versuchen eines Modells wird das naechste Modell verwendet.
Stopp: Erfolg der Stufe oder alle Versuche verbraucht (Eskalation an den Captain, Statusdatei).

Ordner: Der Bau-Projektordner (das Projekt, in dem devvm_build seine runtime_data anlegt) wird ueber
die Umgebungsvariable SEDRA_BAU_PROJEKT oder die Option --projekt angegeben. Pfade im Code sind relativ
zum Repo, keine festen Laufwerkspfade.

Aufruf (aus dem Ordner runtime):
  python benchmarks/bau_schleife.py --projekt <Projektordner> start
  python benchmarks/bau_schleife.py --projekt <Projektordner> bericht <kandidatenordner> [<stufe>]
"""
import importlib.util
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
BENCH = RUNTIME / "benchmarks"
PY = Path(sys.executable)
SPEC_NAME = "factory_sdk_grundlage_v5"
SPEC_FILE = BENCH / "devvm_specs" / f"{SPEC_NAME}.py"
STUFEN = ["S1", "S2", "S3", "S4"]
MODELLE = [("coder.local_primary", 2), ("qwen3coder", 2)]
INFRA_MAX = 3
INFRA_MUSTER = ("ConnectionResetError", "SERVER CRASH", "llama_server_not_found", "VM run failed")

VORLAGE = """FEHLERBERICHT (automatisch aus dem gescheiterten Versuch)

1. Aufgabe
{aufgabe}

2. Was ist schiefgegangen
Stufe {stufe}: der versteckte Test ist fehlgeschlagen. Ausgabe der Pruefung in der microVM:
{ausgabe}
Gescheiterter Versuch: {versuch}.

3. Was tun
- Behebe nur die Stelle, die der Test oben anzeigt. Die Teile, die schon bestehen, bleiben unveraendert.
- Die Regeln in NOTES.md sind die einzige Quelle: Felder, Werte und Fehlercodes genau so verwenden.
- Erfinde keine Felder und Namen, die dort nicht stehen.
- Die Stufe ist fertig, wenn der Test sie besteht.
"""


def projekt_pfad(angabe):
    wert = angabe or os.environ.get("SEDRA_BAU_PROJEKT")
    if not wert:
        raise SystemExit("Kein Bau-Projektordner: --projekt oder SEDRA_BAU_PROJEKT angeben.")
    return Path(wert)


def statusdatei(projekt):
    return projekt / "runtime_data" / "bau_schleife_status.log"


def log(projekt, text):
    zeile = f"{datetime.now():%Y-%m-%d %H:%M:%S} {text}"
    print(zeile, flush=True)
    pfad = statusdatei(projekt)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    with pfad.open("a", encoding="utf-8") as f:
        f.write(zeile + "\n")


def lade_spec():
    spec = importlib.util.spec_from_file_location("spec_v5", SPEC_FILE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fehlerbericht(projekt, kandidat, stufe, versuch, spec_mod):
    """Laeuft in der microVM (spec_check.run_in_vm); liefert den Berichtstext fuer die fehlgeschlagene Stufe."""
    sys.path.insert(0, str(BENCH))
    sys.path.insert(0, str(RUNTIME / "src"))
    import spec_check  # noqa: E402

    python, probleme, zeilen = spec_check.run_in_vm(str(projekt), kandidat, spec_mod)
    ausgabe = []
    for name, ok, tail in zeilen:
        if name == stufe and not ok:
            ausgabe.extend("   " + t for t in tail)
    if probleme:
        ausgabe.extend("   Lint: " + p for p in probleme)
    aufgabe = next(s["task"] for s in spec_mod.STAGES if s["name"] == stufe)
    return VORLAGE.format(aufgabe=aufgabe.strip(), stufe=stufe, ausgabe="\n".join(ausgabe) or "   (keine Ausgabe)",
                          versuch=versuch)


def bau_versuch(projekt, stufe, seed, bericht, modell):
    """Ein devvm_build-Lauf. Gibt (Erfolg, Kandidatenordner, Log-Pfad, Infrastrukturfehler) zurueck."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    lauf_log = projekt / "runtime_data" / f"bau_schleife_{stufe}_{modell}_{stamp}.log"
    befehl = [str(PY), "benchmarks/devvm_build.py", str(projekt), "--spec", SPEC_NAME, "--profile", "standard",
              "--coder", modell, "--only", stufe]
    if seed:
        befehl += ["--seed", str(seed)]
    if bericht:
        befehl += ["--review", str(bericht)]
    with lauf_log.open("w", encoding="utf-8") as f:
        subprocess.run(befehl, cwd=str(RUNTIME), stdout=f, stderr=subprocess.STDOUT)
    text = lauf_log.read_text(encoding="utf-8", errors="replace")
    erfolg = f"stage {stufe}: hidden PASSED" in text
    treffer = re.findall(r"-> (\S.*?attempt_\d+_\d+_\d+)", text)
    kandidat = (RUNTIME / treffer[-1]).resolve() if treffer else None      # relative Angaben gelten ab dem Repo-Ordner runtime
    infra = any(m in text for m in INFRA_MUSTER) and not erfolg
    return erfolg, kandidat, lauf_log, infra


def stufe_bauen(projekt, stufe, seed, spec_mod):
    """Gibt den Kandidaten der erfolgreichen Stufe zurueck, sonst None."""
    bericht = None
    infra_zaehler = 0
    for modell, anzahl in MODELLE:
        versuch_nr = 0
        while versuch_nr < anzahl:
            versuch = f"{modell} Versuch {versuch_nr + 1}"
            log(projekt, f"start {stufe} {versuch}")
            erfolg, kandidat, lauf_log, infra = bau_versuch(projekt, stufe, seed, bericht, modell)
            if erfolg:
                log(projekt, f"ERFOLG {stufe} {versuch}; Kandidat {kandidat}; Log {lauf_log}")
                return kandidat
            if infra:
                infra_zaehler += 1
                log(projekt, f"Infrastrukturfehler {stufe} {versuch} (nicht gezaehlt, {infra_zaehler}/{INFRA_MAX}); Log {lauf_log}")
                if infra_zaehler >= INFRA_MAX:
                    log(projekt, f"ESKALATION: Infrastruktur {INFRA_MAX}x gestoert bei {stufe}")
                    return None
                continue
            versuch_nr += 1
            log(projekt, f"fehlgeschlagen {versuch}; Log {lauf_log}")
            if kandidat and kandidat.is_dir():
                text = fehlerbericht(projekt, kandidat, stufe, versuch, spec_mod)
                bericht = projekt / "runtime_data" / f"fehlerbericht_{stufe}_{modell}_{versuch_nr}.txt"
                bericht.write_text(text, encoding="utf-8")
                seed = kandidat          # naechster Versuch baut auf dem gescheiterten Kandidaten weiter
                log(projekt, f"fehlerbericht {bericht}")
    log(projekt, f"ESKALATION: alle Versuche bei {stufe} verbraucht")
    return None


def schleife(projekt):
    spec_mod = lade_spec()
    seed = None                          # jede Stufe startet aus dem Stand der Vorstufe, S1 ohne Startstand
    for stufe in STUFEN:
        kandidat = stufe_bauen(projekt, stufe, seed, spec_mod)
        if kandidat is None:
            log(projekt, f"ende: Stufe {stufe} nicht bestanden, Stopp")
            return 1
        seed = kandidat
    log(projekt, "ende: alle Stufen S1 bis S4 bestanden")
    return 0


def main(argv):
    projekt_angabe = None
    if "--projekt" in argv:
        i = argv.index("--projekt")
        projekt_angabe = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    if not argv or argv[0] not in ("start", "bericht"):
        print(__doc__)
        return 0
    projekt = projekt_pfad(projekt_angabe)
    if argv[0] == "start":
        return schleife(projekt)
    if len(argv) < 2:
        raise SystemExit("bericht braucht den Kandidatenordner")
    stufe = argv[2] if len(argv) > 2 else "S2"
    print(fehlerbericht(projekt, Path(argv[1]), stufe, "Probe", lade_spec()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
