r"""Prüft die Abnahmetabellen einer Spec auf Testdateien, die es nicht gibt (Bauweg 2026-10-25, Punkt 3): beim Entwurf, nicht erst bei der Abnahme.

    python benchmarks/spec_testnames.py docs/SPEC_AGENTEN_ORCHESTRIERUNG_v1.md [--lines 1240-1290] [--strict]

Gezählt wird jede Tabellenzeile, deren zweite Zelle mit einem Testdateinamen beginnt (`tests/test_x.py` oder `test_x.py`, auch mehrere, durch Komma getrennt).
Eine genannte Datei gilt als vorhanden, wenn sie unter tests/ liegt, wenn die Zeile `(neu)` enthält (sie wird mit dem Schritt gebaut) oder wenn der Name in
einer Zeile steht, die mit `Gebaut (` beginnt (die Zuordnung nach dem Bau). Alles andere ist ein Befund mit Zeilennummer.
Exit-Code 1 nur mit --strict und mindestens einem Befund."""
import argparse
import re
import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
TESTS = RUNTIME / 'tests'
NAME = re.compile(r'(?:tests/)?(test_\w+\.py)')


def findings(doc, first=1, last=None):
    lines = Path(doc).read_text(encoding='utf-8').splitlines()
    built = ' '.join(l for l in lines if l.startswith('Gebaut ('))
    out = []
    for number, line in enumerate(lines, 1):
        if number < first or (last is not None and number > last) or not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) < 2 or not cells[1].startswith('`'):
            continue
        names = NAME.findall(cells[1])
        # `test_a.py`, `test_b.py` und `test_a.py`, `_b.py` (Kurzform ohne Vorsilbe) – nur ganze Namen prüfen
        if '(neu)' in line:
            continue
        for name in names:
            if not (TESTS / name).is_file() and name not in built:
                out.append((number, name))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description='Testdateien der Abnahmetabellen einer Spec prüfen.')
    ap.add_argument('doc')
    ap.add_argument('--lines', help='Zeilenbereich, z. B. 1240-1290')
    ap.add_argument('--strict', action='store_true')
    args = ap.parse_args(argv)
    first, last = 1, None
    if args.lines:
        a, b = args.lines.split('-')
        first, last = int(a), int(b)
    found = findings(args.doc, first, last)
    for number, name in found:
        print(f'{args.doc}:{number}: {name} gibt es nicht (anlegen, `(neu)` in die Zeile oder in der Zeile `Gebaut (` zuordnen)')
    print(f'{len(found)} Befund(e)')
    return 1 if (found and args.strict) else 0


if __name__ == '__main__':
    sys.exit(main())
