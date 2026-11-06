"""Umstieg einer bestehenden Installation auf die SEDRA-Namen (1.23.0): Vorschau, Anwenden, Zurücknehmen.

Der eingebaute Updater älterer Installationen kennt nur die alten Programmpfade und lehnt dieses Paket ab.
Dieser Installer liegt im Paket und arbeitet ohne den alten Updater: Er prüft das Paket gegen sein Manifest,
sichert alles, was er ändert, kopiert die neuen Dateien, zieht den Projektordner um und schreibt ein Protokoll
für `--rollback`. Ohne `--apply` wird nichts geschrieben. Kein Netz, keine Modelle, keine Prozesse.

    python INSTALL_NAMENSWECHSEL.py --root <Installationsordner>                       Vorschau, nennt den Bestätigungsschlüssel
    python INSTALL_NAMENSWECHSEL.py --root <Installationsordner> --apply --confirm <Schlüssel>
    python INSTALL_NAMENSWECHSEL.py --root <Installationsordner> --rollback

SEDRA vorher beenden. Gelöscht wird nichts: Altes wandert nach local_config/update/sicherung.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

MANIFEST = 'release/MANIFEST_NAMENSWECHSEL.sha256'
PROTOKOLL = 'local_config/update/namenswechsel.json'
ZEILE = re.compile(r'^([0-9a-f]{64})  (\S.*)$')
ERLAUBT = ('runtime/src/sedra_runtime/', 'runtime/config/', 'architecture/SEDRA_Architecture_')
WURZEL_DATEIEN = ('START_SEDRA.bat', 'start_sedra.sh', 'START_SEDRA.command')


class Fehler(ValueError):
    pass


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lokal_behalten(rel: str) -> bool:
    return rel == 'runtime/config/local_paths.yaml' or '.bak-' in Path(rel).name


def manifest_lesen(text: str) -> dict:
    out = {}
    for n, zeile in enumerate(text.splitlines(), 1):
        if not zeile.strip():
            continue
        m = ZEILE.match(zeile)
        if not m:
            raise Fehler(f'manifest_zeile_{n}_ungueltig')
        rel = m.group(2)
        if rel.startswith('/') or '..' in rel.split('/') or '\\' in rel:
            raise Fehler('manifest_pfad_nicht_erlaubt:' + rel)
        if not (rel.startswith(ERLAUBT) or rel in WURZEL_DATEIEN) or lokal_behalten(rel):
            raise Fehler('manifest_pfad_nicht_erlaubt:' + rel)
        out[rel] = m.group(1)
    if not out:
        raise Fehler('manifest_leer')
    return out


def paket_pruefen(candidate: Path) -> dict:
    erwartet = manifest_lesen((candidate / MANIFEST).read_text(encoding='utf-8'))
    for rel, h in erwartet.items():
        p = candidate / rel
        if p.is_symlink() or not p.is_file():
            raise Fehler('paketdatei_fehlt:' + rel)
        if sha(p) != h:
            raise Fehler('pruefsumme_falsch:' + rel)
    vorhanden = set()
    for bereich in ('runtime/src/sedra_runtime', 'runtime/config', 'architecture'):
        for p in (candidate / bereich).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc':
                rel = p.relative_to(candidate).as_posix()
                if rel.startswith(ERLAUBT) and not lokal_behalten(rel):
                    vorhanden.add(rel)
    if vorhanden | {r for r in WURZEL_DATEIEN if (candidate / r).is_file()} != set(erwartet):
        zu_viel = sorted((vorhanden | set(WURZEL_DATEIEN)) - set(erwartet))
        raise Fehler('dateien_passen_nicht:' + ','.join(zu_viel[:3]))
    return erwartet


def namen(candidate: Path):
    sys.path.insert(0, str(candidate / 'runtime/src'))
    from sedra_runtime import legacy_names
    return legacy_names


def vorschau(candidate: Path, root: Path):
    candidate, root = Path(candidate).resolve(), Path(root).resolve()
    if candidate == root or candidate.is_relative_to(root) or root.is_relative_to(candidate):
        raise Fehler('paket_und_installation_muessen_getrennt_liegen')
    ln = namen(candidate)
    erwartet = paket_pruefen(candidate)
    if (root / PROTOKOLL).is_file():
        raise Fehler('schon_umgestellt_oder_protokoll_vorhanden: erst --rollback')
    alt_paket = (root / 'runtime/src' / ln.PAKET_ALT).is_dir()
    if not alt_paket and not (root / 'runtime/src/sedra_runtime').is_dir():
        raise Fehler('keine_sedra_installation_unter_root')
    neu = sorted(r for r in erwartet if not (root / r).is_file())
    geaendert = sorted(r for r in erwartet if (root / r).is_file() and sha(root / r) != erwartet[r])
    plan = {'neue_dateien': neu, 'geaenderte_dateien': geaendert, 'anzahl': len(erwartet),
            'altes_programmpaket_wird_gesichert': alt_paket,
            'projektordner_wird_umbenannt': (root / 'workspace' / ln.PROJEKTORDNER_ALT).is_dir() and not (root / 'workspace' / ln.PROJEKTORDNER_NEU).exists(),
            'alte_architekturordner': sorted(p.name for p in (root / 'architecture').glob(ln.ARCHITEKTUR_ALT + '*') if p.is_dir()) if (root / 'architecture').is_dir() else []}
    schluessel = hashlib.sha256(json.dumps({'root': str(root), 'manifest': hashlib.sha256((candidate / MANIFEST).read_bytes()).hexdigest(),
                                            'plan': plan}, sort_keys=True).encode()).hexdigest()
    return plan, schluessel, erwartet, ln


def anwenden(candidate: Path, root: Path, erwartet: dict, ln) -> dict:
    root = Path(root)
    zeit = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    sicherung = root / 'local_config' / 'update' / 'sicherung' / f'{zeit}_vor_namenswechsel'
    protokoll = {'erstellt': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'sicherung': sicherung.relative_to(root).as_posix(),
                 'neu_angelegt': [], 'gesichert': [], 'umzug': []}
    try:
        for rel in erwartet:
            ziel = root / rel
            if ziel.is_file():
                kopie = sicherung / 'dateien' / rel
                kopie.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ziel, kopie)
                protokoll['gesichert'].append(rel)
            else:
                protokoll['neu_angelegt'].append(rel)
        for rel in erwartet:
            ziel = root / rel
            ziel.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(candidate / rel, ziel)
        protokoll['umzug'] = ln.umziehen(root)
    except Exception:
        _zurueck(root, protokoll, ln)
        raise
    (root / PROTOKOLL).parent.mkdir(parents=True, exist_ok=True)
    (root / PROTOKOLL).write_text(json.dumps(protokoll, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'status': 'umgestellt', 'dateien': len(erwartet), 'umzug': protokoll['umzug'], 'sicherung': protokoll['sicherung']}


def _zurueck(root: Path, protokoll: dict, ln) -> list[str]:
    schritte = []
    alt_namen = root / 'local_config' / 'update' / 'sicherung' / 'alt_namen'
    neu_proj, alt_proj = root / 'workspace' / ln.PROJEKTORDNER_NEU, root / 'workspace' / ln.PROJEKTORDNER_ALT
    if any(s.startswith('Projektordner umbenannt') for s in protokoll.get('umzug', [])) and neu_proj.is_dir() and not alt_proj.exists():
        neu_proj.rename(alt_proj)
        schritte.append('Projektordner zurückbenannt')
    if alt_namen.is_dir():
        for ordner in sorted(alt_namen.iterdir()):
            ziel = (root / 'runtime/src' / ordner.name) if ordner.name == ln.PAKET_ALT else (root / 'architecture' / ordner.name)
            if not ziel.exists():
                ziel.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(ordner), str(ziel))
                schritte.append('zurückgeholt: ' + ziel.relative_to(root).as_posix())
    for rel in protokoll.get('gesichert', []):
        kopie = root / protokoll['sicherung'] / 'dateien' / rel
        if kopie.is_file():
            shutil.copy2(kopie, root / rel)
    for rel in protokoll.get('neu_angelegt', []):
        (root / rel).unlink(missing_ok=True)
    for ordner in ('runtime/src/sedra_runtime', *[p.relative_to(root).as_posix() for p in (root / 'architecture').glob('SEDRA_Architecture_*')]):
        pfad = root / ordner
        for d in sorted((p for p in pfad.rglob('*') if p.is_dir()), key=lambda p: len(p.parts), reverse=True) if pfad.is_dir() else []:
            if not any(d.iterdir()):
                d.rmdir()
        if pfad.is_dir() and not any(pfad.iterdir()):
            pfad.rmdir()
    return schritte


def zuruecknehmen(root: Path, ln) -> dict:
    root = Path(root)
    if not (root / PROTOKOLL).is_file():
        raise Fehler('kein_protokoll')
    protokoll = json.loads((root / PROTOKOLL).read_text(encoding='utf-8'))
    schritte = _zurueck(root, protokoll, ln)
    (root / PROTOKOLL).unlink()
    return {'status': 'zurueckgenommen', 'schritte': schritte}


def main(argv=None, candidate=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--root', required=True)
    p.add_argument('--apply', action='store_true')
    p.add_argument('--confirm', default='')
    p.add_argument('--rollback', action='store_true')
    args = p.parse_args(argv)
    if candidate is None:
        candidate = Path(__file__).resolve().parent
        if not (candidate / 'runtime/src/sedra_runtime').is_dir():
            candidate = candidate.parent
    candidate = Path(candidate)
    try:
        if args.rollback:
            print(json.dumps(zuruecknehmen(Path(args.root), namen(candidate)), ensure_ascii=False, indent=2))
            return 0
        plan, schluessel, erwartet, ln = vorschau(candidate, Path(args.root))
        print(json.dumps({'vorschau': plan, 'bestaetigung': schluessel, 'angewendet': False}, ensure_ascii=False, indent=2))
        if args.apply:
            if args.confirm != schluessel:
                raise Fehler('genau_die_vorschau_bestaetigen')
            print(json.dumps(anwenden(candidate, Path(args.root), erwartet, ln), ensure_ascii=False, indent=2))
        return 0
    except (Fehler, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
