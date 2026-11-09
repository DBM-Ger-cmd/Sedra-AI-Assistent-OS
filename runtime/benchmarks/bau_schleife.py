"""Neuer Standard fuer den Bau: vollautomatisch, Stufe fuer Stufe, mit Schleife ueber Versuche.

Ablauf:
  0. Sperre: nur ein Lauf gleichzeitig (Sperrdatei runtime_data/bau_schleife.lock mit PID; eine tote PID wird uebernommen).
  1. Vorpruefung: Spec-Stempel (spec_check --vm) und GPU (nur Captain-Freigabe bei fremden Modellservern oder belegtem Speicher).
  2. Fortsetzen: Stand in runtime_data/bau_schleife_stand.json. Eine bestandene Stufe wird nicht noch einmal gebaut.
     --neu verwirft den Stand.
  3. Je Stufe (S1 bis S4) bis zu SAETZE Versuche (Modell plus Optionen). Versuch:
     devvm_build --only <Stufe> --seed <Startstand> [--review <Fehlerbericht>] --coder <Modell> <Optionen>
  4. Erfolg (Zeile "stage <Stufe>: hidden PASSED"): Stand speichern, naechste Stufe. Hat ein frueherer Versuch
     einen Fehler gehabt, werden die geaenderten Dateien automatisch in die Wissensdatenbank gelegt (Muster = Fingerabdruck).
  5. Fehlschlag durch den Kandidaten: Fehlerbericht aus der microVM mit Fingerabdruck, bekannter Loesung und
     Wissensdatenbank-Treffern. Wiederholt sich der Fingerabdruck, wechselt die Strategie. Dreimal gleich: Eskalation.
  6. Infrastrukturfehler zaehlen nicht als Versuch (bis INFRA_MAX). Vorlauf-Fehler brechen sofort ab.
  7. Nach S4: Regressionsprüfung (bestehende Testbereiche mit dem Kandidaten), dann Produktpruefung in der microVM
     und Produktbericht. Uebernahme nach runtime nur mit Freigabe des Captains.

Ordner: der Bau-Projektordner kommt aus --projekt oder SEDRA_BAU_PROJEKT. Keine festen Laufwerkspfade im Code.

Aufruf (aus dem Ordner runtime):
  python benchmarks/bau_schleife.py --projekt <Projektordner> start [<Auftrag>] [--neu]
  python benchmarks/bau_schleife.py --projekt <Projektordner> bericht <kandidatenordner> [<stufe>]
  python benchmarks/bau_schleife.py --projekt <Projektordner> wissen speichern|suchen ...
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
BENCH = RUNTIME / "benchmarks"
PY = Path(sys.executable)
SPEC_NAME = "factory_sdk_grundlage_v5"
SPEC_FILE = BENCH / "devvm_specs" / f"{SPEC_NAME}.py"
STUFEN = ["S1", "S2", "S3", "S4"]
INFRA_MAX = 3
GLEICHER_FEHLER_MAX = 3
GPU_BASIS_MAX_MIB = 3072                 # wie clear_leftovers: hoechstens 3 GiB belegt
REGRESSION_BEREICHE = ["workflow", "runtime"]
INFRA_MUSTER = ("ConnectionResetError", "SERVER CRASH", "llama_server_not_found", "VM run failed")
WISSEN_PROJEKT = RUNTIME.parent / "workspace" / "SEDRA_OS"      # die Wissensdatenbank, die auch die Harness nutzt
MAX_BERATER_DATEI = 20000                                        # Dateien ueber dieser Groesse gehen nicht an den Berater

# Parametersaetze in der Reihenfolge der Versuche. Die Optionen ueberschreiben nur ihren eigenen Wert.
SAETZE = [
    {"name": "standard", "coder": "coder.local_primary", "args": []},
    {"name": "standard, eigene Pruefung leicht", "coder": "coder.local_primary", "args": ["--self-check", "light"]},
    {"name": "qwen3coder", "coder": "qwen3coder", "args": []},
    {"name": "qwen3coder, eigene Pruefung leicht", "coder": "qwen3coder", "args": ["--self-check", "light"]},
]

VORLAGE = """FEHLERBERICHT (automatisch aus dem gescheiterten Versuch)

1. Aufgabe
{aufgabe}

2. Was ist schiefgegangen
Stufe {stufe}: der versteckte Test ist fehlgeschlagen. Ausgabe der Pruefung in der microVM:
{ausgabe}
Gescheiterter Versuch: {versuch}. Fehler-Fingerabdruck: {fingerabdruck}
{wiederholung}{bekannt}
3. Was tun
- Behebe nur die Stelle, die der Test oben anzeigt. Die Teile, die schon bestehen, bleiben unveraendert.
- Die Regeln in NOTES.md sind die einzige Quelle: Felder, Werte und Fehlercodes genau so verwenden.
- Erfinde keine Felder und Namen, die dort nicht stehen.
- Die Stufe ist fertig, wenn der Test sie besteht.

4. Aus der Wissensdatenbank (SEDRA, Treffer nach Bedeutung)
{wissen}"""


# --- Grundlagen -----------------------------------------------------------------------------------------------------

def projekt_pfad(angabe):
    wert = angabe or os.environ.get("SEDRA_BAU_PROJEKT")
    if not wert:
        raise SystemExit("Kein Bau-Projektordner: --projekt oder SEDRA_BAU_PROJEKT angeben.")
    return Path(wert)


def log(projekt, text):
    zeile = f"{datetime.now():%Y-%m-%d %H:%M:%S} {text}"
    print(zeile, flush=True)
    pfad = projekt / "runtime_data" / "bau_schleife_status.log"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    with pfad.open("a", encoding="utf-8") as f:
        f.write(zeile + "\n")


def lade_spec():
    spec = importlib.util.spec_from_file_location("spec_v5", SPEC_FILE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _lebt(pid):
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    return str(pid) in out


# --- 1. Einzelbetrieb -----------------------------------------------------------------------------------------------

def sperre_setzen(projekt):
    pfad = projekt / "runtime_data" / "bau_schleife.lock"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    if pfad.exists():
        alt = pfad.read_text(encoding="utf-8", errors="replace").strip()
        if alt.isdigit() and int(alt) != os.getpid() and _lebt(int(alt)):
            raise SystemExit(f"Ein anderer Bau-Lauf ist aktiv (PID {alt}). Nur ein Lauf gleichzeitig. Sperrdatei: {pfad}")
    pfad.write_text(str(os.getpid()), encoding="utf-8")
    return pfad


def sperre_loesen(pfad):
    try:
        if pfad.exists() and pfad.read_text(encoding="utf-8", errors="replace").strip() == str(os.getpid()):
            pfad.unlink()
    except OSError:
        pass


# --- 2. Stand zum Fortsetzen ------------------------------------------------------------------------------------------

def stand_datei(projekt):
    return projekt / "runtime_data" / "bau_schleife_stand.json"


def stand_lesen(projekt):
    pfad = stand_datei(projekt)
    if not pfad.exists():
        return {}
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    return daten if daten.get("spec") == SPEC_NAME and not daten.get("fertig") else {}


def stand_schreiben(projekt, stufen, fertig=False):
    pfad = stand_datei(projekt)
    pfad.write_text(json.dumps({"spec": SPEC_NAME, "stufen": stufen, "fertig": fertig}, ensure_ascii=False, indent=2), encoding="utf-8")


# --- 3. Vorpruefung: Stempel und GPU ----------------------------------------------------------------------------------

def gpu_und_modelle_pruefen(projekt):
    """Nur sauberer Start: kein laufender llama-server (der Bau wuerde ihn beenden) und freier Speicher auf der GPU."""
    sys.path.insert(0, str(BENCH))
    import prozess_pruefung as pp  # noqa: E402

    server = [p for p in pp.liste() if "llama-server" in (p.get("Name") or "").lower()]
    if server:
        pids = ", ".join(str(p["ProcessId"]) for p in server)
        log(projekt, f"Vorpruefung: llama-server laeuft (PID {pids}). Der Bau wuerde ihn beenden. Kein Start.")
        return False
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=30).stdout
        belegt = int(out.split()[0])
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        log(projekt, "Vorpruefung: GPU-Speicher nicht lesbar (nvidia-smi). Kein Start.")
        return False
    if belegt > GPU_BASIS_MAX_MIB:
        log(projekt, f"Vorpruefung: GPU belegt {belegt} MiB (Grenze {GPU_BASIS_MAX_MIB}). Kein Start.")
        return False
    log(projekt, f"Vorpruefung GPU: ohne Modellserver, {belegt} MiB belegt.")
    return True


def vorpruefung(projekt):
    lauf = subprocess.run([str(PY), "benchmarks/spec_check.py", SPEC_NAME, "--vm", "--project", str(projekt)],
                          cwd=str(RUNTIME), capture_output=True, encoding="utf-8", errors="replace")
    letzte = (lauf.stdout or "").strip().splitlines()[-1:] or ["(keine Ausgabe)"]
    log(projekt, f"vorpruefung spec_check --vm: Exit {lauf.returncode}; {letzte[0][:160]}")
    return lauf.returncode == 0 and gpu_und_modelle_pruefen(projekt)


# --- Bekannte Fehler und Wissensdatenbank -----------------------------------------------------------------------------

BEKANNTE_START = [
    {"muster": "MISSING_FIELD", "beschreibung": "Pflichtfeld fehlt: das Modell hat Felder erfunden oder ausgelassen.",
     "loesung": "Nur die Feldnamen aus NOTES.md verwenden; die Regelblaetter sind die einzige Quelle."},
    {"muster": "spec_changed_since_check", "beschreibung": "Spec-Stempel veraltet.",
     "loesung": "spec_check --vm fuer die Spec neu laufen lassen; die Schleife tut das bei jedem Start."},
    {"muster": "ConnectionResetError", "beschreibung": "Modellserver bricht ab (Infrastruktur, kein Modellfehler).",
     "loesung": "Versuch wiederholen; bei Haeufung Modellserver neu starten, Kontext senken."},
]


def bekannte_datei(projekt):
    return projekt / "runtime_data" / "bekannte_fehler.json"


def bekannte_fehler(projekt):
    pfad = bekannte_datei(projekt)
    if not pfad.exists():
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text(json.dumps(BEKANNTE_START, ensure_ascii=False, indent=2), encoding="utf-8")
    return json.loads(pfad.read_text(encoding="utf-8"))


def bekannte_loesung(projekt, fingerabdruck):
    for eintrag in bekannte_fehler(projekt):
        if eintrag["muster"] and eintrag["muster"] in fingerabdruck:
            text = f"Bekannter Fehler: {eintrag['beschreibung']} Bekannte Loesung: {eintrag['loesung']}"
            datei = eintrag.get("loesung_datei")
            if datei and (projekt / datei).is_file():
                code = (projekt / datei).read_text(encoding="utf-8", errors="replace")[:4000]
                text += f"\nGespeicherte, geprueft gute Loesung ({datei}):\n{code}"
            return text
    return ""


def merke_fehler(projekt, fingerabdruck, stufe):
    if not fingerabdruck or bekannte_loesung(projekt, fingerabdruck):
        return
    eintraege = bekannte_fehler(projekt)
    eintraege.append({"muster": fingerabdruck[:120], "beschreibung": f"neu, Stufe {stufe}: noch ohne Befund",
                      "loesung": "offen: Captain ergaenzt die Loesung"})
    bekannte_datei(projekt).write_text(json.dumps(eintraege, ensure_ascii=False, indent=2), encoding="utf-8")


def wissen_speichern(projekt, datei, muster, beschreibung, aufbewahren=None):
    """Legt eine Loesung unter runtime_data/bau_wissen ab und verknuepft sie mit einem Fehlermuster."""
    quelle = Path(datei)
    if not quelle.is_file():
        raise SystemExit(f"Datei nicht gefunden: {quelle}")
    ziel_ordner = projekt / "runtime_data" / "bau_wissen"
    ziel_ordner.mkdir(parents=True, exist_ok=True)
    name = f"{datetime.now():%Y%m%d_%H%M%S_%f}_{quelle.name}"
    (ziel_ordner / name).write_bytes(quelle.read_bytes())
    eintraege = bekannte_fehler(projekt)
    eintraege.append({"muster": muster, "beschreibung": beschreibung, "loesung": "siehe gespeicherte Datei",
                      "loesung_datei": f"runtime_data/bau_wissen/{name}"})
    bekannte_datei(projekt).write_text(json.dumps(eintraege, ensure_ascii=False, indent=2), encoding="utf-8")
    return name


def merke_loesung(projekt, fehlkandidat, erfolgskandidat, muster, stufe):
    """Automatisch: die Dateien, die der erfolgreiche Versuch gegenueber dem gescheiterten geaendert hat, in die Wissensdatenbank."""
    gemerkt = []
    for datei in sorted(erfolgskandidat.rglob("*.py")):
        rel = datei.relative_to(erfolgskandidat)
        alt = fehlkandidat / rel
        if alt.is_file() and alt.read_bytes() == datei.read_bytes():
            continue
        if datei.stat().st_size > 20000:
            continue
        gemerkt.append(wissen_speichern(projekt, datei, muster, f"Automatisch gemerkt: Stufe {stufe}, Datei {rel.as_posix()}"))
    if gemerkt:
        log(projekt, f"Loesung gemerkt fuer '{muster[:60]}': {len(gemerkt)} Datei(en)")
    return gemerkt


def wissen_treffer(projekt, frage, k=3):
    """Sucht in der Wissensdatenbank von SEDRA (dieselbe Suche wie die Harness, Leser 'captain').
    Nicht erreichbar: der Grund steht im Bericht, der Bau laeuft weiter."""
    try:
        sys.path.insert(0, str(RUNTIME / "src"))
        from sedra_runtime.wissen import konfig as wkonfig
        from sedra_runtime.wissen.speicher import WissenSpeicher, leser
        from sedra_runtime.wissen.embed import TestLabZugang, VerzoegertesLabor
        from sedra_runtime.jobs.testlab import TestLab, default_path
        cfg = wkonfig.load(RUNTIME / "config" / "wissen.yaml", projekt / "local_config" / "wissen.yaml")
        sp = WissenSpeicher.oeffnen(cfg, projekt_root=projekt, repo_root=RUNTIME.parent, audit=lambda e, p: None,
                                    gpu=TestLabZugang(VerzoegertesLabor(default_path(projekt), TestLab)))
        try:
            erg = sp.suche(frage[:400], leser=leser("captain", 6, None), k=k, protokoll=False)
        finally:
            sp.schliessen()
    except Exception as exc:
        return f"(Wissensdatenbank nicht erreichbar: {type(exc).__name__}: {str(exc)[:160]})"
    treffer = erg.get("treffer") or []
    if not treffer:
        return f"(keine Treffer, Modus {erg.get('modus')})"
    zeilen = [f"- {t['datei']} ({t.get('stelle') or '-'}): {str(t['text'])[:400].strip()}" for t in treffer]
    return "\n".join(zeilen) + (f"\n(Hinweis: {erg['hinweis']})" if erg.get("hinweis") else "")


def wissen_suchen(projekt, text):
    treffer = []
    for eintrag in bekannte_fehler(projekt):
        feld = " ".join(str(eintrag.get(k, "")) for k in ("muster", "beschreibung", "loesung", "loesung_datei")).lower()
        if text.lower() in feld:
            treffer.append(eintrag)
    return treffer


# --- 4. Fingerabdruck und Fehlerbericht ----------------------------------------------------------------------------------

def fingerabdruck_aus(ausgabe):
    for zeile in ausgabe:
        z = zeile.strip()
        if re.search(r"(Error|FabrikFehler|AssertionError|Lint:)", z):
            return re.sub(r"line \d+|0x[0-9a-fA-F]+|\d{5,}", "N", z)[:160]
    return next((z.strip() for z in ausgabe if z.strip()), "")[:160]


def fehlerbericht(projekt, kandidat, stufe, versuch, spec_mod, vorige_fingerabdruecke):
    """Laeuft in der microVM (spec_check.run_in_vm). Liefert (Berichtstext, Fingerabdruck)."""
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
    roh = [z.strip() for z in ausgabe]
    fp = fingerabdruck_aus(roh) if roh else ""
    loesung = bekannte_loesung(projekt, fp)
    wiederholt = bool(fp) and vorige_fingerabdruecke.count(fp) >= 1
    wiederholung = ("Derselbe Fehler wie im Versuch davor: die Strategie wechselt (anderes Modell oder andere Optionen).\n"
                    if wiederholt else "")
    aufgabe = next(s["task"] for s in spec_mod.STAGES if s["name"] == stufe)
    wissen = wissen_treffer(WISSEN_PROJEKT, f"{aufgabe.strip()[:200]} {fp}")
    text = VORLAGE.format(aufgabe=aufgabe.strip(), stufe=stufe, ausgabe="\n".join(ausgabe) or "   (keine Ausgabe)",
                          versuch=versuch, fingerabdruck=fp or "(keiner)", wiederholung=wiederholung,
                          bekannt=(loesung + "\n") if loesung else "", wissen=wissen)
    merke_fehler(projekt, fp, stufe)
    return text, fp


# --- 5. Versuche je Stufe -----------------------------------------------------------------------------------------------

def bau_versuch(projekt, stufe, seed, bericht, satz):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    lauf_log = projekt / "runtime_data" / f"bau_schleife_{stufe}_{satz['coder']}_{stamp}.log"
    befehl = [str(PY), "benchmarks/devvm_build.py", str(projekt), "--spec", SPEC_NAME, "--profile", "standard",
              "--coder", satz["coder"], "--only", stufe] + satz["args"]
    if seed:
        befehl += ["--seed", str(seed)]
    if bericht:
        befehl += ["--review", str(bericht)]
    with lauf_log.open("w", encoding="utf-8") as f:
        subprocess.run(befehl, cwd=str(RUNTIME), stdout=f, stderr=subprocess.STDOUT)
    text = lauf_log.read_text(encoding="utf-8", errors="replace")
    erfolg = f"stage {stufe}: hidden PASSED" in text
    treffer = re.findall(r"-> (\S.*?attempt_\d+_\d+_\d+)", text)
    kandidat = (RUNTIME / treffer[-1]).resolve() if treffer else None
    infra = any(m in text for m in INFRA_MUSTER) and not erfolg
    return erfolg, kandidat, lauf_log, infra


def berater_versuch(projekt, stufe, kandidat, fehlerbericht_text, spec_mod):
    """Ein Versuch mit dem Berater (Cloud, nur Text). Gibt den neuen Kandidaten zurueck, wenn die Stufe in der microVM besteht.
    Ist der Berater nicht eingerichtet, passiert nichts. Er zaehlt nicht als Modellversuch."""
    sys.path.insert(0, str(BENCH))
    import berater  # noqa: E402

    ok, grund = berater.berater_status()
    if not ok:
        log(projekt, f"Berater aus ({grund})")
        return None
    dateien = {}
    for datei in sorted((kandidat / "factory_sdk").rglob("*.py")):
        if datei.stat().st_size <= MAX_BERATER_DATEI:
            dateien[datei.relative_to(kandidat).as_posix()] = datei.read_text(encoding="utf-8", errors="replace")
    try:
        neu = berater.berater_fragen(fehlerbericht_text, dateien)
    except (ValueError, Exception) as exc:      # Netz, Schluessel, Antwortform: der Bau laeuft weiter
        log(projekt, f"Berater-Versuch {stufe} nicht ausgefuehrt: {type(exc).__name__}: {str(exc)[:160]}")
        return None
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ziel = projekt / "runtime_data" / "devvm_candidates" / SPEC_NAME / f"berater_{stufe}_{stamp}"
    shutil.copytree(kandidat, ziel, dirs_exist_ok=True)
    for pfad, inhalt in neu.items():
        if not pfad.startswith("factory_sdk/"):
            continue
        zieldatei = ziel / pfad
        zieldatei.parent.mkdir(parents=True, exist_ok=True)
        zieldatei.write_text(inhalt, encoding="utf-8")
    import spec_check  # noqa: E402
    _python, probleme, zeilen = spec_check.run_in_vm(str(projekt), ziel, spec_mod)
    bestanden = any(name == stufe and passed for name, passed, _ in zeilen)
    log(projekt, f"Berater-Versuch {stufe}: {'bestanden' if bestanden else 'nicht bestanden'}; Kandidat {ziel}")
    return ziel if bestanden else None


def stufe_bauen(projekt, stufe, seed, spec_mod):
    """Gibt den Kandidaten der erfolgreichen Stufe zurueck, sonst None."""
    bericht = None
    infra_zaehler = 0
    fingerabdruecke = []
    letzter_fehler = None      # (fingerabdruck, gescheiterter Kandidat) fuer das automatische Merken
    for nr, satz in enumerate(SAETZE, 1):
        log(projekt, f"start {stufe} Versuch {nr}/{len(SAETZE)}: {satz['name']} ({satz['coder']})")
        erfolg, kandidat, lauf_log, infra = bau_versuch(projekt, stufe, seed, bericht, satz)
        if erfolg:
            log(projekt, f"ERFOLG {stufe} Versuch {nr}; Kandidat {kandidat}; Log {lauf_log}")
            if letzter_fehler and kandidat:
                merke_loesung(projekt, letzter_fehler[1], kandidat, letzter_fehler[0], stufe)
            return kandidat
        if infra:
            infra_zaehler += 1
            log(projekt, f"Infrastrukturfehler {stufe} Versuch {nr} (nicht gezaehlt, {infra_zaehler}/{INFRA_MAX}); Log {lauf_log}")
            if infra_zaehler >= INFRA_MAX:
                log(projekt, f"ESKALATION: Infrastruktur {INFRA_MAX}x gestoert bei {stufe}")
                return None
            continue
        if kandidat is None:
            erste = next((z.strip() for z in lauf_log.read_text(encoding="utf-8", errors="replace").splitlines() if z.strip()), "leeres Log")
            log(projekt, f"ESKALATION: Vorlauf-Fehler bei {stufe}, kein Versuch gelaufen: {erste[:200]}")
            return None
        log(projekt, f"fehlgeschlagen {stufe} Versuch {nr}; Log {lauf_log}")
        if kandidat.is_dir():
            text, fp = fehlerbericht(projekt, kandidat, stufe, f"{nr} ({satz['name']})", spec_mod, fingerabdruecke)
            fingerabdruecke.append(fp)
            if fp:
                letzter_fehler = (fp, kandidat)
            if fingerabdruecke.count(fp) >= GLEICHER_FEHLER_MAX:
                log(projekt, f"ESKALATION: gleicher Fehler {GLEICHER_FEHLER_MAX}x bei {stufe}: {fp}")
                return None
            bericht = projekt / "runtime_data" / f"fehlerbericht_{stufe}_{nr}.txt"
            bericht.write_text(text, encoding="utf-8")
            seed = kandidat          # naechster Versuch baut auf dem gescheiterten Kandidaten weiter
            log(projekt, f"fehlerbericht {bericht}; Fingerabdruck: {fp or '(keiner)'}")
            ergebnis = berater_versuch(projekt, stufe, kandidat, text, spec_mod)
            if ergebnis:
                merke_loesung(projekt, kandidat, ergebnis, fp or stufe, stufe)
                return ergebnis
    log(projekt, f"ESKALATION: alle {len(SAETZE)} Parametersaetze bei {stufe} verbraucht")
    return None


# --- 6. Regression und Produktpruefung ------------------------------------------------------------------------------------

def regression(projekt, kandidat):
    """Die bestehenden Testbereiche von SEDRA laufen mit dem Kandidaten (in einer Kopie der Runtime, das Repo bleibt unberuehrt)."""
    kopie = Path(tempfile.mkdtemp(prefix="regression_"))
    try:
        ziel = kopie / "runtime"
        shutil.copytree(RUNTIME, ziel, ignore=shutil.ignore_patterns(".venv", "__pycache__", "runtime_data", ".pytest_cache"))
        pakets = ziel / "src" / "factory_sdk"
        if pakets.exists():
            shutil.rmtree(pakets)
        shutil.copytree(kandidat / "factory_sdk", pakets)
        lauf = subprocess.run([str(PY), "benchmarks/run_tests.py", *REGRESSION_BEREICHE], cwd=str(ziel),
                              capture_output=True, encoding="utf-8", errors="replace", timeout=3600)
        ende = (lauf.stdout or "").strip().splitlines()[-3:]
        return lauf.returncode == 0, ende
    except (OSError, subprocess.SubprocessError) as exc:
        return False, [f"Regressionsprüfung nicht lauffähig: {type(exc).__name__}: {str(exc)[:160]}"]
    finally:
        shutil.rmtree(kopie, ignore_errors=True)


def produkt_pruefen(projekt, kandidat, spec_mod, auftrag):
    sys.path.insert(0, str(BENCH))
    sys.path.insert(0, str(RUNTIME / "src"))
    import spec_check  # noqa: E402

    python, probleme, zeilen = spec_check.run_in_vm(str(projekt), kandidat, spec_mod)
    alle_ok = bool(zeilen) and not probleme and all(ok for _, ok, _ in zeilen) and len(zeilen) == len(STUFEN)
    reg_ok, reg_ende = regression(projekt, kandidat)
    log(projekt, f"Regressionsprüfung {REGRESSION_BEREICHE}: {'ok' if reg_ok else 'NICHT ok'}")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bericht = projekt / "runtime_data" / f"produktbericht_{stamp}.md"
    gesamt = alle_ok and reg_ok
    text = "\n".join([
        "# Produktbericht Factory-Bau",
        "",
        f"Auftrag: {auftrag}",
        f"Spec: {SPEC_NAME}",
        f"Python in der microVM: {python or 'unbekannt'}",
        f"Lint: {'ohne Befund' if not probleme else 'Befunde: ' + '; '.join(probleme)}",
        "Stufen in der microVM:",
        *[f"- {name}: {'bestanden' if ok else 'NICHT bestanden'}" for name, ok, _ in zeilen],
        f"Regressionsprüfung ({', '.join(REGRESSION_BEREICHE)}): {'ok' if reg_ok else 'NICHT ok'}",
        *[f"  {z}" for z in reg_ende],
        f"Kandidat: {kandidat}",
        "",
        "Ergebnis: " + ("ALLE PRUEFUNGEN BESTANDEN" if gesamt else "NICHT BESTANDEN"),
        "",
        "Nächster Schritt: Der Captain prüft das Produkt. Übernahme in runtime nur mit ausdrücklicher Freigabe im Chat.",
        "",
    ])
    bericht.write_text(text, encoding="utf-8")
    log(projekt, f"produktbericht {bericht} ({'ok' if gesamt else 'nicht bestanden'})")
    return bericht, gesamt


def manager_erlaubt_bau(projekt):
    """Schritt 2 der Manager-Verfassung: jeder Bau-Start geht durch den Manager. Ohne Recht 'bau_starten' startet nichts."""
    sys.path.insert(0, str(RUNTIME / "src"))
    from sedra_runtime.manager import Manager, VerfassungsVerstoss
    manager = Manager("bau-schleife", set(), journal=projekt / "runtime_data" / "manager" / "journal.jsonl")
    try:
        manager.nutze_werkzeug("bau_starten")
    except VerfassungsVerstoss as exc:
        log(projekt, f"Bau-Start verweigert durch den Manager: {exc}")
        return False
    return True


def schleife(projekt, auftrag="(nicht angegeben)", neu=False):
    if not manager_erlaubt_bau(projekt):
        return 1
    sperre = sperre_setzen(projekt)
    try:
        if not vorpruefung(projekt):
            log(projekt, "ESKALATION: Vorpruefung fehlgeschlagen, kein Bau gestartet")
            return 1
        spec_mod = lade_spec()
        stand = {} if neu else stand_lesen(projekt)
        stufen_stand = dict(stand.get("stufen", {}))
        if stufen_stand:
            log(projekt, f"Fortsetzen: bestanden {', '.join(stufen_stand)}")
        seed = None
        kandidat = None
        for stufe in STUFEN:
            if stufe in stufen_stand:
                seed = Path(stufen_stand[stufe])
                continue
            kandidat = stufe_bauen(projekt, stufe, seed, spec_mod)
            if kandidat is None:
                log(projekt, f"ende: Stufe {stufe} nicht bestanden, Stopp (Stand bleibt zum Fortsetzen erhalten)")
                return 1
            stufen_stand[stufe] = str(kandidat)
            stand_schreiben(projekt, stufen_stand)
            seed = kandidat
        log(projekt, "alle Stufen S1 bis S4 bestanden, Regressionsprüfung und Produktprüfung starten")
        bericht, ok = produkt_pruefen(projekt, seed, spec_mod, auftrag)
        stand_schreiben(projekt, stufen_stand, fertig=True)
        log(projekt, f"ende: Produktprüfung {'ok' if ok else 'nicht bestanden'}; Bericht {bericht}")
        return 0 if ok else 1
    finally:
        sperre_loesen(sperre)


def main(argv):
    projekt_angabe = None
    if "--projekt" in argv:
        i = argv.index("--projekt")
        projekt_angabe = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    neu = "--neu" in argv
    argv = [a for a in argv if a != "--neu"]
    if not argv or argv[0] not in ("start", "bericht", "wissen"):
        print(__doc__)
        return 0
    projekt = projekt_pfad(projekt_angabe)
    if argv[0] == "wissen":
        if len(argv) >= 5 and argv[1] == "speichern":
            print("gespeichert:", wissen_speichern(projekt, argv[2], argv[3], argv[4]))
        elif len(argv) >= 3 and argv[1] == "suchen":
            for e in wissen_suchen(projekt, argv[2]):
                print(f"- {e['muster']} | {e['beschreibung']} | {e.get('loesung_datei', e['loesung'])}")
        else:
            print("Aufruf: wissen speichern <datei> <fehlermuster> <beschreibung> | wissen suchen <text>")
        return 0
    if argv[0] == "start":
        auftrag = argv[1] if len(argv) > 1 else "(nicht angegeben)"
        return schleife(projekt, auftrag, neu)
    if len(argv) < 2:
        raise SystemExit("bericht braucht den Kandidatenordner")
    stufe = argv[2] if len(argv) > 2 else "S2"
    text, _ = fehlerbericht(projekt, Path(argv[1]), stufe, "Probe", lade_spec(), [])
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
