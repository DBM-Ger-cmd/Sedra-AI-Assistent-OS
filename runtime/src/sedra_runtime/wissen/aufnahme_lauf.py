"""Erstaufnahme einer Sammlung als Lauf der Harness (SPEC_WISSEN_KERN_v1 WK-24; G2 K5 §2.7, D-K5-4, D-K5-6).

Ein eigener Prozess (Lauftyp `wissen_aufnahme` in `config/harness_laeufe.yaml`, gestartet über die Lauf-Hülle: Fortschritt, Stopp, Ende).
Er hält die Sperre `local_config/wissen/aufnahme.lock` für seine ganze Dauer; der Takt des Servers nimmt dieselbe Sperre je Durchgang und setzt
aus, solange der Lauf sie hält – zwei Schreiber gleichzeitig gibt es so nicht. (Die Sperre `takt.lock` hält der Server dauerhaft; deshalb
eine eigene.) Ablauf: Abgleich in Schritten (`aufnahme.dateien_je_schritt`), bis keine Datei mehr offen ist, dann Einbetten in Schritten auf
der CPU über denselben Einbett-Server (läuft er schon, wird er mitbenutzt; sonst startet der Lauf ihn und beendet ihn am Ende wieder).
Hält jemand die GPU-Lease für einen Bau, wartet der Lauf wie der Takt. Abbruch jederzeit: jeder Schritt ist eine Transaktion; ein neuer
Lauf macht über die Tabelle `dateien` dort weiter.

Fortschrittszeilen (Regel in harness_laeufe.yaml: „Stand n/100“): `Stand p/100 · Dateien n/m · Abschnitte a · eingebettet e/v`;
der Abgleich zählt bis 50, das Einbetten von 50 bis 100.
Rückgabe von `main`: 0 fertig · 2 Fehler (Quelle unbekannt, aus, Wissen nicht lesbar) · 3 Sperre nicht bekommen."""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from ..core.mission_lock import exclusive
from . import aufnahme

WARTEN_S = 600.0
PAUSE_S = 30.0


def zeile(dateien, gesamt, abschnitte, vektoren=None):
    """Eine Fortschrittszeile; `vektoren` None heißt: noch im Abgleich."""
    if vektoren is None:
        p = 50 * dateien // gesamt if gesamt else 0
        return f"Stand {p}/100 · Dateien {dateien}/{gesamt} · Abschnitte {abschnitte} · eingebettet –"
    p = 50 + (50 * min(vektoren, abschnitte) // abschnitte if abschnitte else 50)
    return f"Stand {p}/100 · Dateien {dateien}/{gesamt} · Abschnitte {abschnitte} · eingebettet {vektoren}/{abschnitte}"


def _sperre(pfad, warten_s, schlaf):
    """Die Sperre holen; ist der Takt gerade dran, bis zu `warten_s` warten. None, wenn sie nicht frei wird."""
    frist = time.monotonic() + warten_s
    while True:
        cm = exclusive(pfad)
        try:
            cm.__enter__()
            return cm
        except RuntimeError as exc:
            if str(exc) != "mission_execution_busy" or time.monotonic() >= frist:
                return None
            schlaf(2.0)


def laufen(sp, quelle_id, *, ausgabe=print, warten_s=WARTEN_S, schlaf=time.sleep, pause_max_s=3600.0):
    """Der Lauf an einem offenen Speicher. Rückgabe wie `main`."""
    sperre = _sperre(sp.pfad.parent / aufnahme.SPERRE, warten_s, schlaf)
    if sperre is None:
        ausgabe("Die Aufnahme ist belegt (ein anderer Lauf oder der Takt); später noch einmal starten.")
        return 3
    try:
        q = sp.quelle(quelle_id)
        if q is None or not q["aktiv"]:
            ausgabe(f"Quelle {quelle_id} ist unbekannt oder abgeschaltet.")
            return 2
        sp.audit("WIS_AUFNAHME_LAUF", {"quelle": quelle_id, "aktion": "start"})
        while True:
            a = sp.abgleich(quelle_id)
            st = sp.dateien_stand(quelle_id, limit=1)["summen"]
            fertig = st["aufgenommen"] + st["uebersprungen"]
            gesamt = max(fertig, st["aufgenommen"] + (st["offen"] or 0))     # `offen` zählt übersprungene Dateien mit
            ausgabe(zeile(fertig, gesamt, st["abschnitte"]))
            if not a.get("dateien_offen"):
                break
        gestartet = not sp.dienst.antwortet()
        pause_seit = None
        try:
            while True:
                r = sp.einbetten_schritt()
                s = sp.stand()
                ausgabe(zeile(fertig, gesamt, s["abschnitte"], s["vektoren"]))
                if r["ende"] == "pause":                           # Bau mit GPU-Lease: warten wie der Takt
                    pause_seit = pause_seit or time.monotonic()
                    if time.monotonic() - pause_seit > pause_max_s:
                        ausgabe("Die GPU ist zu lange belegt; der Lauf hört auf. Der Takt bettet später weiter ein.")
                        break
                    schlaf(PAUSE_S)
                    continue
                pause_seit = None
                if r["ende"] == "fehler":
                    ausgabe("Einbetten nicht möglich: " + str(r.get("grund") or "?") + " – die Volltextsuche findet die Abschnitte trotzdem.")
                    break
                if r["eingebettet"] == 0 or s["vektoren"] >= s["abschnitte"]:
                    break
        finally:
            if gestartet:                                          # nur den Server beenden, den dieser Lauf gestartet hat
                sp.dienst.stoppe()
        sp.audit("WIS_AUFNAHME_LAUF", {"quelle": quelle_id, "aktion": "ende"})
        ausgabe("fertig")
        return 0
    finally:
        sperre.__exit__(None, None, None)


def _speicher(projekt, repo):
    from ..core.audit import AuditLog
    from ..jobs.testlab import TestLab, default_path
    from . import konfig
    from .embed import TestLabZugang, VerzoegertesLabor
    from .speicher import WissenSpeicher
    cfg = konfig.load(repo / "runtime" / "config" / "wissen.yaml", projekt / "local_config" / "wissen.yaml")
    log = AuditLog(projekt / "runtime_data" / "audit" / "events.jsonl")
    return WissenSpeicher.oeffnen(cfg, projekt_root=projekt, repo_root=repo, audit=lambda e, p: log.append(e, component="wissen", payload=p),
                                  gpu=TestLabZugang(VerzoegertesLabor(default_path(projekt), TestLab)))


def main(argv=None):
    p = argparse.ArgumentParser(description="Erstaufnahme einer Quelle des Wissens (Lauf der Harness)")
    p.add_argument("--project", required=True)
    p.add_argument("--quelle", required=True)
    a = p.parse_args(argv)
    repo = Path(__file__).resolve().parents[4]
    try:
        sp = _speicher(Path(a.project).resolve(), repo)
    except (ValueError, OSError) as exc:
        print("Das Wissen lässt sich nicht öffnen: " + (str(exc) or type(exc).__name__)[:160], flush=True)
        return 2
    try:
        return laufen(sp, a.quelle, ausgabe=lambda t: print(t, flush=True))
    finally:
        sp.schliessen()


if __name__ == "__main__":
    sys.exit(main())
