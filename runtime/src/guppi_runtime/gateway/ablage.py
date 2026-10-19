"""Die Ablage des GateWay nach der Spezifikation docs/SPEC_GATEWAY_ARBEITSSTRECKE_2026-10-19.md, Abschnitt 6 (Entscheidung 3):

    Eingang/             Originale, unverändert; je Original ein Vermerk (Begleitdatei *.vermerk.json)
    Eingang/Arbeitskopien/  Kopie eines Originals zum Bearbeiten
    Ausgang/             anonymisierte, geprüfte Fassungen mit Vermerk (Original, Prüfsumme, Vorgaben, Zeit)

Ein Original wird nie verändert oder gelöscht. Eine Ausgabe trägt immer den Vermerk: woher sie kommt, mit welcher Prüfsumme und
mit welchen Vorgaben. Der Text selbst steht nie im Vermerk. Dieses Modul liest und schreibt nur in diese drei Ordner."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

ENDUNGEN = ('.md', '.txt', '.docx')
MAX_BYTES = 2_000_000
ORIGINAL_HINWEIS = 'Original, nicht gesendet'


class AblageFehler(ValueError):
    pass


def ordner(root: Path) -> dict:
    """Die drei Ordner unter local_config/gateway; angelegt, wenn sie fehlen."""
    base = Path(root) / 'local_config' / 'gateway'
    out = {'eingang': base / 'eingang', 'arbeitskopien': base / 'eingang' / 'Arbeitskopien', 'ausgang': base / 'ausgang'}
    for p in out.values():
        p.mkdir(parents=True, exist_ok=True)
    return out


def sicherer_name(name: str) -> str:
    """Nur der Dateiname, mit erlaubter Endung. Pfade, versteckte Dateien und fremde Zeichen werden abgelehnt."""
    raw = str(name or '').strip()
    if '/' in raw or chr(92) in raw or '..' in raw: raise AblageFehler('name_ungueltig')     # ein Pfad wird nicht gekürzt, sondern abgelehnt
    name = Path(raw).name
    if not name or name.startswith('.') or not re.fullmatch(r'[\w\-. ()äöüÄÖÜß]{1,120}', name):
        raise AblageFehler('name_ungueltig')
    if Path(name).suffix.lower() not in ENDUNGEN:
        raise AblageFehler('dateityp_nicht_erlaubt')
    return name


def sha256_datei(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _jetzt() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')


def vermerk_pfad(original: Path) -> Path:
    return original.with_name(original.name + '.vermerk.json')


def original_vermerken(original: Path) -> dict:
    """Der Vermerk am Original: es bleibt unverändert, der Vermerk sagt, dass es nicht gesendet wurde."""
    original = Path(original)
    eintrag = {'art': 'original', 'name': original.name, 'sha256': sha256_datei(original), 'hinweis': ORIGINAL_HINWEIS, 'angelegt': _jetzt()}
    vermerk_pfad(original).write_text(json.dumps(eintrag, ensure_ascii=False, indent=2), encoding='utf-8')
    return eintrag


def arbeitskopie(root: Path, name: str) -> Path:
    """Eine Kopie des Originals im Ordner Arbeitskopien. Das Original bleibt, wo es ist."""
    name = sicherer_name(name)
    d = ordner(root)
    quelle = d['eingang'] / name
    if not quelle.is_file():
        raise AblageFehler('original_nicht_gefunden')
    if quelle.stat().st_size > MAX_BYTES:
        raise AblageFehler('datei_zu_gross')
    original_vermerken(quelle)
    ziel = d['arbeitskopien'] / name
    shutil.copy2(quelle, ziel)
    return ziel


def speichern_unter(root: Path, quelle_name: str, text: str, ziel_name: str, vorgaben: list) -> dict:
    """Die bearbeitete Fassung in den Ausgang schreiben, unter einem neuen Namen. Das Original wird nicht angefasst.

    `vorgaben`: die angewendeten Vorgaben als Liste (Art, Fundstelle, Platzhalter) – ohne den Originaltext.
    Gibt den Vermerk zurück: Dateiname, Prüfsumme des Originals, Vorgaben, Zeit."""
    quelle_name = sicherer_name(quelle_name)
    ziel_name = sicherer_name(ziel_name)
    d = ordner(root)
    original = d['eingang'] / quelle_name
    if not original.is_file():
        raise AblageFehler('original_nicht_gefunden')
    if (d['ausgang'] / ziel_name).exists():            # eine Ausgabe wird nie stillschweigend ersetzt
        raise AblageFehler('ziel_existiert')
    if not isinstance(text, str) or not text.strip():
        raise AblageFehler('text_leer')
    if len(text.encode('utf-8')) > MAX_BYTES:
        raise AblageFehler('text_zu_gross')
    ziel = d['ausgang'] / ziel_name
    ziel.write_text(text, encoding='utf-8')
    vermerk = {'art': 'ausgang', 'name': ziel_name, 'aus_original': original.name, 'original_sha256': sha256_datei(original),
               'vorgaben': [dict(v) for v in (vorgaben or []) if isinstance(v, dict)][:200],
               'hinweis': 'anonymisiert und geprüft – bereit zur Verarbeitung mit externen Quellen', 'angelegt': _jetzt()}
    vermerk_pfad(ziel).write_text(json.dumps(vermerk, ensure_ascii=False, indent=2), encoding='utf-8')
    return vermerk
