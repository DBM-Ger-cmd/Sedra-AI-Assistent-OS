"""Minimalpaket fuer den USB-Stick (K:\\SEDRA): Liste lesen, Python-Importhuelle ermitteln, kopieren, Manifest schreiben.

Keine Verknuepfungen (exFAT kennt keine Junctions und Symlinks): jede Quelle wird als echte Datei oder echter Ordner kopiert.
Die Liste steht in `stick_liste.txt` neben diesem Skript. Zeilen:
    repo <pfad>        aus diesem Repository (Ordner mit / am Ende)
    bestand <pfad>     aus dem Hauptcheckout (nicht in git: Engine, portables Python)
    modul <name>       ein Python-Modul mit allen statischen Importen (sedra_runtime.*)
    profil <art>       (SPEC_STICK_AUS_PROFIL_v1 ST-01) alle Werkzeuge, deren tool.yaml `profile:` die Art nennt, dazu alle Werkzeuge mit `grundfunktion:` und die Instrumente
                       der Taskleiste (leiste.json) – je Werkzeug der ganze Ordner uix/tools/<id>/. `--pruefen` meldet vorher, was fehlt (ST-04).
    shell <id>         (SPEC_APPS_v1_AM8 AM8-11) der Ordner der Shell samt ihren Apps (Grundfunktionen, `slot:`, Start-Gruppen, Taskleiste) und allem, was die Manifeste unter `needs` nennen
    app <id>           (AM8-11) der Ordner des Werkzeugs samt `needs.apps` (rekursiv), `needs.kern` (Kern-Pakete) und `needs.dateien` (Dateien oder Ordner unter uix/)
    <quelle> <pfad> -> <ziel>   umbenannt kopieren
Aufruf (Bau-PC):  python -I -B runtime/benchmarks/stick_paket.py --repo <worktree> --bestand <hauptcheckout> --ziel K:\\SEDRA
Nur pruefen:      ... --pruefen        (fehlende Importe und fehlende Dateien melden, nichts kopieren)
Gegenprobe:       ... --gegenprobe     (AM8-12: was die Zeilen `repo` der Liste haben, die Ableitung aus den Manifesten aber nicht; nur Befund, nichts wird angeglichen)
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

PAKET = "sedra_runtime"
AUSSCHLUSS = {"__pycache__", ".pytest_cache", "local_paths.yaml", "local_config", ".git"}
SCHREIBEN = {"STICK_MANIFEST.json"}
HERE = Path(__file__).resolve().parent


def liste(pfad):
    """Zeilen der Liste als (art, quelle, ziel) mit art in repo|bestand|modul; Leerzeilen und # werden ausgelassen."""
    eintraege = []
    for nr, zeile in enumerate(Path(pfad).read_text(encoding="utf-8").splitlines(), 1):
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#"):
            continue
        teile = zeile.split()
        if teile[0] == "modul":
            eintraege.append(("modul", teile[1], teile[1]))
        elif teile[0] in ("profil", "shell", "app") and len(teile) == 2:
            eintraege.append((teile[0], teile[1], teile[1]))
        elif teile[0] in ("repo", "bestand") and len(teile) in (2, 4):
            ziel = teile[3] if len(teile) == 4 and teile[2] == "->" else teile[1]
            eintraege.append((teile[0], teile[1], ziel))
        else:
            raise ValueError(f"stick_liste.txt Zeile {nr}: {zeile!r}")
    return eintraege


def modul_datei(src, name):
    """Datei eines Moduls im Paket (name.py oder name/__init__.py), sonst None."""
    teile = name.split(".")
    datei = Path(src, *teile).with_suffix(".py")
    if datei.is_file():
        return datei
    paket = Path(src, *teile, "__init__.py")
    return paket if paket.is_file() else None


def closure(src, einstiegs):
    """Alle Dateien, die die Einstiegsmodule (und ihre Eltern-Pakete) brauchen. `src` enthaelt den Ordner sedra_runtime."""
    src = Path(src)
    bekannt, offen, dateien = set(), list(einstiegs), set()
    while offen:
        name = offen.pop()
        if name in bekannt:
            continue
        bekannt.add(name)
        teile = name.split(".")
        for n in range(1, len(teile)):
            init = Path(src, *teile[:n], "__init__.py")
            if init.is_file():
                dateien.add(init)
        datei = modul_datei(src, name)
        if datei is None:
            raise FileNotFoundError(f"Modul fehlt im Quellbaum: {name}")
        dateien.add(datei)
        offen.extend(_import_namen(datei, name, src) - bekannt)
    return sorted(dateien)


def _import_namen(datei, name, src):
    baum = ast.parse(datei.read_text(encoding="utf-8"), filename=str(datei))
    paket = name if datei.name == "__init__.py" else name.rsplit(".", 1)[0]
    namen = set()
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Import):
            namen.update(a.name for a in knoten.names if a.name.split(".")[0] == PAKET)
        elif isinstance(knoten, ast.ImportFrom):
            if knoten.level:
                basis = paket.split(".")[: len(paket.split(".")) - (knoten.level - 1)]
                ziel = ".".join(basis + ([knoten.module] if knoten.module else []))
            else:
                ziel = knoten.module or ""
            if ziel.split(".")[0] != PAKET:
                continue
            namen.add(ziel)
            namen.update(f"{ziel}.{a.name}" for a in knoten.names)
    return {n for n in namen if modul_datei(src, n) is not None}


def _kopierbar(pfad):
    return not any(teil in AUSSCHLUSS for teil in pfad.parts) and not pfad.name.endswith(".pyc")


def _ist_verknuepfung(pfad):
    return pfad.is_symlink() or getattr(pfad, "is_junction", lambda: False)()


def _sammeln(quelle_wurzel, rel):
    """Dateien unter quelle_wurzel/rel; ein Ordner nimmt alle echten Dateien (ohne Ausschluss), Verknuepfungen brechen ab."""
    ziel = Path(quelle_wurzel, rel)
    if not ziel.exists():
        raise FileNotFoundError(f"fehlt: {ziel}")
    if ziel.is_file():
        return [ziel]
    ausgabe = []
    for pfad in sorted(ziel.rglob("*")):
        if _ist_verknuepfung(pfad):
            raise RuntimeError(f"Verknuepfung im Paket nicht erlaubt: {pfad}")
        if pfad.is_file() and _kopierbar(pfad.relative_to(quelle_wurzel)):
            ausgabe.append(pfad)
    return ausgabe


TOOLS = Path("runtime", "src", PAKET, "uix", "tools")
LEISTE = Path("runtime", "src", PAKET, "uix", "shells", "harness", "leiste.json")


def werkzeug_manifeste(repo):
    """{id: tool-Block} aller Paket-Werkzeuge (uix/tools/<id>/tool.yaml); ein nicht lesbares steht mit leerem Block da."""
    erg = {}
    for ordner in sorted(Path(repo, TOOLS).glob("*")):
        datei = ordner / "tool.yaml"
        if not datei.is_file() or ordner.name.startswith("_"):
            continue
        try:
            erg[ordner.name] = (yaml.safe_load(datei.read_text(encoding="utf-8")) or {}).get("tool") or {}
        except (yaml.YAMLError, OSError, UnicodeDecodeError):
            erg[ordner.name] = {}
    return erg


def taskleisten_zellen(repo):
    try:
        return [z for z in json.loads(Path(repo, LEISTE).read_text(encoding="utf-8")).get("zellen", []) if isinstance(z, str)]
    except (OSError, ValueError):
        return []


def profil_werkzeuge(repo, art):
    """ST-01: {id: Grund} der Werkzeuge des Profils – `profile` nennt die Art, Grundfunktionen, Instrumente der Taskleiste. Die Instrumente stehen auch dann da, wenn ihr Ordner fehlt (dann meldet `--pruefen` es)."""
    erg = {}
    for tid, man in werkzeug_manifeste(repo).items():
        if art in (man.get("profile") or []):
            erg[tid] = f"profile: [{art}]"
        elif man.get("grundfunktion"):
            erg[tid] = "Grundfunktion " + str(man["grundfunktion"])
    for zelle in taskleisten_zellen(repo):
        erg.setdefault(zelle, "Zelle der Taskleiste")
    return erg


def pruefen_vollstaendig(repo, art, paare):
    """ST-04: was dem Profil fehlt, als Zeilen „fehlt: …“ (leer = vollständig): (a) ein Werkzeug des Profils ohne Ordner oder ohne seine `needs.apps`, (b) eine Zelle der Taskleiste ohne `gauge-*`-Ordner,
    (c) eine Grundfunktion ohne Werkzeug im Plan."""
    fehlt = []
    manifeste = werkzeug_manifeste(repo)
    gewaehlt = profil_werkzeuge(repo, art)
    im_plan = {Path(k).parts[len(TOOLS.parts)] for k in paare if Path(k).parts[:len(TOOLS.parts)] == TOOLS.parts and len(Path(k).parts) > len(TOOLS.parts)}
    for tid, grund in sorted(gewaehlt.items()):
        if tid not in manifeste:
            fehlt.append(f"fehlt: Werkzeug {tid} ({grund}) – kein Ordner uix/tools/{tid}/")
        elif tid not in im_plan:
            fehlt.append(f"fehlt: Werkzeug {tid} ({grund}) steht nicht im Plan")
        for dep in ((manifeste.get(tid) or {}).get("needs") or {}).get("apps", {}) or {}:
            if dep not in im_plan:
                fehlt.append(f"fehlt: {dep} (braucht {tid})")
    for tid, man in manifeste.items():
        if man.get("grundfunktion") and tid not in im_plan:
            fehlt.append(f"fehlt: Werkzeug {tid} der Grundfunktion {man['grundfunktion']}")
    return sorted(set(fehlt))


SRC = Path("runtime", "src", PAKET)
UIX = SRC / "uix"
SHELLS = UIX / "shells"


def _ordner(pfad):
    return Path(pfad).as_posix().rstrip("/") + "/"


def _yaml_block(datei, schluessel):
    try:
        return (yaml.safe_load(Path(datei).read_text(encoding="utf-8")) or {}).get(schluessel) or {}
    except (yaml.YAMLError, OSError, UnicodeDecodeError):
        return {}


def _json(datei):
    try:
        daten = json.loads(Path(datei).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return daten if isinstance(daten, dict) else {}


def _needs(man):
    n = man.get("needs") if isinstance(man, dict) else None
    return n if isinstance(n, dict) else {}


def ableitung(repo, art, ident):
    """AM8-11: {repo-relativer Pfad: Grund} fuer `app <id>` oder `shell <id>` aus den Manifesten. Ein Pfad ohne Ordner steht trotzdem drin (dann meldet `--pruefen` ihn).
    App: Ordner, `needs.apps` rekursiv, `needs.kern` -> Kern-Paket, `needs.dateien` -> Datei oder Ordner unter uix/.
    Shell: Ordner, Apps aus `grundfunktionen: slot:<id>`, den Start-Gruppen und der Taskleiste der Shell, Werkzeuge mit `grundfunktion:`, dazu die `needs` der Shell."""
    erg, offen, gesehen = {}, [(art, ident, f"Zeile {art} {ident}")], set()
    manifeste = werkzeug_manifeste(repo)
    while offen:
        a, i, grund = offen.pop()
        if (a, i) in gesehen:
            continue
        gesehen.add((a, i))
        if a == "app":
            erg.setdefault(_ordner(TOOLS / i), grund)
            man = manifeste.get(i) or {}
        else:
            erg.setdefault(_ordner(SHELLS / i), grund)
            man = _yaml_block(Path(repo, SHELLS, i, "shell.yaml"), "shell")
            for wert in (man.get("grundfunktionen") or {}).values():
                if isinstance(wert, str) and wert.startswith("slot:"):
                    offen.append(("app", wert[5:], f"Grundfunktion der Shell {i}"))
            for tid, tman in manifeste.items():
                if tman.get("grundfunktion"):
                    offen.append(("app", tid, "Grundfunktion " + str(tman["grundfunktion"])))
            for tid in sorted(_json(Path(repo, SHELLS, i, "start_gruppen.json")).get("zuordnung") or {}):
                if tid in manifeste:
                    offen.append(("app", tid, f"Start-Gruppe der Shell {i}"))
            for zelle in _json(Path(repo, SHELLS, i, "leiste.json")).get("zellen") or []:
                if isinstance(zelle, str):
                    offen.append(("app", zelle, f"Taskleiste der Shell {i}"))
        n = _needs(man)
        for dep in n["apps"] if isinstance(n.get("apps"), dict) else []:
            offen.append(("app", dep, f"needs.apps von {i}"))
        for k in n.get("kern") or []:
            if isinstance(k, str):
                erg.setdefault(_ordner(SRC / k), f"needs.kern von {i}")
        for d in n.get("dateien") or []:
            if isinstance(d, str):
                pfad = (UIX / d).as_posix()
                erg.setdefault(_ordner(pfad) if d.endswith("/") else pfad, f"needs.dateien von {i}")
    return erg


def _ableitungen(repo, eintraege):
    erg = {}
    for art, ident, _ in eintraege:
        if art in ("shell", "app"):
            for pfad, grund in ableitung(repo, art, ident).items():
                erg.setdefault(pfad, grund)
    return erg


def pruefen_ableitung(repo, eintraege):
    """AM8-11: Zeilen „fehlt: …“ fuer jeden abgeleiteten Pfad, den es im Repository nicht gibt (leer = vollstaendig)."""
    return sorted(f"fehlt: {pfad} ({grund})" for pfad, grund in _ableitungen(repo, eintraege).items() if not Path(repo, pfad).exists())


def gegenprobe(repo, eintraege):
    """AM8-12: Zeilen `repo` der Liste (Werkzeuge, Shells, Kern-Pakete, uix-Ordner), die die Ableitung aus den Manifesten NICHT deckt, als Befund „nur in der Liste: …“.
    Ohne Zeilen `shell`/`app` in der Liste gilt `shell harness` (der Stick ist die Harness). Nichts wird angeglichen."""
    ziele = [e for e in eintraege if e[0] in ("shell", "app")] or [("shell", "harness", "harness")]
    abgeleitet = [_ordner(p) if p.endswith("/") else p for p in _ableitungen(repo, ziele)]
    praefixe = (TOOLS.as_posix() + "/", SHELLS.as_posix() + "/")
    heutige = []
    for art, pfad, _ in eintraege:
        rel = Path(pfad).as_posix()
        if art != "repo":
            continue
        if rel.startswith(praefixe) or (rel.startswith(SRC.as_posix() + "/") and pfad.endswith("/")):
            heutige.append(rel.rstrip("/") + "/")

    def gedeckt(rel):
        return any(rel == a or rel.startswith(a) for a in abgeleitet)
    return sorted(f"nur in der Liste: {rel}" for rel in heutige if not gedeckt(rel))


def profil_info(eintraege, repo):
    """{art, apps: [ids], grundfunktionen: [namen]} für das Manifest (ST-05); leer, wenn die Liste keine Zeile `profil` hat."""
    arten = [e[1] for e in eintraege if e[0] == "profil"]
    if not arten:
        return None
    art = arten[0]
    manifeste = werkzeug_manifeste(repo)
    gewaehlt = profil_werkzeuge(repo, art)
    return {"art": art, "apps": sorted(gewaehlt), "grundfunktionen": sorted({str(m["grundfunktion"]) for m in manifeste.values() if m.get("grundfunktion")})}


def plan(eintraege, repo, bestand):
    """{ziel_relativ: quelldatei} fuer alle Eintraege. Module kommen aus dem Repository unter runtime/src."""
    quelle = {"repo": Path(repo), "bestand": Path(bestand)}
    paare = {}
    modul_namen = [e[1] for e in eintraege if e[0] == "modul"]
    erweitert = []
    for art, pfad, ziel in eintraege:                         # `profil <art>` wird zu einer Zeile je Werkzeug-Ordner
        if art == "profil":
            erweitert += [("repo", (TOOLS / tid).as_posix() + "/", (TOOLS / tid).as_posix() + "/") for tid in sorted(profil_werkzeuge(repo, pfad))
                          if Path(repo, TOOLS, tid).is_dir()]
        elif art in ("shell", "app"):                           # AM8-11: aus den Manifesten abgeleitet
            erweitert += [("repo", p, p) for p in sorted(ableitung(repo, art, pfad)) if Path(repo, p).exists()]
        else:
            erweitert.append((art, pfad, ziel))
    for art, pfad, ziel in erweitert:
        if art == "modul":
            continue
        wurzel = quelle[art]
        base = wurzel / pfad
        if base.is_file():
            paare[Path(ziel).as_posix()] = base
            continue
        for datei in _sammeln(wurzel, pfad):
            paare[(Path(ziel) / datei.relative_to(base)).as_posix()] = datei
    src = Path(repo, "runtime", "src")
    for datei in closure(src, modul_namen):
        paare["runtime/src/" + datei.relative_to(src).as_posix()] = datei
    return {k: v for k, v in paare.items() if _kopierbar(Path(k))}


def manifest(ziel, eintraege_dateien, stand, profil=None):
    """STICK_MANIFEST.json: Pfad, Groesse, SHA-256 je Datei; mit Profil (ST-05) dazu `profil {art, apps, grundfunktionen}`."""
    eintraege = []
    for rel in sorted(eintraege_dateien):
        pfad = Path(ziel, rel)
        eintraege.append({"pfad": rel.replace(os.sep, "/"), "groesse": pfad.stat().st_size, "sha256": _hash(pfad)})
    daten = {"schema": 1, "stand": stand, "dateien": eintraege}
    if profil:
        daten["profil"] = profil
    Path(ziel, "STICK_MANIFEST.json").write_text(json.dumps(daten, indent=1, ensure_ascii=False), encoding="utf-8")
    return daten


def _hash(pfad):
    h = hashlib.sha256()
    with open(pfad, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def kopieren(paare, ziel):
    """Kopiert alle Paare nach `ziel`. Gibt die relativen Pfade zurueck."""
    ziel = Path(ziel)
    rel = []
    for schluessel, datei in sorted(paare.items()):
        dst = Path(ziel, schluessel)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(datei, dst)
        rel.append(schluessel)
    return rel


def _stand(repo):
    try:
        return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unbekannt"


def main(argv=None):
    p = argparse.ArgumentParser(description="SEDRA-Minimalpaket fuer den Stick")
    p.add_argument("--repo", required=True)
    p.add_argument("--bestand", required=True)
    p.add_argument("--ziel", required=True)
    p.add_argument("--liste", default=str(HERE / "stick_liste.txt"))
    p.add_argument("--pruefen", action="store_true")
    p.add_argument("--gegenprobe", action="store_true")
    a = p.parse_args(argv)
    eintraege = liste(a.liste)
    if a.gegenprobe:                                           # AM8-12: nur Befund, nichts wird angeglichen
        befund = gegenprobe(a.repo, eintraege)
        print(f"{len(befund)} Zeilen der Liste ohne Deckung durch die Manifeste")
        for zeile in befund:
            print(zeile)
        return 0
    paare = plan(eintraege, a.repo, a.bestand)
    info = profil_info(eintraege, a.repo)
    fehlt = pruefen_vollstaendig(a.repo, info["art"], paare) if info else []
    fehlt = sorted(set(fehlt + pruefen_ableitung(a.repo, eintraege)))
    if a.pruefen:
        print(f"{len(paare)} Dateien im Plan")
        for schluessel in sorted(paare):
            print(schluessel)
        for zeile in fehlt:
            print(zeile)
        return 1 if fehlt else 0
    if fehlt:                                                  # ST-04: vor dem Kopieren abbrechen
        print("Abbruch, dem Profil fehlt etwas:")
        for zeile in fehlt:
            print(zeile)
        return 1
    rel = kopieren(paare, a.ziel)
    daten = manifest(a.ziel, rel, _stand(a.repo), info)
    print(f"{len(daten['dateien'])} Dateien, {sum(d['groesse'] for d in daten['dateien'])} Byte, Manifest STICK_MANIFEST.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
