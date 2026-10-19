"""Ein fremdes Modul einbauen – immer über ein Gate (SHELL_WERKZEUG_VERTRAG_v1 §6 „Installation“, §7).

Was der Captain vor der Freigabe sieht, steht hier: das Manifest, jede Datei mit ihrer Größe und ihrem SHA-256, und was die
Durchsicht gefunden hat. Geprüft wird auf das, was die Allowlist *nicht* abfangen kann, weil es am `ctx.api` vorbeigeht:

    eval / new Function          Code, der erst zur Laufzeit entsteht
    fetch / XMLHttpRequest       ein eigener Weg ins Netz, an der Allowlist vorbei
    import(…) von außerhalb      Nachladen aus fremden Quellen
    localStorage                 Speicher der Shell; das Layout gehört ihr, nicht dem Werkzeug
    document.write / innerHTML   Markup aus Daten – der Weg zu fremdem Code im eigenen Fenster

Ein Fund ist kein Urteil: er steht im Gate, der Captain entscheidet. Nur `CORE` kann ein fremdes Modul nie werden, und ein
`COMMUNITY`-Modul bekommt vom Gateway ohnehin nur Leserouten.

Dieses Modul schreibt nichts. Es liest einen Ordner, prüft und beschreibt; das Kopieren macht der Hub nach der Freigabe."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

MAX_FILES = 60
MAX_BYTES = 2_000_000
ALLOWED_SUFFIX = {'.js', '.css', '.yaml', '.json', '.md', '.svg', '.png', '.html'}

FLAGS = (
    ('eval', re.compile(r'\beval\s*\(')),
    ('new Function', re.compile(r'new\s+Function\s*\(')),
    ('fetch', re.compile(r'(?<![.\w])fetch\s*\(')),
    ('XMLHttpRequest', re.compile(r'\bXMLHttpRequest\b')),
    ('EventSource', re.compile(r'\bEventSource\b')),
    ('import()', re.compile(r'\bimport\s*\(')),
    ('localStorage', re.compile(r'\blocalStorage\b')),
    ('document.write', re.compile(r'\bdocument\.write\b')),
    ('innerHTML', re.compile(r'\binnerHTML\b')),
    ('fremde Adresse', re.compile(r'https?://(?!127\.0\.0\.1|localhost)')),
    # Stufe B der Modul-Isolation (Plan 2026-10-19): der Kern-Zugang, die Adresse mit dem Token, Cookies und das Elternfenster
    ('sedraApi', re.compile(r'\bsedraApi\b')),
    ('location', re.compile(r'\blocation\s*\.\s*(hash|href|search)\b')),
    ('document.cookie', re.compile(r'\bdocument\s*\.\s*cookie\b')),
    ('window.parent/top', re.compile(r'\bwindow\s*\.\s*(parent|top|opener)\b|\b(parent|top)\s*\.\s*(postMessage|location|document)\b')),
    ('window[...]', re.compile(r'\bwindow\s*\[')),
    ('sessionStorage', re.compile(r'\bsessionStorage\b')),
)

FLAG_WORD = {
    'eval': 'baut Code zur Laufzeit zusammen',
    'new Function': 'baut Code zur Laufzeit zusammen',
    'fetch': 'geht an der Allowlist vorbei ins Netz',
    'XMLHttpRequest': 'geht an der Allowlist vorbei ins Netz',
    'EventSource': 'öffnet einen eigenen Ereignisstrom',
    'import()': 'lädt Code nach',
    'localStorage': 'schreibt in den Speicher der Shell',
    'document.write': 'schreibt Markup in die Seite',
    'innerHTML': 'setzt Markup aus Daten zusammen',
    'fremde Adresse': 'nennt eine Adresse außerhalb dieses Rechners',
    'sedraApi': 'greift auf den Kern-Zugang der Oberfläche zu (Token, fremde Kennungen)',
    'location': 'liest die Adresse, in der der Token steht',
    'document.cookie': 'liest oder schreibt Cookies der Seite',
    'window.parent/top': 'greift über das eigene Fenster hinaus',
    'window[...]': 'greift dynamisch auf Fensterwerte zu, nicht prüfbar',
    'sessionStorage': 'schreibt in den Sitzungsspeicher der Shell',
}


def inside(base: Path, path: Path):
    """Ob `path` wirklich unter `base` liegt: kein Teil des Weges darf eine Verknüpfung sein, und aufgelöst muss er drinbleiben."""
    base, path = Path(base).resolve(), Path(path)
    step = path
    while step != base and step.parent != step:
        if step.is_symlink():
            return False
        step = step.parent
    try:
        return path.resolve().is_relative_to(base)
    except (OSError, ValueError):
        return False


def sha256(path: Path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def is_comment(line):
    """Ob diese Zeile nur Kommentar ist – und zwar so, dass sich dahinter nichts verstecken lässt.

    Härtung: `*/ eval(x)` beginnt mit `*` und ist trotzdem Code. Eine Fortsetzungszeile zählt deshalb nur als Kommentar,
    solange der Block auf ihr nicht endet. Nach `//` wird nicht abgeschnitten: in `'https://…'` steckt der Fund selbst."""
    stripped = line.lstrip()
    if stripped.startswith('//'):
        return True
    if stripped.startswith(('*', '/*')):
        end = stripped.find('*/')
        return end < 0 or not stripped[end + 2:].strip()
    return False


def scan_text(text, name=''):
    """Die Funde einer Datei: [{flag, zeile, text, warum}] – die Zeile steht dabei, damit der Captain sie lesen kann."""
    out = []
    for number, line in enumerate(text.splitlines(), 1):
        if is_comment(line):
            continue                                    # ein Kommentar, der ein Wort erwähnt, ist kein Fund
        for flag, pattern in FLAGS:
            if pattern.search(line):
                out.append({'flag': flag, 'file': name, 'line': number, 'text': line.strip()[:160],
                            'warum': FLAG_WORD.get(flag, '')})
    return out


def read_module(folder: Path, kind='tools'):
    """Liest einen Modulordner: Dateien, Hashes, Funde. Wirft, wenn schon die Form nicht stimmt."""
    folder = Path(folder)
    if not folder.is_dir():
        raise ValueError('module_folder_not_found')
    manifest_name = 'tool.yaml' if kind == 'tools' else 'shell.yaml'
    if not (folder / manifest_name).is_file():
        raise ValueError(f'{manifest_name}_missing')
    files, findings, total = [], [], 0
    base = folder.resolve()
    # Härtung: eine Verknüpfung – auch eine auf einen Ordner – wird abgewiesen, nicht stumm übergangen. `rglob` steigt in
    # verknüpfte Ordner gar nicht hinab; ohne diese Prüfung fehlten die Dateien im Gate, ohne dass es jemand merkt.
    for entry in sorted(folder.rglob('*')):
        if entry.is_symlink():
            raise ValueError('symlink_refused:' + entry.relative_to(folder).as_posix())
    for path in sorted(p for p in folder.rglob('*') if p.is_file()):
        rel = path.relative_to(folder).as_posix()
        if '..' in rel or any(part.startswith('.') for part in rel.split('/')):
            raise ValueError('unexpected_path:' + rel)
        # Härtung: eine Verknüpfung zeigt aus dem Modul heraus. Sonst käme beim Einbau eine fremde Datei mit – und das
        # Gateway würde sie ausliefern, weil sie auf `.js` endet. Geprüft wird jeder Teil des Pfades, nicht nur die Datei.
        if not inside(base, path):
            raise ValueError('symlink_refused:' + rel)
        if path.suffix.lower() not in ALLOWED_SUFFIX:
            raise ValueError('unexpected_file_type:' + rel)
        size = path.stat().st_size
        total += size
        if len(files) >= MAX_FILES or total > MAX_BYTES:
            raise ValueError('module_too_large')
        files.append({'path': rel, 'bytes': size, 'sha256': sha256(path)})
        if path.suffix.lower() in ('.js', '.html'):
            findings.extend(scan_text(path.read_text(encoding='utf-8', errors='replace'), rel))
    return {'files': files, 'findings': findings, 'bytes': total}


def summary(findings):
    """Ein Satz über die Durchsicht – ohne zu urteilen, aber ohne zu beschönigen."""
    if not findings:
        return 'Die Durchsicht hat nichts gefunden, was an der Allowlist vorbeiginge.'
    flags = sorted({f['flag'] for f in findings})
    return ('Die Durchsicht hat ' + str(len(findings)) + ' Stelle(n) gefunden: ' + ', '.join(flags)
            + '. Das ist kein Urteil – sieh sie dir an, bevor du freigibst.')
