"""Übertragbare Auftragsstruktur für Aufträge an Modelle (Regelwerk Standardläufe, Abschnitt 11).

Ein Auftrag ist ein Ordner mit zwei Dateien und enthält keine Pfade dieses PCs:

    <auftrag>/auftrag.json        Manifest: Modell, Eingaben, Schreibbereich, Ausgaben, Prüf- und Abbruchregeln
    <auftrag>/spezifikation.md    Text des Auftrags (relativ zum Ordner, höchstens 4000 Zeichen)

Der Ordner kann auf einen anderen Rechner kopiert werden. Die Werkstatt-Wurzel (Ordner mit `redesign/`) gibt der
Aufrufer an; sie steht nie in der Datei. Pfade im Manifest sind relativ zum Labor (`lab`). Maschinenordner
folgen dem Platzhalter-Muster aus local_paths.py.

Das Manifest wird über `laufdefinition.pruefen` geprüft, damit es dieselben Regeln wie frei anlegbare Läufe hat.
Dazu kommen: Pflichtfelder, Prüf- und Abbruchregeln aus festen Listen, und die Portabilitätsprüfung.
Ausgeführt wird der Auftrag weiter über `laufdefinition` und `redesign_agent`; diese Datei ändert den Lauf nicht.
"""
from __future__ import annotations
import json
import re
import shutil
from pathlib import Path

from . import laufdefinition

FORMAT = "guppi-auftrag"
VERSION = 1
MANIFEST = "auftrag.json"
MAX_SPEC = 4000                 # wie laufdefinition.MAX_TASK: der Text geht als Auftrag in den Lauf
MAX_EINGABEN = 20

# Feste Obergrenzen (Regelwerk Abschnitt 4). Der Lauf nutzt seine eigenen Konstanten in redesign_agent;
# das Manifest darf nur niedrigere Werte nennen.
ABBRUCH_OBERGRENZEN = {"max_schritte": 40, "max_wiederholungen": 2, "schritt_timeout_s": 240, "token_limit": 12000}

# Feste Liste der Prüfregeln. Maschinell: die ersten fünf. "belege" braucht den Vorarbeiter (Regelwerk Abschnitt 5, Punkt 4).
PRUEFREGELN = ("schreibbereich", "ausgaben_vollstaendig", "zeilen_max_400", "keine_fetch_localstorage", "syntax_js", "belege")
MANUELLE_REGELN = ("belege",)
PFLICHT = ("format", "version", "name", "modell", "spezifikation", "lab", "schreibbereich", "ausgaben", "pruefregeln")

# Muster für Angaben, die nur auf diesem PC gelten. Ein Treffer macht den Ordner nicht portabel.
MASCHINEN_MUSTER = [
    re.compile(r"[A-Za-z]:[\\/]"),                       # Laufwerk: C:\ oder E:/
    re.compile(r"(?:^|[\s\"'=(])/(?:home|Users|mnt|opt|var|tmp)/"),
    re.compile(r"\\\\[^\\\s]+\\"),                       # UNC-Pfad
    re.compile(r"[\\/]Users[\\/][A-Za-z0-9._-]+", re.IGNORECASE),
]


def _rel(text, feld):
    """Relativer Pfad im Labor: kein Laufwerk, kein Schrägstrich am Anfang, kein '..'."""
    text = str(text or "")
    if not text or text.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", text) or ".." in Path(text.replace("\\", "/")).parts:
        raise ValueError(f"{feld}_pfad_unzulaessig")
    return text.replace("\\", "/")


def _zahl(manifest_teil, feld, obergrenze):
    wert = manifest_teil.get(feld)
    if not isinstance(wert, int) or isinstance(wert, bool) or wert < 1 or wert > obergrenze:
        raise ValueError(f"abbruch_{feld}_ungueltig")
    return wert


def manifest_pruefen(manifest):
    """Prüft das Manifest ohne Dateizugriff. Gibt die bereinigte Fassung zurück, sonst ValueError mit Grund."""
    if not isinstance(manifest, dict): raise ValueError("manifest_kein_objekt")
    if manifest.get("format") != FORMAT: raise ValueError("format_unbekannt")
    if manifest.get("version") != VERSION: raise ValueError("version_unbekannt")
    fehlend = [f for f in PFLICHT if f not in manifest]
    if fehlend: raise ValueError("pflichtfeld_fehlt:" + fehlend[0])

    modell = manifest["modell"]
    if not isinstance(modell, dict): raise ValueError("modell_kein_objekt")
    eingaben = [_rel(x, "eingabe") for x in (manifest.get("eingaben") or [])]
    if len(eingaben) > MAX_EINGABEN: raise ValueError("eingaben_zu_viele")

    pruefregeln = list(manifest["pruefregeln"] or [])
    for regel in pruefregeln:
        if regel not in PRUEFREGELN: raise ValueError("pruefregel_unbekannt:" + str(regel)[:40])
    if len(set(pruefregeln)) != len(pruefregeln): raise ValueError("pruefregel_doppelt")
    if "schreibbereich" not in pruefregeln or "ausgaben_vollstaendig" not in pruefregeln:
        raise ValueError("pruefregel_pflicht_fehlt")

    abbruch = manifest.get("abbruchregeln") or {}
    if not isinstance(abbruch, dict): raise ValueError("abbruchregeln_kein_objekt")
    unbekannt = set(abbruch) - set(ABBRUCH_OBERGRENZEN)
    if unbekannt: raise ValueError("abbruchregel_unbekannt:" + sorted(unbekannt)[0])
    bereinigt = {}
    for feld, grenze in ABBRUCH_OBERGRENZEN.items():
        if feld in abbruch:
            bereinigt[feld] = _zahl(abbruch, feld, grenze)

    spez = _rel(manifest["spezifikation"], "spezifikation")
    if not spez.endswith(".md"): raise ValueError("spezifikation_kein_md")

    lauf = {"name": manifest["name"], "art": manifest.get("art") or "bewerten",
            "beschreibung": manifest.get("beschreibung") or "", "lab": manifest["lab"],
            "provider": modell.get("provider") or "", "model": modell.get("model") or "",
            "task": "(Auftragstext)", "allow": manifest["schreibbereich"], "outputs": manifest["ausgaben"]}
    # Name, Art, Pfade, Modell, Schreibbereich und Ausgaben prüft laufdefinition; der Auftragstext kommt in als_laufdefinition
    geprueft = laufdefinition.pruefen(lauf)
    return {"format": FORMAT, "version": VERSION, "name": geprueft["name"], "art": geprueft["art"],
            "beschreibung": geprueft["beschreibung"], "modell": {"provider": geprueft["provider"], "model": geprueft["model"]},
            "spezifikation": spez, "lab": geprueft["lab"], "eingaben": eingaben, "schreibbereich": geprueft["allow"],
            "ausgaben": geprueft["outputs"], "pruefregeln": pruefregeln, "abbruchregeln": bereinigt}


def laden(ordner):
    """Liest <ordner>/auftrag.json und den Auftragstext. Gibt (manifest, text) zurück."""
    ordner = Path(ordner)
    pfad = ordner / MANIFEST
    if not pfad.is_file(): raise ValueError("manifest_fehlt")
    try:
        roh = json.loads(pfad.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise ValueError("manifest_kein_json")
    manifest = manifest_pruefen(roh)
    spez = (ordner / manifest["spezifikation"]).resolve()
    if not spez.is_relative_to(ordner.resolve()) or not spez.is_file(): raise ValueError("spezifikation_fehlt")
    text = spez.read_text(encoding="utf-8").strip()
    if not text: raise ValueError("auftrag_leer")
    if len(text) > MAX_SPEC: raise ValueError("auftrag_zu_lang")
    return manifest, text


def als_laufdefinition(ordner):
    """Die Definition, die laufdefinition.anlegen und vorarbeiter 'lauf_anlegen' erwarten."""
    manifest, text = laden(ordner)
    hinweis = ""
    if manifest["eingaben"]:
        hinweis = "\n\nEingaben (nur lesen): " + ", ".join(manifest["eingaben"])
    return {"name": manifest["name"], "art": manifest["art"], "beschreibung": manifest["beschreibung"], "lab": manifest["lab"],
            "provider": manifest["modell"]["provider"], "model": manifest["modell"]["model"],
            "task": text + hinweis, "allow": manifest["schreibbereich"], "outputs": manifest["ausgaben"]}


def portabel_pruefen(ordner):
    """Liste der Fundstellen, an denen Angaben nur auf diesem PC gelten. Leer heißt: portabel.
    Platzhalter wie <modelle> sind erlaubt. Geprüft werden Manifest und Auftragstext."""
    ordner = Path(ordner)
    fund = []
    for datei in (ordner / MANIFEST, ordner / "spezifikation.md"):
        if not datei.is_file(): continue
        for nr, zeile in enumerate(datei.read_text(encoding="utf-8").splitlines(), 1):
            if any(m.search(zeile) for m in MASCHINEN_MUSTER):
                fund.append({"datei": datei.name, "zeile": nr})
    return fund


def pruefe_ausgaben(box, manifest, schreibprotokoll):
    """Maschinelle Prüfung nach Regelwerk Abschnitt 5 (Punkte 1, 2, 3, 5). `box` ist der Labor-Ordner,
    `schreibprotokoll` die Liste aus dem Lauf ({"path", "bytes"}). Gibt Befunde zurück, nicht Entscheidungen."""
    box = Path(box)
    befunde = []
    regeln = manifest["pruefregeln"]

    if "schreibbereich" in regeln:
        erlaubt = manifest["schreibbereich"]
        fremd = [w["path"] for w in schreibprotokoll
                 if not any(w["path"] == a or w["path"].startswith(a.rstrip("/") + "/") for a in erlaubt)]
        befunde.append(_befund("schreibbereich", not fremd, "fremde Schreibvorgänge: " + ", ".join(fremd[:5]) if fremd else ""))

    if "ausgaben_vollstaendig" in regeln:
        fehlend = [o for o in manifest["ausgaben"] if not (box / o).is_file() or (box / o).stat().st_size == 0]
        befunde.append(_befund("ausgaben_vollstaendig", not fehlend, "fehlt oder leer: " + ", ".join(fehlend) if fehlend else ""))

    dateien = [p for p in box.rglob("*") if p.is_file() and p.suffix in (".js", ".css", ".html", ".md")] if box.is_dir() else []
    if "zeilen_max_400" in regeln:
        lang = [p.name for p in dateien if len(p.read_text(encoding="utf-8", errors="replace").splitlines()) > 400]
        befunde.append(_befund("zeilen_max_400", not lang, "über 400 Zeilen: " + ", ".join(lang[:5]) if lang else ""))

    if "keine_fetch_localstorage" in regeln:
        js = [p for p in dateien if p.suffix == ".js"]
        treffer = [p.name for p in js if re.search(r"\bfetch\s*\(|localStorage", p.read_text(encoding="utf-8", errors="replace"))]
        befunde.append(_befund("keine_fetch_localstorage", not treffer, "fetch oder localStorage in: " + ", ".join(treffer[:5]) if treffer else ""))

    if "syntax_js" in regeln:
        js = [p for p in dateien if p.suffix == ".js"]
        node = shutil.which("node")
        if not node:
            befunde.append(_befund("syntax_js", None, "node nicht gefunden: nicht geprüft"))  # nicht_geprueft, kein Fehlschlag
        else:
            import subprocess
            schlecht = []
            for p in js:
                lauf = subprocess.run([node, "--check", str(p)], capture_output=True, text=True, timeout=30)
                if lauf.returncode != 0: schlecht.append(p.name)
            befunde.append(_befund("syntax_js", not schlecht, "Syntaxfehler in: " + ", ".join(schlecht[:5]) if schlecht else ""))

    for regel in regeln:
        if regel in MANUELLE_REGELN:
            befunde.append(_befund(regel, None, "manuell: Vorarbeiter prüft", status="manuell"))
    return befunde


def _befund(regel, ok, hinweis, status=None):
    """ok: True/False für eine maschinell geprüfte Regel, None für eine, die nicht geprüft werden konnte oder manuell ist."""
    if status is None:
        status = ("bestanden" if ok else "nicht_bestanden") if ok is not None else "nicht_geprueft"
    return {"regel": regel, "status": status, "hinweis": hinweis}


def ergebnis(befunde):
    """Zusammenfassung für den Vorarbeiter: 'nacharbeit' bei einem Fehlschlag, sonst 'maschinell_ok'.
    Die Entscheidung des Captains bleibt offen (Regelwerk Abschnitt 3, Punkt 6)."""
    if any(b["status"] == "nicht_bestanden" for b in befunde):
        return "nacharbeit"
    return "maschinell_ok"


def paket(ordner, ziel):
    """Kopiert einen Auftrag in einen neuen Ordner, nachdem er geprüft wurde. Gibt die Liste der Kopien zurück."""
    ordner, ziel = Path(ordner), Path(ziel)
    manifest, _ = laden(ordner)
    fund = portabel_pruefen(ordner)
    if fund: raise ValueError("nicht_portabel")
    if ziel.exists(): raise ValueError("ziel_vergeben")
    ziel.mkdir(parents=True)
    kopien = []
    for datei in (MANIFEST, manifest["spezifikation"]):
        (ziel / datei).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ordner / datei, ziel / datei)
        kopien.append(datei)
    return kopien
