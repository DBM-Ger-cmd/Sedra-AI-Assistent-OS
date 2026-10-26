r"""Ein Befehl für die Tests der Runtime (Bauweg 2026-10-25, Punkt 1): Pfad einrichten, Bereich oder geänderte Dateien wählen, parallel laufen, gegen die Liste
der bekannten roten Tests vergleichen. Nur NEUE Fehlschläge machen den Lauf rot.

    python benchmarks/run_tests.py orchestra            # ein Bereich (siehe AREAS), ohne die langsamen Browser-Tests
    python benchmarks/run_tests.py --changed            # nur Tests, die zu den geänderten Dateien passen (gegen HEAD, dazu unversioniert)
    python benchmarks/run_tests.py --changed --base origin/spec/agenten-orchestrierung    # gegen einen Stand
    python benchmarks/run_tests.py all --slow           # alles, auch die Browser-Bahn (test_uix_*)
    python benchmarks/run_tests.py test_orchestra_run test_orchestra_tick                 # einzelne Dateien
    python benchmarks/run_tests.py all --jobs 6 --update-known                            # Liste der bekannten roten Tests neu schreiben (nur mit Absicht)

Bahnen: `fast` (Standard) lässt die Tests aus, die einen Browser starten (SLOW_FILES); `--slow` nimmt sie dazu.
Bekannte rote Tests stehen in tests/known_red.txt (eine Test-Kennung je Zeile, `#` Kommentar, Grund dahinter); ein Test dort, der grün wird,
wird gemeldet, damit die Zeile verschwindet. Exit-Code 0, wenn es keinen neuen Fehlschlag gibt."""
import argparse
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
TESTS = RUNTIME / 'tests'
KNOWN = TESTS / 'known_red.txt'
AREAS = {
    'orchestra': ('test_orchestra_*', 'test_guard_standing', 'test_desk_gated', 'test_desk_decisions', 'test_job_*', 'test_wissen_desk'),
    'desk': ('test_desk_*', 'test_orchestra_desk', 'test_orchestra_messages', 'test_orchestra_hire'),
    'scheduler': ('test_model_scheduler*', 'test_slot*', 'test_vramplan*', 'test_testlab', 'test_job_*', 'test_role_routing', 'test_model_loader'),
    'wissen': ('test_wissen_*',),
    'uix': ('test_uix_*',),
}
SLOW_FILES = ('test_uix_browser', 'test_uix_flows', 'test_uix_shell_start', 'test_uix_kommandodeck', 'test_uix_rekorder')   # starten einen Browser


def all_files():
    return sorted(p.stem for p in TESTS.glob('test_*.py'))


def match(patterns):
    from fnmatch import fnmatch
    return [f for f in all_files() if any(fnmatch(f, pat) for pat in patterns)]


def known_red():
    if not KNOWN.is_file():
        return set()
    out = set()
    for line in KNOWN.read_text(encoding='utf-8').splitlines():
        line = line.split('#', 1)[0].strip()
        if line:
            out.add(line)
    return out


def changed_files(base):
    names = set()
    for cmd in (['git', 'diff', '--name-only', base], ['git', 'ls-files', '--others', '--exclude-standard']):
        done = subprocess.run(cmd, cwd=RUNTIME, capture_output=True, text=True)
        names.update(l.strip() for l in done.stdout.splitlines() if l.strip())
    return sorted(names)


def tests_for_changes(base):
    """Test-Dateien, die selbst geändert wurden, und Test-Dateien, die den Namen eines geänderten Quellmoduls nennen."""
    files = changed_files(base)
    stems = set()
    chosen = set()
    for name in files:
        path = Path(name)
        if path.suffix != '.py' and path.suffix != '.js' and path.suffix != '.yaml':
            continue
        if path.parent.name == 'tests' and path.stem.startswith('test_'):
            chosen.add(path.stem)
        elif 'src' in path.parts or 'config' in path.parts or 'benchmarks' in path.parts or 'uix' in path.parts:
            stems.add(path.parent.name if path.stem in ('tool', 'test', '__init__') else path.stem)
    texts = {f: (TESTS / f'{f}.py').read_text(encoding='utf-8', errors='replace') for f in all_files()}
    for stem in stems:
        word = re.compile(r'\b' + re.escape(stem) + r'\b')
        chosen.update(f for f, text in texts.items() if word.search(text))
    return sorted(chosen), files


LOADER = """
import sys, unittest
loader, suite, skipped = unittest.TestLoader(), unittest.TestSuite(), []
for name in sys.argv[1:]:
    try:
        suite.addTests(loader.loadTestsFromName(name))
    except unittest.SkipTest:                    # ein Modul, das sich beim Import überspringt (fehlende Abhängigkeit)
        skipped.append(name)
result = unittest.TextTestRunner(verbosity=1, stream=sys.stderr).run(suite)
print('MODULE_SKIPPED:', ' '.join(skipped), file=sys.stderr)
sys.exit(0 if result.wasSuccessful() else 1)
"""


def python_exe(browser=False):
    """Die `.venv` der Runtime, wenn es sie gibt (mit dulwich, microsandbox u. a.: dann laufen auch die DevVM-Tests), sonst der laufende Python.
    Die Browser-Bahn (SLOW_FILES) braucht `playwright`; hat die `.venv` es nicht, läuft sie unter dem laufenden Python."""
    if browser:
        for rel in ('.venv/Scripts/python.exe', '.venv/bin/python'):
            candidate = RUNTIME / rel
            if candidate.is_file():
                has = subprocess.run([str(candidate), '-c', 'import playwright'], capture_output=True).returncode == 0
                return str(candidate) if has else sys.executable
        return sys.executable
    for rel in ('.venv/Scripts/python.exe', '.venv/bin/python'):
        candidate = RUNTIME / rel
        if candidate.is_file():
            return str(candidate)
    return sys.executable


def run_group(modules, timeout):
    env = {**os.environ, 'PYTHONPATH': os.pathsep.join([str(RUNTIME / 'src'), str(TESTS)])}
    started = time.monotonic()
    done = subprocess.run([python_exe(any(m in SLOW_FILES for m in modules)), '-c', LOADER, *modules], cwd=RUNTIME, env=env, capture_output=True, text=True,
                          encoding='utf-8', errors='replace', timeout=timeout)
    text = (done.stderr or '') + (done.stdout or '')
    failed = set(re.findall(r'^(?:FAIL|ERROR): .*?\(([\w.]+)\)', text, flags=re.M))
    ran = re.search(r'^Ran (\d+) tests?', text, flags=re.M)
    skipped = re.search(r'skipped=(\d+)', text)
    module_skipped = re.search(r'^MODULE_SKIPPED:(.*)$', text, flags=re.M)
    return {'modules': modules, 'module_skipped': module_skipped.group(1).split() if module_skipped else [], 'failed': failed, 'ran': int(ran.group(1)) if ran else 0, 'skipped': int(skipped.group(1)) if skipped else 0,
            'seconds': time.monotonic() - started, 'text': text, 'code': done.returncode}


def split(modules, jobs):
    groups = [[] for _ in range(max(1, min(jobs, len(modules))))]
    # grobe Gleichverteilung nach Dateigröße (Größe ~ Laufzeit); große zuerst
    sized = sorted(modules, key=lambda m: -(TESTS / f'{m}.py').stat().st_size)
    loads = [0] * len(groups)
    for module in sized:
        i = loads.index(min(loads))
        groups[i].append(module)
        loads[i] += (TESTS / f'{module}.py').stat().st_size
    return [g for g in groups if g]


def main(argv=None):
    ap = argparse.ArgumentParser(description='Tests der Runtime: Bereich, geänderte Dateien, parallel, gegen bekannte rote Tests.')
    ap.add_argument('targets', nargs='*', help='Bereich (' + ', '.join(sorted(AREAS)) + ', all) oder Testdateien ohne .py')
    ap.add_argument('--changed', action='store_true', help='nur Tests zu geänderten Dateien')
    ap.add_argument('--base', default='HEAD', help='Stand für --changed (Standard HEAD)')
    ap.add_argument('--slow', action='store_true', help='auch die Browser-Bahn')
    ap.add_argument('--jobs', type=int, default=max(1, min(6, (os.cpu_count() or 2) // 2)))
    ap.add_argument('--timeout', type=int, default=1800)
    ap.add_argument('--update-known', action='store_true', help='tests/known_red.txt aus diesem Lauf schreiben')
    ap.add_argument('--list', action='store_true', help='nur die gewählten Dateien zeigen')
    args = ap.parse_args(argv)
    modules, why = [], ''
    if args.changed:
        modules, files = tests_for_changes(args.base)
        why = f'{len(files)} geänderte Dateien gegen {args.base}'
    for target in args.targets:
        if target == 'all':
            modules += all_files()
        elif target in AREAS:
            modules += match(AREAS[target])
        elif (TESTS / f'{target}.py').is_file():
            modules.append(target)
        else:
            ap.error(f'unbekannt: {target}')
    if not args.targets and not args.changed:
        ap.error('Bereich, Dateien oder --changed angeben')
    modules = sorted(set(modules))
    if not args.slow and not any(t in SLOW_FILES for t in args.targets):
        skipped_slow = [m for m in modules if m in SLOW_FILES]
        modules = [m for m in modules if m not in SLOW_FILES]
    else:
        skipped_slow = []
    print(f'{len(modules)} Testdateien' + (f' ({why})' if why else '') + (f', Browser-Bahn ausgelassen: {len(skipped_slow)}' if skipped_slow else ''))
    if args.list or not modules:
        print('\n'.join(modules))
        return 0
    groups = split(modules, args.jobs)
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=len(groups)) as pool:
        results = list(pool.map(lambda g: run_group(g, args.timeout), groups))
    failed = set().union(*(r['failed'] for r in results))
    ran, skipped = sum(r['ran'] for r in results), sum(r['skipped'] for r in results)
    crashed = [r for r in results if r['code'] != 0 and not r['failed'] and r['ran'] == 0]
    known = known_red()
    new = sorted(failed - known)
    still = sorted(failed & known)
    healed = sorted(k for k in known - failed if any(k.split('.')[0] == m for m in modules))
    module_skipped = [m for r in results for m in r['module_skipped']]
    if module_skipped:
        print(f'{len(module_skipped)} Dateien übersprungen (Importabbruch, z. B. fehlende Abhängigkeit):', *module_skipped, sep=chr(10) + '  ')
    print(f'{ran} Tests, {skipped} übersprungen, {len(failed)} rot, {time.monotonic() - started:.0f} s ({len(groups)} Gruppen parallel)')
    for r in crashed:
        print('GRUPPE OHNE ERGEBNIS (Importfehler?):', ' '.join(r['modules']))
        print(r['text'][-1500:])
    if still:
        print(f'bekannt rot ({len(still)}):', *still, sep='\n  ')
    if healed:
        print(f'bekannt rot, jetzt grün ({len(healed)}) – Zeile in tests/known_red.txt streichen:', *healed, sep='\n  ')
    if new:
        print(f'NEU ROT ({len(new)}):', *new, sep='\n  ')
        for r in results:
            if r['failed'] - known:
                print('-' * 70)
                print(r['text'][-3000:])
    if args.update_known:
        KNOWN.write_text('# Bekannt rote Tests (Stand ' + time.strftime('%Y-%m-%d') + '); `#` beginnt einen Grund. Nur mit Absicht erneuern.\n'
                         + '\n'.join(sorted(failed)) + '\n', encoding='utf-8')
        print('tests/known_red.txt geschrieben')
        return 0
    return 1 if (new or crashed) else 0


if __name__ == '__main__':
    sys.exit(main())
