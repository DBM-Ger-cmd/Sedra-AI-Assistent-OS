"""Sprache → Text (Kern): welcher Provider auf diesem Rechner da ist, seine Kommandozeile, sein Lauf. Rein bis auf `which` und `run`,
beide sind Parameter – die Tests geben Attrappen. Provider in dieser Reihenfolge: `whisperx` (m-bain/whisperX, BSD-2: faster-whisper,
Wort-Zeiten, VAD, CPU mit int8) und `whisper` (openai-whisper). Beide schreiben eine SRT; die wird ein Transkript.
Die Sprecher-Trennung von WhisperX (pyannote, Hugging-Face-Token, Netz) wird nicht aufgerufen – eine Entscheidung des Captains."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

SPRACHEN = ('de', 'en', 'fr', 'es', 'it')
TIMEOUT = 45 * 60
EINSTELLUNG_DATEI = 'sprache.stt.json'     # optional in <Projekt>/local_config: modell, geraet, rechenart, befehl
STANDARD = {'modell': 'small', 'geraet': 'cpu', 'rechenart': 'int8', 'befehl': ''}
MODELLE = ('tiny', 'base', 'small', 'medium', 'large-v2', 'large-v3')

# Name, ausführbare Datei, Installationsbefehl, Hinweis – Reihenfolge = Vorzug
PROVIDER = (
    ('whisperx', 'whisperx', 'pip install whisperx', 'WhisperX (m-bain/whisperX): faster-whisper, Wort-Zeiten, VAD; CPU mit int8 möglich.'),
    ('whisper', 'whisper', 'pip install -U openai-whisper', 'openai-whisper: die Referenz-Kommandozeile; langsamer, ohne Wort-Zeiten.'),
)


def einstellung(project_root):
    """Die optionale Einstellung aus local_config/sprache.stt.json; fehlende oder unbrauchbare Schlüssel bekommen den Standard."""
    p = Path(project_root) / 'local_config' / EINSTELLUNG_DATEI
    out = dict(STANDARD)
    try:
        roh = json.loads(p.read_text(encoding='utf-8')) if p.is_file() else {}
    except (OSError, ValueError):
        roh = {}
    if not isinstance(roh, dict): roh = {}
    for k in out:
        v = roh.get(k)
        if isinstance(v, str) and v.strip(): out[k] = v.strip()[:200]
    if out['modell'] not in MODELLE: out['modell'] = STANDARD['modell']
    if out['geraet'] not in ('cpu', 'cuda'): out['geraet'] = 'cpu'
    if out['rechenart'] not in ('int8', 'float16', 'float32'): out['rechenart'] = 'int8'
    return out


def provider_finden(which=shutil.which, e=None):
    """`bereit` nur, wenn Provider und ffmpeg ausführbar gefunden werden – sonst `platzhalter` mit Grund und Installationsbefehl."""
    e = dict(STANDARD, **(e or {}))
    ffmpeg = bool(which('ffmpeg'))
    grund = dict(e, ffmpeg=ffmpeg)
    for name, exe, install, hinweis in PROVIDER:
        eigener = e['befehl'] if e['befehl'] and Path(e['befehl']).stem == exe and which(e['befehl']) else None
        pfad = eigener or which(exe)
        if not pfad: continue
        if not ffmpeg:
            return dict(grund, status='platzhalter', provider=name, befehl=str(pfad), install='ffmpeg installieren (Paketverwaltung des Systems)',
                        note=hinweis + ' Aber ffmpeg fehlt – ohne ffmpeg kann der Provider webm/ogg/m4a nicht lesen.')
        return dict(grund, status='bereit', provider=name, befehl=str(pfad), install=install, note=hinweis)
    return dict(grund, status='platzhalter', provider='keiner', befehl='', install=PROVIDER[0][2],
                note='Kein Sprach-zu-Text-Provider auf diesem Rechner. SEDRA erkennt „whisperx“ (empfohlen) oder „whisper“ im PATH; '
                     'danach läuft die Transkription lokal. Bis dahin: Abschrift von Hand oder ein fertiges Transkript (TXT, SRT, VTT) importieren.')


def befehl(p, datei, sprache, ziel):
    """Die Kommandozeile (rein): SRT in den Zielordner, Sprache fest (LocalScribe: die Sprache ist eine Angabe des Captains, kein Raten)."""
    if sprache not in SPRACHEN: raise ValueError('sprache_unbekannt')
    exe = p.get('befehl') or p['provider']
    gemeinsam = [exe, str(datei), '--model', p['modell'], '--language', sprache, '--output_format', 'srt', '--output_dir', str(ziel), '--device', p['geraet']]
    if p['provider'] == 'whisperx':
        return gemeinsam + ['--compute_type', p['rechenart']]
    if p['provider'] == 'whisper':
        return gemeinsam + ['--fp16', 'False' if p['rechenart'] != 'float16' else 'True']
    raise ValueError('provider_unbekannt')


def srt_finden(ziel, stamm):
    """Die SRT des Providers: `<stamm>.srt` – oder die einzige SRT im Zielordner."""
    ziel = Path(ziel)
    p = ziel / (stamm + '.srt')
    if p.is_file(): return p
    srts = sorted(ziel.glob('*.srt'))
    return srts[0] if len(srts) == 1 else None


def transkribieren(p, datei, sprache, ziel, run=subprocess.run):
    """Der Lauf: der Provider schreibt die SRT nach `ziel`, zurück kommt ihr Text. Jeder Fehler ist ein ValueError mit dem Ende der Ausgabe."""
    if p.get('status') != 'bereit': raise ValueError('kein_provider')
    ziel = Path(ziel); ziel.mkdir(parents=True, exist_ok=True)
    cmd = befehl(p, datei, sprache, ziel)
    try:
        r = run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        raise ValueError('stt_zeitlimit')
    except OSError as exc:
        raise ValueError('stt_start_fehlgeschlagen: ' + str(exc)[:200])
    if r.returncode != 0:
        raise ValueError('stt_fehler: ' + (r.stderr or r.stdout or '')[-300:].strip())
    srt = srt_finden(ziel, Path(datei).stem)
    if srt is None: raise ValueError('stt_keine_ausgabe')
    text = srt.read_text(encoding='utf-8', errors='replace')
    if not text.strip(): raise ValueError('stt_leer')
    return text
