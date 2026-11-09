"""Der Eingang des Wissens: Dateien per Ziehen oder per Windows-Dialog ins Projekt holen, damit sie eine Quelle werden können.

Ein Browser reicht beim Ziehen nie den Pfad weiter, nur den Inhalt. Deshalb landen gezogene Dateien (in Teilstücken unter dem 1-MB-Limit der
Anfragen) in `local_config/wissen/eingang/<Sitzung>/` im Projekt. Dasselbe Ziel hat der Windows-Dialog: er liefert Pfade, die Dateien werden
kopiert. Danach ist der Eingang eine Quelle der Wurzel `projekt` und geht den gewohnten Weg: Antrag im Posteingang, Freigabe, Aufnahme.
Dieses Modul nimmt nichts auf und gibt nichts frei. Nur Dateiarten, die der Adapter `dokumente` liest; Größen je Art aus der Konfiguration."""
from __future__ import annotations

import base64
import binascii
import re
import secrets
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath

EINGANG = ("local_config", "wissen", "eingang")
ARTEN = (".md", ".txt", ".docx", ".csv", ".pdf", ".xlsx", ".pptx")
MUSTER = ",".join("*" + a for a in ARTEN)
SITZUNG = re.compile(r"E-\d{8}-\d{6}-[0-9a-f]{4}")
MAX_DATEIEN = 500
MAX_GESAMT = 300 * 1024 * 1024
MAX_TEIL = 700 * 1024                      # Bytes je Teilstück, Base64 bleibt damit unter 1 MB
AUSGELASSEN = {".git", "node_modules", "__pycache__", ".venv", "$RECYCLE.BIN", "System Volume Information"}
RESERVIERT = {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)} | {f"lpt{i}" for i in range(1, 10)}


# die deutschen Sätze zu den Fehlercodes (speicher.SAETZE nimmt sie auf)
SAETZE = {
    "wis_eingang_sitzung_ungueltig": "Der Eingang ist unbekannt; bitte noch einmal von vorn hinzufügen.",
    "wis_eingang_name_ungueltig": "Ein Dateiname ist nicht erlaubt (nur einfache Namen, keine Laufwerke und keine Sonderzeichen).",
    "wis_eingang_daten_ungueltig": "Die übertragenen Daten sind ungültig.",
    "wis_eingang_teil_zu_gross": "Ein Teilstück der Datei ist zu groß.",
    "wis_eingang_offset_ungueltig": "Die Datei kam in falscher Reihenfolge an; bitte noch einmal ziehen.",
    "wis_eingang_datei_zu_gross": "Eine Datei ist größer als erlaubt und wurde nicht übernommen.",
    "wis_eingang_zu_viele_dateien": "Das sind mehr als 500 Dateien auf einmal; bitte in kleineren Teilen hinzufügen.",
    "wis_eingang_zu_gross": "Das ist mehr als 300 MB auf einmal; bitte in kleineren Teilen hinzufügen.",
    "wis_eingang_leer": "Im Eingang liegt nichts, was das Wissen lesen kann (Markdown, Text, Word, CSV, PDF, Excel, PowerPoint).",
    "wis_dialog_art_ungueltig": "Der Dialog kennt nur Ordner oder Dateien.",
    "wis_dialog_nur_windows": "Der Auswahldialog gibt es nur unter Windows; bitte die Dateien ins Fenster ziehen.",
    "wis_dialog_zeit": "Im Auswahldialog wurde nichts gewählt.",
    "wis_dialog_fehlt": "Der Auswahldialog konnte nicht gestartet werden.",
    "wis_dialog_fehlgeschlagen": "Der Auswahldialog hat nicht geantwortet.",
}


def _fehler(code):
    return ValueError(code)


def basis(projekt_root):
    return Path(projekt_root).joinpath(*EINGANG)


def neue_sitzung():
    return "E-" + datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(2)


def ordner(projekt_root, sitzung):
    if not isinstance(sitzung, str) or not SITZUNG.fullmatch(sitzung):
        raise _fehler("wis_eingang_sitzung_ungueltig")
    return basis(projekt_root) / sitzung


def rel_pfad(projekt_root, sitzung):
    """Der Pfad der Quelle relativ zum Projekt, mit '/' (für die Bindung)."""
    ordner(projekt_root, sitzung)
    return "/".join(EINGANG) + "/" + sitzung


def sauberer_name(name):
    """Relativer Dateiname mit '/' ohne '..', Laufwerk, reservierte Namen und Sonderzeichen; sonst `wis_eingang_name_ungueltig`."""
    roh = str(name or "").replace("\\", "/")
    if not roh or roh.startswith("/") or roh.endswith("/") or len(roh) > 240 or re.match(r"^[A-Za-z]:", roh):
        raise _fehler("wis_eingang_name_ungueltig")
    teile = []
    for teil in PurePosixPath(roh).parts:
        if teil in ("", ".", "..") or len(teil) > 120 or re.search(r'[<>:"|?*\x00-\x1f]', teil) or teil.rstrip(" .") != teil:
            raise _fehler("wis_eingang_name_ungueltig")
        if teil.split(".")[0].lower() in RESERVIERT:
            raise _fehler("wis_eingang_name_ungueltig")
        teile.append(teil)
    if PurePosixPath(teile[-1]).suffix.lower() not in ARTEN:
        raise _fehler("wis_dateiart_nicht_erlaubt")
    return "/".join(teile)


def grenze(konfig, endung):
    je = getattr(konfig, "je_art", None) or {}
    return int(je.get(endung.lstrip(".").lower(), getattr(konfig, "datei_max_bytes", 2_000_000)))


def _gesamt(ziel):
    return sum(p.stat().st_size for p in ziel.rglob("*") if p.is_file()) if ziel.is_dir() else 0


def _anzahl(ziel):
    return sum(1 for p in ziel.rglob("*") if p.is_file()) if ziel.is_dir() else 0


def ablegen(projekt_root, konfig, *, sitzung, name, offset, daten, ende=False):
    """Ein Teilstück einer gezogenen Datei anhängen. `offset` muss genau der bisherigen Länge entsprechen (Wiederholung ist erkennbar)."""
    ziel_ordner = ordner(projekt_root, sitzung)
    rel = sauberer_name(name)
    try:
        teil = base64.b64decode(str(daten or ""), validate=True)
    except (binascii.Error, ValueError):
        raise _fehler("wis_eingang_daten_ungueltig") from None
    if len(teil) > MAX_TEIL:
        raise _fehler("wis_eingang_teil_zu_gross")
    ziel = ziel_ordner.joinpath(*rel.split("/"))
    if type(offset) is not int or offset < 0:
        raise _fehler("wis_eingang_offset_ungueltig")
    bisher = ziel.stat().st_size if ziel.is_file() else 0
    if offset != bisher:
        raise _fehler("wis_eingang_offset_ungueltig")
    if bisher + len(teil) > grenze(konfig, PurePosixPath(rel).suffix):
        if ziel.is_file():
            ziel.unlink()
        raise _fehler("wis_eingang_datei_zu_gross")
    if offset == 0 and not ziel.exists() and _anzahl(ziel_ordner) >= MAX_DATEIEN:
        raise _fehler("wis_eingang_zu_viele_dateien")
    if _gesamt(ziel_ordner) + len(teil) > MAX_GESAMT:
        raise _fehler("wis_eingang_zu_gross")
    ziel.parent.mkdir(parents=True, exist_ok=True)
    with open(ziel, "ab" if offset else "wb") as f:
        f.write(teil)
    return {"name": rel, "bytes": bisher + len(teil), "ende": bool(ende)}


def stand(projekt_root, sitzung):
    ziel = ordner(projekt_root, sitzung)
    return {"eingang": rel_pfad(projekt_root, sitzung), "dateien": _anzahl(ziel), "bytes": _gesamt(ziel), "muster": MUSTER}


def verwerfen(projekt_root, sitzung):
    ziel = ordner(projekt_root, sitzung)
    if ziel.is_dir():
        shutil.rmtree(ziel)
    return {"verworfen": True}


def kopieren(projekt_root, konfig, pfade, sitzung):
    """Dateien und Ordner, die der Dialog geliefert hat, in den Eingang kopieren. Links werden übersprungen, ebenso fremde Dateiarten,
    zu große Dateien und alles über der Zahl- und Größenbremse. Gibt Zähler und die Gründe zurück."""
    ziel_ordner = ordner(projekt_root, sitzung)
    kopiert, uebersprungen = 0, {"art": 0, "gross": 0, "link": 0, "limit": 0}
    gesamt = _gesamt(ziel_ordner)
    quellen = []
    for roh in pfade:
        p = Path(roh)
        if not p.exists():
            continue
        if p.is_file():
            quellen.append((p, p.name))
            continue
        for q in sorted(p.rglob("*")):
            rel = q.relative_to(p)
            if any(t in AUSGELASSEN or t.startswith(".") for t in rel.parts[:-1]):
                continue
            if q.is_file() or q.is_symlink():
                quellen.append((q, (p.name + "/" + rel.as_posix())))
    for q, name in quellen:
        if q.is_symlink() or getattr(q, "is_junction", lambda: False)():
            uebersprungen["link"] += 1
            continue
        if q.suffix.lower() not in ARTEN:
            uebersprungen["art"] += 1
            continue
        try:
            rel = sauberer_name(name)
            groesse = q.stat().st_size
        except (ValueError, OSError):
            uebersprungen["art"] += 1
            continue
        if groesse > grenze(konfig, q.suffix):
            uebersprungen["gross"] += 1
            continue
        if kopiert >= MAX_DATEIEN or gesamt + groesse > MAX_GESAMT:
            uebersprungen["limit"] += 1
            continue
        ziel = ziel_ordner.joinpath(*rel.split("/"))
        ziel.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(q, ziel)
        kopiert += 1
        gesamt += groesse
    return {"kopiert": kopiert, "uebersprungen": uebersprungen}


_PS = r"""
Add-Type -AssemblyName System.Windows.Forms
$h = New-Object System.Windows.Forms.Form
$h.TopMost = $true; $h.ShowInTaskbar = $false; $h.StartPosition = 'CenterScreen'; $h.Size = New-Object System.Drawing.Size(1,1); $h.Opacity = 0
$h.Show(); $h.Activate()
if ($env:SEDRA_DIALOG -eq 'ordner') {
  $d = New-Object System.Windows.Forms.FolderBrowserDialog
  $d.Description = 'Ordner für das Wissen von SEDRA wählen'
  $d.ShowNewFolderButton = $false
  if ($d.ShowDialog($h) -eq 'OK') { $out = @($d.SelectedPath) } else { $out = @() }
} else {
  $d = New-Object System.Windows.Forms.OpenFileDialog
  $d.Title = 'Dateien für das Wissen von SEDRA wählen'
  $d.Multiselect = $true
  $d.Filter = 'Wissensdateien|*.md;*.txt;*.docx;*.csv;*.pdf;*.xlsx;*.pptx|Alle Dateien|*.*'
  if ($d.ShowDialog($h) -eq 'OK') { $out = $d.FileNames } else { $out = @() }
}
$h.Close()
$text = ($out -join "`n")
[Console]::Out.Write([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($text)))
"""


def dialog(art, *, zeit_s=300, laufen=subprocess.run):
    """Der Windows-Dialog (Ordner oder Dateien) in einem eigenen Prozess mit STA. Gibt die gewählten Pfade zurück, leer bei Abbruch.
    Nur unter Windows; der Dialog öffnet sich auf dem Rechner, auf dem SEDRA läuft."""
    if art not in ("ordner", "dateien"):
        raise _fehler("wis_dialog_art_ungueltig")
    if sys.platform != "win32":
        raise _fehler("wis_dialog_nur_windows")
    import os
    env = dict(os.environ, SEDRA_DIALOG=art)
    try:
        r = laufen(["powershell.exe", "-NoProfile", "-NonInteractive", "-STA", "-ExecutionPolicy", "Bypass", "-Command", _PS],
                   capture_output=True, text=True, env=env, timeout=zeit_s)
    except subprocess.TimeoutExpired:
        raise _fehler("wis_dialog_zeit") from None
    except OSError:
        raise _fehler("wis_dialog_fehlt") from None
    if r.returncode != 0:
        raise _fehler("wis_dialog_fehlgeschlagen")
    try:
        text = base64.b64decode((r.stdout or "").strip() or "", validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        raise _fehler("wis_dialog_fehlgeschlagen") from None
    return [z for z in text.split("\n") if z.strip()]
