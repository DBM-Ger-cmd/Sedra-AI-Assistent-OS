"""Der Freigabe-Katalog der Harness-Shell (SPEC_HARNESS_SHELL_v1 HS-25, G2 §3.5, G3 Stufe 2 U1/U2).

Laden (U1): `local_config/freigabe_katalog.yaml` des SEDRA-Projekts, falls vorhanden – die Datei legt nur der Captain an (D-F2); sonst die
Vorlage `runtime/config/freigabe_katalog.beispiel.yaml` (nur lesen). Eine ungültige Datei ist ein Fehler mit Grund, nie ein stiller Rückfall.

Einstufen (U2, rein): `einstufen(regeln, werkzeug, ziel)` – die genaueste Regel gewinnt (längstes Muster ohne Platzhalter), bei Gleichstand die
strengere Stufe; ohne passende Regel `captain` (HS-21). `einstufen` ist die Referenz für den ersten SEDRA-Bau (Bau-Spec
`docs/BAUSPEC_KATALOG_EINSTUFEN.md`); baut SEDRA sie nach, ersetzt der Bau genau diese Funktion."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

DATEI = 'freigabe_katalog.yaml'
VORLAGE = Path(__file__).resolve().parents[3] / 'config' / 'freigabe_katalog.beispiel.yaml'
STUFEN = ('frei', 'vorarbeiter', 'captain', 'verboten')          # von mild nach streng; `einstufen` nimmt bei Gleichstand die strengere
DATEI_WERKZEUGE = ('datei_lesen', 'dateien_auflisten', 'suchen', 'datei_schreiben', 'datei_aendern')
WERKZEUGE = DATEI_WERKZEUGE + ('befehl', 'lauf_starten', 'lauf_stoppen', 'modell_laden', 'modell_entladen')      # Stufe 3: Läufe und Modelle (Ziel = Lauf-ID bzw. Rezept-ID)
ID = re.compile(r'[a-z0-9][a-z0-9-]{0,47}')


class KatalogFehler(ValueError):
    """Der Katalog ist ungültig; der Text nennt den Grund."""


# ---------------------------------------------------------------- U2: einstufen (rein) – gebaut von SEDRA
# Erster SEDRA-Bau (HS-E5, D-E6), Captain 28.10.2026 übernommen: devvm_build --spec harness_katalog --profile standard, Kandidat
# runtime_data/devvm_candidates/harness_katalog/attempt_01_20261028_152511, versteckt 19/19, gegen die Referenz von Claude
# (benchmarks/devvm_refs/harness_katalog) 698 Vergleiche ohne Abweichung. Unverändert übernommen bis auf diesen Kopf.

def befehl_normal(zeile):
    s = "" if zeile is None else str(zeile)
    return re.sub(r'\s+', ' ', s).strip().casefold()


def pfad_normal(pfad):
    s = "" if pfad is None else str(pfad)
    parts = s.replace('\\', '/').split('/')
    result = [p for p in parts if p and p != '.']
    return '/'.join(result).casefold()


def _glob_match(pattern, target):
    regex = []
    i = 0
    n = len(pattern)
    while i < n:
        c = pattern[i]
        if c == '*':
            if i + 1 < n and pattern[i + 1] == '*':
                if i + 2 < n and pattern[i + 2] == '/':
                    regex.append('(?:.*/)?')
                    i += 3
                else:
                    regex.append('.*')
                    i += 2
            else:
                regex.append('[^/]*')
                i += 1
        elif c == '?':
            regex.append('[^/]')
            i += 1
        else:
            regex.append(re.escape(c))
            i += 1
    return re.fullmatch(''.join(regex), target) is not None


def passt(muster, werkzeug, ziel):
    if werkzeug == "befehl":
        norm_muster = befehl_normal(muster)
        norm_ziel = befehl_normal(ziel)
        if norm_muster.endswith('*'):
            prefix = norm_muster[:-1].rstrip()
            return norm_ziel.startswith(prefix)
        else:
            return norm_muster == norm_ziel
    else:
        norm_muster = pfad_normal(muster)
        norm_ziel = pfad_normal(ziel)
        return _glob_match(norm_muster, norm_ziel)


def genauigkeit(muster):
    return sum(1 for c in str(muster) if c not in ('*', '?'))


def einstufen(regeln, werkzeug, ziel):
    candidates = []
    for idx, regel in enumerate(regeln):
        w_list = regel["werkzeug"]
        if werkzeug in w_list or "*" in w_list:
            for muster in regel["muster"]:
                if passt(muster, werkzeug, ziel):
                    candidates.append((idx, regel, muster))

    if not candidates:
        return {
            "stufe": "captain",
            "regel": None,
            "begruendung": "Keine Regel passt – ohne Regel entscheidet der Captain (HS-21)."
        }

    def sort_key(item):
        idx, regel, muster = item
        stufe_idx = STUFEN.index(regel["stufe"])
        g = genauigkeit(muster)
        return (-g, -stufe_idx, idx)

    candidates.sort(key=sort_key)
    winner_idx, winner_regel, winner_muster = candidates[0]
    return {
        "stufe": winner_regel["stufe"],
        "regel": winner_regel["id"],
        "begruendung": winner_regel["begruendung"]
    }


# ---------------------------------------------------------------- U1: laden und prüfen
def _liste(wert):
    return [wert] if isinstance(wert, str) else wert


def pruefen(doc):
    """Die Regeln aus einer gelesenen Datei – oder KatalogFehler mit Grund."""
    k = doc.get('freigabe_katalog') if isinstance(doc, dict) else None
    if not isinstance(k, dict) or not isinstance(k.get('regeln'), list) or not k['regeln']:
        raise KatalogFehler('regeln_fehlen: die Datei braucht „freigabe_katalog: regeln:“ mit mindestens einer Regel')
    out, ids = [], set()
    for n, r in enumerate(k['regeln'], 1):
        if not isinstance(r, dict):
            raise KatalogFehler(f'regel_{n}_kein_eintrag')
        rid = r.get('id')
        if not isinstance(rid, str) or not ID.fullmatch(rid):
            raise KatalogFehler(f'regel_{n}_id_ungueltig: kleine Buchstaben, Ziffern und Bindestrich')
        if rid in ids:
            raise KatalogFehler(f'regel_{rid}_doppelt')
        ids.add(rid)
        werkzeug, muster = _liste(r.get('werkzeug')), _liste(r.get('muster'))
        if not isinstance(werkzeug, list) or not werkzeug or any(w != '*' and w not in WERKZEUGE for w in werkzeug):
            raise KatalogFehler(f'regel_{rid}_werkzeug_unbekannt: erlaubt {", ".join(WERKZEUGE)} oder *')
        if not isinstance(muster, list) or not muster or not all(isinstance(m, str) and m.strip() for m in muster):
            raise KatalogFehler(f'regel_{rid}_muster_fehlt')
        for m in muster:
            if any(w in DATEI_WERKZEUGE or w == '*' for w in werkzeug) and werkzeug != ['befehl'] and \
                    ('..' in m.replace('\\', '/').split('/') or re.match(r'^([A-Za-z]:|/)', m)):
                raise KatalogFehler(f'regel_{rid}_muster_ausserhalb: Dateimuster relativ zur Projektwurzel, ohne „..“')
        if r.get('stufe') not in STUFEN:
            raise KatalogFehler(f'regel_{rid}_stufe_unbekannt: {", ".join(STUFEN)}')
        begruendung = r.get('begruendung')
        if not isinstance(begruendung, str) or not begruendung.strip():
            raise KatalogFehler(f'regel_{rid}_begruendung_fehlt: jede Regel sagt, warum')
        out.append({'id': rid, 'werkzeug': list(werkzeug), 'muster': list(muster), 'stufe': r['stufe'], 'begruendung': begruendung.strip()})
    return out


def laden(projekt_root: Path, vorlage: Path = VORLAGE):
    """{regeln, quelle, datei} – die Datei des Captains, sonst die Vorlage. Kaputt → KatalogFehler (kein stiller Rückfall)."""
    eigen = Path(projekt_root) / 'local_config' / DATEI
    pfad = eigen if eigen.is_file() else Path(vorlage)
    try:
        doc = yaml.safe_load(pfad.read_text(encoding='utf-8'))
    except (OSError, yaml.YAMLError, UnicodeDecodeError) as exc:
        raise KatalogFehler(f'datei_unlesbar: {pfad.name}: {type(exc).__name__}') from exc
    return {'regeln': pruefen(doc), 'quelle': 'local_config' if pfad == eigen else 'vorlage', 'datei': str(pfad)}


# ---------------------------------------------------------------- Stufe 5: schreiben – nur über einen Antrag mit Gate (G2 Stufe 5 §4, D-U2)
# Der Editor der Einstellungen schreibt die Datei des Captains nie direkt: er legt einen Antrag an (gated.request), und erst
# „Freigeben und anwenden“ ruft `schreiben`/`entfernen`. Die Prüfung ist dieselbe wie beim Laden (`pruefen`), die Sicherung bleibt.
import hashlib as _hashlib
import json as _json
import time as _time

WEITE_MUSTER = re.compile(r'^(\*\*|\*|\*\*/\*|\.|/|\*\*/\*\*)$')          # trifft alles – im Antrag ein Risiko, nie ein Fehler
STUFE_RANG = {s: i for i, s in enumerate(STUFEN)}                           # frei < vorarbeiter < captain < verboten


def pruefe_entwurf(regeln):
    """Die Regeln eines Entwurfs (Liste von Einträgen) – dieselbe Prüfung wie beim Laden einer Datei. KatalogFehler mit Grund."""
    return pruefen({'freigabe_katalog': {'regeln': list(regeln or [])}})


def hash_von(regeln):
    """Stabiler Hash über die geprüften Regeln – die Bindung des Antrags (Stand und Entwurf)."""
    text = _json.dumps(regeln, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return _hashlib.sha256(text.encode('utf-8')).hexdigest()


def befunde(entwurf, stand, vorlage_regeln):
    """Was der Captain vor der Freigabe sehen soll (rein): weite Muster, Lockerungen gegen die Vorlage, Diff-Zahlen. Keine Fehler –
    die kommen aus `pruefe_entwurf`."""
    alt = {r['id']: r for r in stand}
    neu = {r['id']: r for r in entwurf}
    vorlage = {r['id']: r for r in vorlage_regeln}
    out = []
    for r in entwurf:
        v = vorlage.get(r['id'])
        for m in r['muster'] if r != v else ():                           # die Vorlage selbst ist geprüft; nur Eigenes wird gemeldet
            if WEITE_MUSTER.match(m.strip()):
                out.append(f"weites Muster: Regel „{r['id']}“ trifft mit „{m}“ alles ({', '.join(r['werkzeug'])})")
        if v and STUFE_RANG[r['stufe']] < STUFE_RANG[v['stufe']]:
            out.append(f"Lockerung: Regel „{r['id']}“ der Vorlage von {v['stufe']} auf {r['stufe']}")
    for rid, v in vorlage.items():
        if v['stufe'] == 'verboten' and rid not in neu:
            out.append(f"Vorlage-Regel „{rid}“ (verboten) fehlt im Entwurf")
    zahlen = {'neu': sorted(set(neu) - set(alt)), 'entfernt': sorted(set(alt) - set(neu)),
              'geaendert': sorted(i for i in set(alt) & set(neu) if alt[i] != neu[i])}
    return out, zahlen


def _datei(projekt_root):
    return Path(projekt_root) / 'local_config' / DATEI


def sichern(projekt_root, verschieben=False):
    """Kopie der Datei des Captains mit Zeitstempel (`verschieben`: die Datei selbst wird zur Sicherung, nichts wird gelöscht); None, wenn es keine gibt."""
    pfad = _datei(projekt_root)
    if not pfad.is_file():
        return None
    ziel = pfad.with_name(pfad.name + '.bak-' + _time.strftime('%Y%m%d-%H%M%S'))
    n = 0
    while ziel.exists():
        n += 1
        ziel = pfad.with_name(pfad.name + '.bak-' + _time.strftime('%Y%m%d-%H%M%S') + f'-{n}')
    if verschieben:
        pfad.replace(ziel)
    else:
        ziel.write_bytes(pfad.read_bytes())
    return ziel


def schreiben(projekt_root, regeln):
    """Die geprüften Regeln als Datei des Captains (atomar, mit Kopfkommentar und Sicherung). Rückgabe {datei, sicherung, hash}.
    Nur der Applier eines freigegebenen Antrags ruft das (G2 Stufe 5 §4.4)."""
    from ..core.util import atomic_write_text
    regeln = pruefe_entwurf(regeln)
    pfad = _datei(projekt_root)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    sicherung = sichern(projekt_root)
    kopf = ('# Freigabe-Katalog des Captains (SPEC_HARNESS_SHELL_v1 HS-25). Geschrieben über den Katalog-Editor der Harness-Shell\n'
            '# (Stufe 5) nach Freigabe im Posteingang; Sicherungen liegen daneben (*.bak-<zeit>). Von Hand bearbeiten ist weiter erlaubt.\n')
    text = kopf + yaml.safe_dump({'freigabe_katalog': {'regeln': regeln}}, allow_unicode=True, sort_keys=False, width=120)
    atomic_write_text(pfad, text)
    return {'datei': str(pfad), 'sicherung': str(sicherung) if sicherung else None, 'hash': hash_von(regeln), 'regeln': len(regeln)}


def entfernen(projekt_root):
    """Die Datei des Captains mit Sicherung entfernen – danach gilt wieder die Vorlage. Rückgabe {entfernt, sicherung}."""
    pfad = _datei(projekt_root)
    if not pfad.is_file():
        return {'entfernt': False, 'sicherung': None}
    sicherung = sichern(projekt_root, verschieben=True)         # die Datei wird zur Sicherung umbenannt, nicht gelöscht
    return {'entfernt': True, 'sicherung': str(sicherung)}
