#!/usr/bin/env python3
"""Ticket B6-G-01, G-06: der B6-Korpus gegen die GUPPI-Matrix (gateway/klassen.py) – nur Messung, kein Produktcode.

Aufruf (im Ordner runtime/):
    PYTHONPATH=src python3 benchmarks/b6_korpus_gegen_guppi.py <korpus.json> [--out bericht.md]

Eingabe: die Korpusdatei im Schema der KIMOAN-Testdaten (`test_cases[]` mit `case_id`, `input.text`, `input.context.requested_processing`,
`expected.policy_status`, `expected.route`, optional `expected.attributes`). `expected` geht nie in Scanner oder Matrix – nur in den
Vergleich. Je Fall: PASS (Status und Weg wie erwartet), FAIL (Abweichung), NOT_TESTABLE (Fall braucht etwas, das die Matrix nicht
kennt – Quellenklasse, Anhang, Modell). Kritische Falschfreigabe = erwartet BLOCKED oder HUMAN_REVIEW_REQUIRED, GUPPI sagt AUTO_APPROVED.

Grenzen: Die GUPPI-Matrix kennt kein Quellenregister und keine Rollen; `declared_class` der Quelle und `purpose` werden nur ausgegeben,
nicht gewertet. Ein PASS belegt Übereinstimmung mit dem Soll des Korpus, nicht fachliche Richtigkeit des Solls.
Das Skript ruft kein Modell, schreibt nichts außer dem Bericht und sendet nichts über das Netz.
"""
import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from guppi_runtime.core.b6core.normalize import normalize
from guppi_runtime.core.content_policy import ScanFailure, scan_content
from guppi_runtime.gateway import klassen

ROUTE_MAP = {'LOCAL_ONLY': 'LOCAL_ONLY', 'LOCAL_MODEL': 'LOCAL_ONLY', 'CLOUD_AFTER_PSEUDONYMIZATION': 'CLOUD_AFTER_PSEUDONYMIZATION',
             'CLOUD_PSEUDONYMIZED_SIMULATED': 'CLOUD_AFTER_PSEUDONYMIZATION', 'CLOUD_ALLOWED': 'CLOUD_ALLOWED', 'CLOUD_ALLOWED_SIMULATED': 'CLOUD_ALLOWED',
             'CLOUD_MODEL': 'CLOUD_ALLOWED', 'HUMAN_REVIEW': None, 'BLOCKED': None, None: None, '': None}


def lade_csv_korpus(csv_path):
    """Der Korpus v0.2 (Torsten, 03_Testfaelle_v0.2-DRAFT.csv + inputs/): in das JSON-Schema des Adapters.
    Soll-Status aus expected_route/expected_review: BLOCKED → BLOCKED; HUMAN_REVIEW oder R1+R2 → HUMAN_REVIEW_REQUIRED; sonst AUTO_APPROVED.
    Quellen (Q-00x) kennt die GUPPI-Matrix nicht – sie stehen nur im Bericht. Ein Anhang .txt wird als Dokument mitgeprüft; .pdf → NOT_TESTABLE."""
    import csv
    base = Path(csv_path).parent
    out = []
    for r in csv.DictReader(open(csv_path, encoding='utf-8')):
        cid = r['case_id']
        inp = base / 'inputs' / f'{cid}_input.txt'
        text = inp.read_text(encoding='utf-8') if inp.is_file() else ''
        anh = sorted(p for p in (base / 'inputs').glob(f'{cid}_*') if not p.name.endswith('_input.txt'))
        dok = next((p for p in anh if p.suffix.lower() in ('.txt', '.md')), None)
        route = (r.get('expected_route') or '').strip(); review = (r.get('expected_review') or '').strip()
        status = 'BLOCKED' if route == 'BLOCKED' else ('HUMAN_REVIEW_REQUIRED' if route == 'HUMAN_REVIEW' or 'R1' in review else 'AUTO_APPROVED')
        wunsch = 'CLOUD_MODEL' if route.startswith('CLOUD') else 'LOCAL_MODEL'
        out.append({'case_id': cid, 'input': {'text': text, 'dokument': dok.read_text(encoding='utf-8', errors='replace') if dok else '',
                                              'attachments': [p.name for p in anh if p.suffix.lower() not in ('.txt', '.md')],
                                              'source': {'declared_class': (r.get('source_status') or '')[:60]},
                                              'context': {'requested_processing': wunsch, 'purpose': r.get('intent')}},
                    'expected': {'policy_status': status, 'route': route if route not in ('HUMAN_REVIEW', 'BLOCKED') else None,
                                 'attributes': {}, 'grund': (r.get('expected_reason') or '')[:120]}})
    return out
STRENGE = ['AUTO_APPROVED', 'HUMAN_REVIEW_REQUIRED', 'BLOCKED']


def einstufen_text(text, manuell=(), dokument=''):
    clean = normalize(text or '').clean
    dok = normalize(dokument or '').clean
    try:
        hits = [(h.rule_id, h.kind) for h in scan_content(clean)]
        hits_d = [(h.rule_id, h.kind) for h in scan_content(dok)] if dok else []
        ok = True
    except ScanFailure:
        hits, hits_d, ok = [], [], False
    return klassen.einstufen(hits, hits_d, scan_ok=ok, manuell=manuell)


def weg_fuer(e, wunsch):
    """Welchen Weg GUPPI dem Wunsch des Falls anbietet (K-03: nie offener als der Wunsch)."""
    if e.policy == 'BLOCKED' or not e.wege:
        return None
    return klassen.weg_erlaubt(e, 'local' if wunsch == 'LOCAL_ONLY' else 'cloud')


def pruefe(case):
    i, exp = case.get('input') or {}, case.get('expected') or {}
    text = i.get('text') or ''
    dokument = i.get('dokument') or ''
    if not text.strip():
        return {'id': case.get('case_id'), 'ergebnis': 'NOT_TESTABLE', 'grund': 'kein Text'}
    if (i.get('attachments') or i.get('anhaenge')):
        return {'id': case.get('case_id'), 'ergebnis': 'NOT_TESTABLE', 'grund': 'Anhang – GUPPI MVP 1 kennt nur .md/.txt aus dem Projekt'}
    wunsch = ROUTE_MAP.get((i.get('context') or {}).get('requested_processing'), 'LOCAL_ONLY') or 'LOCAL_ONLY'
    manuell = [a for a in (i.get('manual_attributes') or []) if a in klassen.MANUELL]
    e = einstufen_text(text, manuell, dokument)
    ist_weg = weg_fuer(e, wunsch)
    soll_status = exp.get('policy_status')
    soll_weg = ROUTE_MAP.get(exp.get('route'), exp.get('route'))
    soll_attr = sorted(a for a, st in (exp.get('attributes') or {}).items() if st in ('CONFIRMED', 'SUSPECTED', True)) if isinstance(exp.get('attributes'), dict) else sorted(exp.get('attributes') or [])
    row = {'id': case.get('case_id'), 'quelle_klasse': (i.get('source') or {}).get('declared_class'), 'wunsch': wunsch,
           'soll_status': soll_status, 'ist_status': e.policy, 'soll_weg': soll_weg, 'ist_weg': ist_weg,
           'soll_merkmale': soll_attr, 'ist_merkmale': list(e.merkmale), 'ist_klasse': e.klasse}
    if soll_status is None:
        row.update(ergebnis='NOT_TESTABLE', grund='kein Sollwert policy_status')
        return row
    status_ok = e.policy == soll_status
    weg_ok = (soll_weg is None) or (ist_weg == soll_weg) or (soll_weg in e.wege)
    row['ergebnis'] = 'PASS' if status_ok and weg_ok else 'FAIL'
    row['kritisch'] = (soll_status in ('BLOCKED', 'HUMAN_REVIEW_REQUIRED') and e.policy == 'AUTO_APPROVED')
    if not status_ok:
        row['grund'] = f'Status: Soll {soll_status}, Ist {e.policy}'
    elif not weg_ok:
        row['grund'] = f'Weg: Soll {soll_weg}, Ist {ist_weg} (erlaubt: {", ".join(e.wege) or "–"})'
    return row


def bericht(rows, quelle, out):
    c = Counter(r['ergebnis'] for r in rows)
    krit = [r for r in rows if r.get('kritisch')]
    lines = [f'# B6-Korpus gegen GUPPI-Matrix {klassen.POLICY_VERSION} – Messung {datetime.now(timezone.utc).astimezone().isoformat(timespec="minutes")}',
             '', f'Quelle: `{quelle}` · Fälle: {len(rows)} · **{c["PASS"]} PASS / {c["FAIL"]} FAIL / {c["NOT_TESTABLE"]} NOT_TESTABLE** · '
             f'kritische Falschfreigaben: **{len(krit)}**', '',
             'Nur Messung (Ticket B6-G-01, G-06). Quellenklasse, Rollen und Zweck werden von der GUPPI-Matrix nicht gewertet; ein PASS ist '
             'Übereinstimmung mit dem Korpus-Soll, keine fachliche Bestätigung des Solls.', '',
             '| Fall | Quelle | Wunsch | Soll Status | Ist Status | Soll Weg | Ist Weg | Soll Merkmale | Ist Merkmale | Ergebnis | Grund |',
             '|---|---|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        lines.append('| ' + ' | '.join(str(x if x not in (None, [], '') else '–') for x in (
            r.get('id'), r.get('quelle_klasse'), r.get('wunsch'), r.get('soll_status'), r.get('ist_status'), r.get('soll_weg'), r.get('ist_weg'),
            ', '.join(r.get('soll_merkmale') or []), ', '.join(r.get('ist_merkmale') or []),
            r['ergebnis'] + (' **kritisch**' if r.get('kritisch') else ''), r.get('grund'))) + ' |')
    text = '\n'.join(lines) + '\n'
    if out:
        Path(out).write_text(text, encoding='utf-8')
    return text, c, krit


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('korpus'); ap.add_argument('--out', default=None); ap.add_argument('--json', default=None)
    a = ap.parse_args(argv)
    if a.korpus.lower().endswith('.csv'):
        cases = lade_csv_korpus(a.korpus)
    else:
        data = json.loads(Path(a.korpus).read_text(encoding='utf-8'))
        cases = data.get('test_cases') if isinstance(data, dict) else data
    rows = [pruefe(c) for c in cases]
    text, c, krit = bericht(rows, a.korpus, a.out)
    if a.json:
        Path(a.json).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{len(rows)} Fälle: {c["PASS"]} PASS, {c["FAIL"]} FAIL, {c["NOT_TESTABLE"]} NOT_TESTABLE; kritische Falschfreigaben: {len(krit)}')
    if not a.out:
        print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
