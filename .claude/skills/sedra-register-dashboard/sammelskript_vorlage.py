"""Vorlage: mehrere gemergte Auftraege auf einmal ins Register eintragen (nicht ausfuehren, erst anpassen).
Kopieren, PAKET und NEU ausfuellen, dann aus dem Scratchpad starten. Zeilenenden bleiben UTF-8, Einrueckung 2."""
import json
import shutil
from pathlib import Path

PAKET = Path(r"<umgebung>\KOORDINATION_SEDRA\01_KOORDINATOR_QUELLE\koord\SEDRA_Koordinator_Entwicklerpaket_v1_1_2026-11-06")
GRUND = "<grund>_<JJJJMMTT>"                       # Name der Sicherung
BASIS = "<commit vor dem Paket>"
FREIGABE = "<Datum>: Ja, mergen; Ja, pushen (Captain, im Chat)"
ABHAENGIG = ["<id eines Vorgaengers>"]
ENDE = "<kurzer Commit des letzten Teils>"

# (id, titel, integration_commit, scope, acceptance, notes)  - notes nennt "Nicht gebaut" und "Nicht am PC geprueft"
NEU = [
    ("SEDRA-<...>-01", "<Titel>", "<commit>", "<Dateien und Routen>", "<Tests mit Zahlen>", "<nicht gebaut / nicht geprueft>"),
]

REG = PAKET / "04_REGISTER" / "auftraege.json"
S = PAKET / "04_REGISTER" / f"auftraege.json.bak_vor_{GRUND}"
if not S.exists():
    shutil.copy2(REG, S)                           # immer zuerst sichern
reg = json.loads(REG.read_text(encoding="utf-8"))
ids = {t["id"] for t in reg["tasks"]}              # volle ID pruefen, nie eine Kurzform suchen
for tid, titel, commit, scope, acc, notes in NEU:
    if tid in ids:
        continue                                   # vorhandene Eintraege nicht ueberschreiben
    reg["tasks"].append({
        "id": tid, "title": titel, "track": "Module", "owner": "Koordinator", "priority": "P1", "status": "MERGED",
        "depends_on": ABHAENGIG, "scope": scope, "acceptance": acc, "source": "Captain <Datum>",
        "notes": notes, "candidate_paths": [], "assigned_coder": None, "base_commit": BASIS,
        "integration_commit": commit, "tester_report": None, "captain_approval": FREIGABE,
        "last_verified_at": "<JJJJ-MM-TT>",
    })
reg["snapshot_date"] = "<Datum> (Koordinator, nach Push " + ENDE + ")"
b = reg["baseline"]
b["last_reported_local_main"] = ENDE
b["origin_main"] = ENDE
b["unpushed_commits_on_local_main"] = []
b["live_verification_evidence"] = "<Datum>: git push, ls-remote origin main = rev-parse main = " + ENDE + "."
REG.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
print(len(reg["tasks"]))
# danach: validate_register.py, render_dashboard.py, Kopie nach <umgebung>\KOORDINATOR_DASHBOARD.html, cmp
