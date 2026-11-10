"""Werkzeuge des Managers. Jedes Werkzeug kann nur das, was hier steht; die Erlaubnis gibt gesetze.yaml (Abschnitt werkzeuge).

- taschenrechner:      rechnet mit Zahlen und den Grundrechenarten (kein eval, keine Namen, keine Aufrufe)
- notizblock:          schreibt und liest die Notizen des Managers in einer Datei im Projekt (nur anhängen und lesen)
- dashboard_stand:     liest das Register und fasst den Stand zusammen (nur lesen)
- journal_lesen:       liest die letzten Einträge des Journals (nur lesen)
- modell_wahl:         wählt ein Cloud-Modell aus den Fähigkeitstests (nur lesen)
- auftraege_verteilen: gibt Teilaufträge an den Vorarbeiter-Kanal, der sie an das Cloud-Modell (Hilfs-Coder) weitergibt; je Auftrag prüft er Gesetze, Tagesbudget und Inhaltsschutz
"""
import ast
import json
import operator
from datetime import datetime, timezone
from pathlib import Path

REGISTER = Path("auftraege.json")       # relativ zum Projekt; siehe dashboard_stand

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos}
MAX_POTENZ = 12


def taschenrechner(ausdruck):
    """Rechnet einen Ausdruck mit Zahlen und + - * / ** und Klammern. Alles andere wird abgelehnt."""
    if not isinstance(ausdruck, str) or len(ausdruck) > 200:
        raise ValueError("ausdruck_ungueltig")
    baum = ast.parse(ausdruck.replace(",", "."), mode="eval")

    def werte(knoten):
        if isinstance(knoten, ast.Expression):
            return werte(knoten.body)
        if isinstance(knoten, ast.Constant) and isinstance(knoten.value, (int, float)) and not isinstance(knoten.value, bool):
            return knoten.value
        if isinstance(knoten, ast.UnaryOp) and type(knoten.op) in _OPS:
            return _OPS[type(knoten.op)](werte(knoten.operand))
        if isinstance(knoten, ast.BinOp) and type(knoten.op) in _OPS:
            links, rechts = werte(knoten.left), werte(knoten.right)
            if isinstance(knoten.op, ast.Pow) and abs(rechts) > MAX_POTENZ:
                raise ValueError("potenz_zu_gross")
            return _OPS[type(knoten.op)](links, rechts)
        raise ValueError("nicht_erlaubt")

    ergebnis = werte(baum)
    return round(ergebnis, 10) if isinstance(ergebnis, float) else ergebnis


def notizblock_schreiben(projekt, text):
    """Hängt eine Notiz mit Zeitstempel an. Überschreiben und Löschen gibt es nicht."""
    if not isinstance(text, str) or not text.strip() or len(text) > 2000:
        raise ValueError("notiz_ungueltig")
    pfad = Path(projekt) / "runtime_data" / "manager" / "notizblock.md"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    zeile = f"- {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC: {text.strip()}\n"
    with pfad.open("a", encoding="utf-8") as f:
        f.write(zeile)
    return "gespeichert"


def notizblock_lesen(projekt, anzahl=50):
    pfad = Path(projekt) / "runtime_data" / "manager" / "notizblock.md"
    if not pfad.exists():
        return []
    return pfad.read_text(encoding="utf-8").splitlines()[-int(anzahl):]


def dashboard_stand(register):
    """Zählt Aufträge nach Status und nennt die offenen (nicht MERGED, nicht MAIN_VERIFIED, nicht CLOSED)."""
    daten = json.loads(Path(register).read_text(encoding="utf-8"))
    aufgaben = daten.get("tasks", [])
    zaehl = {}
    for a in aufgaben:
        zaehl[a.get("status", "?")] = zaehl.get(a.get("status", "?"), 0) + 1
    fertig = {"MERGED", "MAIN_VERIFIED", "CLOSED"}
    offen = [{"id": a["id"], "status": a.get("status")} for a in aufgaben if a.get("status") not in fertig]
    return {"anzahl": len(aufgaben), "nach_status": zaehl, "offen": offen}


def journal_lesen(journal, anzahl=20):
    pfad = Path(journal)
    if not pfad.exists():
        return []
    zeilen = pfad.read_text(encoding="utf-8").splitlines()[-int(anzahl):]
    return [json.loads(z) for z in zeilen if z.strip()]


def modell_wahl(aufgabe_typ, ordner):
    """Modell für einen Aufgabentyp aus den Fähigkeitstests (siehe modellwahl.py). Nur lesen."""
    from .modellwahl import waehle_modell
    return waehle_modell(aufgabe_typ, ordner)


MAX_AUFTRAEGE = 5            # Teilaufträge je Aufruf
MAX_AUFTRAG_TEXT = 12000     # Zeichen je Teilauftrag


def auftraege_verteilen(manager, sedra_root, auftraege):
    """Der Manager gibt Teilaufträge an den Hilfs-Coder in der Cloud (Vorarbeiter-Kanal, manager/kanal.py). Jeder Auftrag: {typ, text}.
    Erlaubnis kommt aus gesetze.yaml; der Kanal prüft je Auftrag Aufgabentyp (cloud_aufgaben), Tagesbudget und Inhaltsschutz. Ein abgelehnter Auftrag
    steht mit seinem Grund im Ergebnis, er stoppt die anderen nicht. Das Ergebnis ist nur Text: nichts wird geschrieben oder übernommen."""
    manager.nutze_werkzeug("auftraege_verteilen")
    if not isinstance(auftraege, list) or not 1 <= len(auftraege) <= MAX_AUFTRAEGE:
        raise ValueError("auftraege_ungueltig")
    sauber = []
    for a in auftraege:
        if not isinstance(a, dict) or not isinstance(a.get("typ"), str) or not isinstance(a.get("text"), str) or len(a["text"]) > MAX_AUFTRAG_TEXT:
            raise ValueError("auftrag_ungueltig")
        sauber.append({"typ": a["typ"], "text": a["text"]})
    from .kanal import verteile
    return verteile(manager, sedra_root, sauber)


def bau_starten(projekt, auftrag, spec=None, rezept=None, kontext=None):
    """Startet einen vollautomatischen Bau-Lauf (benchmarks/bau_schleife.py start). Übernahme in runtime bleibt beim Captain.
    Läuft schon ein Bau (Sperrdatei mit lebender PID), startet nichts."""
    import subprocess
    import sys
    if not isinstance(auftrag, str) or not auftrag.strip() or len(auftrag) > 200:
        raise ValueError("auftrag_ungueltig")
    import re
    if spec is not None and (not isinstance(spec, str) or not re.fullmatch(r"[a-z][a-z0-9_]{1,60}", spec)):
        raise ValueError("spec_ungueltig")
    if rezept is not None and (not isinstance(rezept, str) or not re.fullmatch(r"[a-z][a-z0-9_.]{1,60}", rezept)):
        raise ValueError("rezept_ungueltig")
    if kontext is not None and (isinstance(kontext, bool) or not isinstance(kontext, int) or not 4096 <= kontext <= 262144):
        raise ValueError("kontext_ungueltig")
    projekt = Path(projekt)
    from ..workflows import fabrik
    halt = fabrik.angehalten(projekt)                                # roter Knopf: bei angehaltener Fabrik startet kein Bau
    if halt:
        return {"gestartet": False, "grund": "Die Fabrik ist angehalten (" + str(halt.get("grund") or "Notaus") + "); der Captain gibt sie wieder frei."}
    sperre = projekt / "runtime_data" / "bau_schleife.lock"
    if sperre.exists():
        alt = sperre.read_text(encoding="utf-8", errors="replace").strip()
        if alt.isdigit():
            lauf = subprocess.run(["tasklist", "/FI", f"PID eq {alt}", "/NH"], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
            if alt in lauf:
                return {"gestartet": False, "grund": f"Bau läuft schon (PID {alt})"}
    runtime = Path(__file__).resolve().parents[3]
    proc = subprocess.Popen([sys.executable, "benchmarks/bau_schleife.py", "--projekt", str(projekt)] + (["--spec", spec] if spec else []) + (["--rezept", rezept] if rezept else []) + (["--kontext", str(kontext)] if rezept and kontext else []) + ["start", auftrag.strip()],
                            cwd=str(runtime), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"gestartet": True, "pid": proc.pid}
