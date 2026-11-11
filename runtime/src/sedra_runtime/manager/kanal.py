"""Vorarbeiter-Kanal: verwaltet die Cloud-Modelle. Nimmt Aufträge des Managers an, prüft sie gegen die Gesetze,
wählt das Modell aus den Fähigkeitstests und gibt das Ergebnis mit Herkunft zurück. Er entscheidet nichts über Freigaben.

Ablauf je Auftrag:
  1. Manager.pruefe_auftrag(typ, cloud=True): Gesetze, Tagesbudget, Journal. Dann die Arbeitsanweisung des Typs (falls vorhanden)
     vor den Auftrag setzen; sie muss die Cloud selbst erlauben.
  2. modellwahl.waehle_modell(typ, ordner): ein Modell, das den Test für diesen Typ bestanden hat.
  3. labor.cloud_chat(...): Inhaltsschutz und Audit wie bei jedem Cloudaufruf.
  4. Ergebnis mit Modell, Zeit und Grund zurück; Fehler werden als solche gemeldet, nie als Erfolg.
"""
import time
from pathlib import Path

from .modellwahl import waehle_modell
from .verfassung import Manager, VerfassungsVerstoss


class Vorarbeiter:
    def __init__(self, sedra_root, manager=None):
        self.root = Path(sedra_root)
        self.ordner = self.root / "wissen_quellen" / "modelle"
        self.manager = manager or Manager("vorarbeiter", set(), journal=self.root / "runtime_data" / "manager" / "journal.jsonl")

    def auftrag(self, typ, nachricht):
        """Gibt {ok, modell, antwort, sekunden} oder {ok: False, grund} zurück."""
        try:
            self.manager.pruefe_auftrag(typ, cloud=True)
        except VerfassungsVerstoss as exc:
            return {"ok": False, "grund": f"Gesetz: {exc}"}
        try:
            anweisung, _ = self.manager.arbeitsanweisung(typ, pflicht=False)
        except VerfassungsVerstoss as exc:
            return {"ok": False, "grund": f"Arbeitsanweisung: {exc}"}
        if anweisung:
            if not anweisung["cloud"]:
                return {"ok": False, "grund": f"Die Arbeitsanweisung '{typ}' erlaubt die Cloud nicht."}
            nachricht = f"Arbeitsanweisung (verbindlich, ändert keine Gesetze):\n{anweisung['text']}\n\n---\nAuftrag:\n{nachricht}"
        modell = waehle_modell(typ, self.ordner)
        if not modell:
            return {"ok": False, "grund": f"Kein Modell hat den Test für '{typ}' bestanden."}
        return self._senden(typ, modell, nachricht)

    def _senden(self, typ, modell, nachricht):
        from sedra_runtime import cloud_settings as cs
        from sedra_runtime import labor
        from sedra_runtime.core.audit import AuditLog
        cfg = cs.load_config(self.root)
        store = cs.CloudKeyStore(cs.key_store_path(self.root))
        protokoll = AuditLog(self.root / "runtime_data" / "audit" / "events.jsonl")
        import os
        t0 = time.monotonic()
        try:
            a = labor.cloud_chat(cfg, "nvidia", modell, [{"role": "user", "content": nachricht}], environ=os.environ, key_store=store, audit=protokoll)
        except Exception as exc:
            return {"ok": False, "modell": modell, "grund": f"{type(exc).__name__}: {str(exc)[:160]}", "sekunden": round(time.monotonic() - t0, 1)}
        text = (a.get("reply") or a.get("content") or "") if isinstance(a, dict) else ""
        if not text.strip():
            return {"ok": False, "modell": modell, "grund": f"leere Antwort (Status {a.get('status') if isinstance(a, dict) else '?'})",
                    "sekunden": round(time.monotonic() - t0, 1)}
        return {"ok": True, "modell": modell, "typ": typ, "antwort": text, "sekunden": round(time.monotonic() - t0, 1)}


def verteile(manager, sedra_root, auftraege):
    """Der Manager gibt mehrere Aufträge an den Vorarbeiter. Jeder Auftrag: {typ, text}. Reihenfolge bleibt erhalten.
    Ergebnis je Auftrag: ok, Modell, Antwort oder Grund. Ein Fehler stoppt die anderen nicht."""
    vorarbeiter = Vorarbeiter(sedra_root, manager=manager)
    ergebnisse = []
    for a in auftraege:
        typ = str(a.get("typ", ""))
        text = str(a.get("text", ""))
        if not text.strip():
            ergebnisse.append({"ok": False, "typ": typ, "grund": "leerer Auftrag"})
            continue
        erg = vorarbeiter.auftrag(typ, text)
        erg.setdefault("typ", typ)
        ergebnisse.append(erg)
    return ergebnisse
