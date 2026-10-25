"""Hilfe für Abnahmetests gegen `src` (Bauweg 2026-10-25, Punkt 2): die versteckten Tests der letzten Stufe einer devvm-Spec laufen gegen den
übernommenen Code, nicht gegen den Kandidaten des Baus.

Die Module werden in einen temporären Ordner kopiert; nur die relativen Importe werden zu einfachen Namen (wie die Specs sie brauchen). Jede
versteckte Datei läuft als `python <datei>` mit diesem Ordner als Arbeitsordner, Exit-Code 0 = bestanden. Abweichungen von den versteckten Tests
(spätere Specs, die den Bau-Spec nicht kannte) stehen ausdrücklich in `known` mit Grund: (Datei, Muster, Ersatz, Grund)."""
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]


def plain_imports(text):
    text = re.sub(r'^from \. import ', 'import ', text, flags=re.M)
    return re.sub(r'^from \.(\w+) import ', r'from \1 import ', text, flags=re.M)


def last_stage(spec):
    path = RUNTIME / 'benchmarks' / 'devvm_specs' / f'{spec}.py'
    loader = importlib.util.spec_from_file_location(f'spec_{spec}', path)
    module = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(module)
    return module.STAGES[-1]['hidden']


def plain_tree(folder, modules, into):
    for name in modules:
        source = (Path(folder) / f'{name}.py').read_text(encoding='utf-8')
        (Path(into) / f'{name}.py').write_text(plain_imports(source), encoding='utf-8')


def run_hidden(spec, tree, modules, known=(), timeout=300):
    """{datei: (returncode, ende der Ausgabe)} für die versteckten Tests der letzten Stufe von `spec` gegen die Module in `tree`."""
    results = {}
    for name, code in last_stage(spec).items():
        with tempfile.TemporaryDirectory(prefix='hidden-') as work:
            for module in modules:
                (Path(work) / f'{module}.py').write_text((Path(tree) / f'{module}.py').read_text(encoding='utf-8'), encoding='utf-8')
            for file, pattern, replacement, _reason in known:
                if file == name:
                    code = re.sub(pattern, replacement, code)
            (Path(work) / name).write_text(code, encoding='utf-8')
            env = {**os.environ, 'PYTHONPATH': work}
            done = subprocess.run([sys.executable, name], cwd=work, env=env, capture_output=True, text=True, timeout=timeout)
            results[name] = (done.returncode, (done.stderr or done.stdout)[-600:])
    return results
