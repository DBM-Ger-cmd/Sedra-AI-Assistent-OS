"""Lese-Weg der Vorschau neben dem Gespräch (SPEC_HARNESS_SHELL_v1 Stufe 6, HS-71 bis HS-73; G2 §3; G3 N5).

Die Vorschau zeigt Dateien, die das Gespräch berührt hat. Dieser Weg liest **nur**: Er prüft den Pfad (relativ, kein `..`, im Projekt), verlangt, dass der Pfad im Verlauf der Sitzung
als Ziel eines Datei-Werkzeugs vorkommt (kein freies Durchsuchen), und lässt nichts lesen, was der Katalog verbietet oder ein fester Vorbehalt trifft – dieselbe Einstufung wie
beim Werkzeug `datei_lesen`. Der Inhalt ist Text für die Anzeige (fremder Text, keine Anweisung)."""
from __future__ import annotations

from pathlib import Path

from . import freigabe

WERKZEUGE = ('datei_lesen', 'datei_schreiben', 'datei_aendern')
BYTES_MAX = 200_000
ZEILEN_MAX = 600


class VorschauFehler(ValueError):
    """Der Pfad ist ungültig oder gehört nicht zum Verlauf der Sitzung; der Text ist der Grund."""


def _norm(pfad):
    if not isinstance(pfad, str) or not pfad.strip() or '\0' in pfad:
        raise VorschauFehler('pfad_fehlt')
    p = pfad.strip().replace(chr(92), '/')
    teile = [t for t in p.split('/') if t not in ('', '.')]
    if p.startswith('/') or (len(p) > 1 and p[1] == ':') or '..' in teile or not teile:
        raise VorschauFehler('pfad_ausserhalb: relativ zur Projektwurzel, ohne „..“')
    return '/'.join(teile)


def im_verlauf(eintraege, pfad):
    """Kommt `pfad` als Ziel eines Datei-Werkzeugs im Verlauf der Sitzung vor?"""
    for e in eintraege or []:
        if e.get('typ') in ('werkzeug', 'karte') and (e.get('name') or e.get('werkzeug')) in WERKZEUGE:          # auch eine Karte, die auf Freigabe wartet
            args = e.get('args') if isinstance(e.get('args'), dict) else {}
            try:
                if _norm(str(args.get('pfad') or '')) == pfad:
                    return True
            except VorschauFehler:
                continue
    return False


def lesen(wurzel, regeln, eintraege, pfad, *, bytes_max=BYTES_MAX, zeilen_max=ZEILEN_MAX):
    """{status, pfad, …}: `ok` (text, zeilen, gekuerzt, groesse), `gesperrt`, `binaer` (groesse), `fehlt`. Wirft VorschauFehler bei ungültigem Pfad."""
    rel = _norm(pfad)
    if not im_verlauf(eintraege, rel):
        raise VorschauFehler('pfad_nicht_im_verlauf: die Vorschau zeigt nur Dateien, die dieses Gespräch berührt hat')
    e = freigabe.einstufung(regeln, 'datei_lesen', {}, {'ziel': rel, 'vorhanden': True})
    if e['stufe'] == 'verboten' or e.get('vorbehalt'):
        return {'status': 'gesperrt', 'pfad': rel, 'grund': e.get('begruendung') or 'der Katalog lässt das Lesen nicht zu'}
    basis = Path(wurzel).resolve()
    ziel = (basis / rel).resolve()
    try:
        ziel.relative_to(basis)
    except ValueError:
        raise VorschauFehler('pfad_ausserhalb: relativ zur Projektwurzel, ohne „..“') from None
    if not ziel.is_file():
        return {'status': 'fehlt', 'pfad': rel}
    groesse = ziel.stat().st_size
    with ziel.open('rb') as f:
        roh = f.read(bytes_max + 1)
    if b'\0' in roh[:4096]:
        return {'status': 'binaer', 'pfad': rel, 'groesse': groesse}
    gekuerzt = len(roh) > bytes_max
    zeilen = roh[:bytes_max].decode('utf-8', errors='replace').splitlines()
    if len(zeilen) > zeilen_max:
        zeilen, gekuerzt = zeilen[:zeilen_max], True
    return {'status': 'ok', 'pfad': rel, 'text': '\n'.join(zeilen), 'zeilen': len(zeilen), 'gekuerzt': gekuerzt, 'groesse': groesse}
