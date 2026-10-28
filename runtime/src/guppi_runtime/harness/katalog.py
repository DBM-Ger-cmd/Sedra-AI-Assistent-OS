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
STUFEN = ('frei', 'vorarbeiter', 'captain', 'verboten')
STRENGE = {s: i for i, s in enumerate(STUFEN)}          # verboten > captain > vorarbeiter > frei
DATEI_WERKZEUGE = ('datei_lesen', 'dateien_auflisten', 'suchen', 'datei_schreiben', 'datei_aendern')
WERKZEUGE = DATEI_WERKZEUGE + ('befehl',)
ID = re.compile(r'[a-z0-9][a-z0-9-]{0,47}')


class KatalogFehler(ValueError):
    """Der Katalog ist ungültig; der Text nennt den Grund."""


# ---------------------------------------------------------------- U2: einstufen (rein)
def befehl_normal(zeile):
    """Eine Befehlszeile zum Vergleichen: Leerraum zusammengefasst, außen gekürzt, Groß/Klein egal (Windows)."""
    return ' '.join(str(zeile or '').split()).casefold()


def pfad_normal(pfad):
    """Ein Pfad relativ zur Projektwurzel zum Vergleichen: `/` als Trenner, ohne `./`, Groß/Klein egal (Windows). `..` bleibt sichtbar –
    der Aufrufer hat vorher aufgelöst; ein Pfad mit `..` passt auf kein Muster ohne `..`, es gilt dann `captain`."""
    teile = [t for t in str(pfad or '').replace('\\', '/').split('/') if t not in ('', '.')]
    return '/'.join(teile).casefold()


def _glob_regex(muster):
    out, i = [], 0
    while i < len(muster):
        if muster.startswith('**/', i):
            out.append('(?:.*/)?'); i += 3
        elif muster.startswith('**', i):
            out.append('.*'); i += 2
        elif muster[i] == '*':
            out.append('[^/]*'); i += 1
        elif muster[i] == '?':
            out.append('[^/]'); i += 1
        else:
            out.append(re.escape(muster[i])); i += 1
    return re.compile(''.join(out) + r'\Z', re.S)


def passt(muster, werkzeug, ziel):
    """Passt ein Muster auf ein Ziel? Dateien: Glob relativ zur Wurzel (`**` über Ordner, `*` in einem Teil). `befehl`: endet das Muster mit
    `*`, ist es der Anfang der normalisierten Zeile, sonst die ganze Zeile."""
    if werkzeug == 'befehl':
        m, z = befehl_normal(muster), befehl_normal(ziel)
        return z.startswith(m[:-1].rstrip()) if m.endswith('*') else z == m
    return bool(_glob_regex(pfad_normal(muster)).match(pfad_normal(ziel)))


def genauigkeit(muster):
    """Wie genau ein Muster ist: die Zahl seiner Zeichen ohne Platzhalter."""
    return len(str(muster).replace('*', '').replace('?', ''))


def einstufen(regeln, werkzeug, ziel):
    """{stufe, regel, begruendung} für einen Aufruf. `regeln` ist die Liste aus `laden`/`pruefen` (je Regel `werkzeug` und `muster` als
    Listen). Ohne passende Regel: `captain` (HS-21). `vorarbeiter` bleibt stehen – wer entscheidet, regelt die Freigabe."""
    beste = None
    for r in regeln:
        if werkzeug not in r['werkzeug'] and '*' not in r['werkzeug']:
            continue
        for m in r['muster']:
            if not passt(m, werkzeug, ziel):
                continue
            schluessel = (genauigkeit(m), STRENGE[r['stufe']])
            if beste is None or schluessel > beste[0]:
                beste = (schluessel, r)
    if beste is None:
        return {'stufe': 'captain', 'regel': None, 'begruendung': 'Keine Regel passt – ohne Regel entscheidet der Captain (HS-21).'}
    r = beste[1]
    return {'stufe': r['stufe'], 'regel': r['id'], 'begruendung': r['begruendung']}


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
