"""Bausteine für Aufgaben-Freigaben (Captain 04.11.2026, Analyse docs/ANALYSE_FREIGABEN_VEREINFACHEN_2026-11-04.md, S1).

Ein Baustein ist eine fertige Erlaubnis („Tests starten“, „Dokumente in docs/ ändern“) für das Formular der Aufgaben – ein Klick statt einer Zeile mit Muster-Syntax.
Die Vorgabe steht in `runtime/config/freigabe_bausteine.yaml`; eigene legt nur der Captain in `local_config/freigabe_bausteine.yaml` an (gleiche id ersetzt die Vorgabe).
Das Modell legt nie einen an: es gibt keinen Weg dafür, nur dieses Lesen. Ein Baustein ist nur eine Auswahlhilfe – was beim Anlegen einer Aufgabe daraus wird, prüft
derselbe Code wie bei jeder Zeile (harness/aufgabe.py); hier wird nur abgewiesen, was nie sinnvoll wäre (unbekanntes Werkzeug, Muster, das alles trifft).
Eine kaputte Datei ist ein ValueError mit Satz; die Vorgabe geht dann trotzdem (die eigene Datei fällt mit Hinweis weg), damit das Formular nie leer bleibt."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

VORGABE = Path(__file__).resolve().parents[3] / 'config' / 'freigabe_bausteine.yaml'
DATEI = 'freigabe_bausteine.yaml'
WERKZEUGE = ('datei_lesen', 'dateien_auflisten', 'suchen', 'datei_schreiben', 'datei_aendern', 'befehl', 'lauf_starten', 'lauf_stoppen')
ID = re.compile(r'[a-z0-9][a-z0-9-]{0,39}')
WEIT = re.compile(r'^(\*\*?|\*\*/\*|\.?/?\*\*?)$')
ZEILEN_MAX, BAUSTEINE_MAX, TEXT_MAX = 6, 30, 120


def pruefen(doc, quelle):
    """Die Bausteine einer Datei als Liste {id, name, hinweis, zeilen, quelle} – oder ValueError mit Satz."""
    liste = doc.get('bausteine') if isinstance(doc, dict) else None
    if not isinstance(liste, list):
        raise ValueError(f'bausteine_ohne_liste: {quelle}')
    if len(liste) > BAUSTEINE_MAX:
        raise ValueError(f'bausteine_zu_viele: {quelle} (höchstens {BAUSTEINE_MAX})')
    out, ids = [], set()
    for e in liste:
        if not isinstance(e, dict):
            raise ValueError(f'baustein_kein_objekt: {quelle}')
        bid = e.get('id')
        if not isinstance(bid, str) or not ID.fullmatch(bid):
            raise ValueError(f'baustein_id_ungueltig: {bid!r} – kleine Buchstaben, Ziffern, Bindestrich')
        if bid in ids:
            raise ValueError(f'baustein_id_doppelt: {bid}')
        ids.add(bid)
        name = e.get('name')
        if not isinstance(name, str) or not name.strip() or len(name) > TEXT_MAX:
            raise ValueError(f'baustein_name_fehlt: {bid}')
        hinweis = e.get('hinweis') or ''
        if not isinstance(hinweis, str) or len(hinweis) > 300:
            raise ValueError(f'baustein_hinweis_ungueltig: {bid}')
        zeilen = e.get('zeilen')
        if not isinstance(zeilen, list) or not zeilen or len(zeilen) > ZEILEN_MAX:
            raise ValueError(f'baustein_zeilen_ungueltig: {bid} (1 bis {ZEILEN_MAX} Zeilen)')
        fertig = []
        for z in zeilen:
            w, m = (z.get('werkzeug'), z.get('muster')) if isinstance(z, dict) else (None, None)
            if w not in WERKZEUGE:
                raise ValueError(f'baustein_werkzeug_unbekannt: {bid}: {w!r} – erlaubt {", ".join(WERKZEUGE)}')
            if not isinstance(m, str) or not m.strip() or len(m) > 200:
                raise ValueError(f'baustein_muster_fehlt: {bid}')
            if WEIT.match(m.strip().replace('\\', '/')):
                raise ValueError(f'baustein_muster_zu_weit: {bid}: {m!r} trifft alles')
            fertig.append({'werkzeug': w, 'muster': m.strip()})
        out.append({'id': bid, 'name': name.strip(), 'hinweis': hinweis.strip(), 'zeilen': fertig, 'quelle': quelle})
    return out


def _lesen(pfad, quelle):
    try:
        doc = yaml.safe_load(Path(pfad).read_text(encoding='utf-8'))
    except (OSError, yaml.YAMLError, UnicodeDecodeError) as exc:
        raise ValueError(f'bausteine_nicht_lesbar: {quelle}: {type(exc).__name__}') from exc
    return pruefen(doc, quelle)


def laden(projekt_root, vorgabe=VORGABE):
    """{bausteine: [...], hinweise: [Sätze]}: die Vorgabe, darüber die eigenen (gleiche id ersetzt). Eine kaputte eigene Datei steht als Hinweis, nie als Absturz."""
    bausteine = {b['id']: b for b in _lesen(vorgabe, 'repo')}
    hinweise = []
    eigene = Path(projekt_root) / 'local_config' / DATEI
    if eigene.is_file():
        try:
            for b in _lesen(eigene, 'local_config'):
                bausteine[b['id']] = b
        except ValueError as exc:
            hinweise.append(str(exc))
    return {'bausteine': list(bausteine.values()), 'hinweise': hinweise}
