"""Verfassung des Managers: die Gesetze als harte, nachprüfbare Grenzen. Der Rahmen (verfassung.md) bleibt Text,
die Gesetze (gesetze.yaml) werden hier vor jeder Entscheidung und jeder Delegation geprüft.

Der Manager darf frei entscheiden, aber jede Entscheidung läuft durch `pruefe_auftrag` und `delegiere`. Verstöße werfen
VerfassungsVerstoss; der Grund steht im Journal (runtime_data/manager/journal.jsonl).
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

CONFIG = Path(__file__).resolve().parents[3] / "config" / "manager"


class VerfassungsVerstoss(ValueError):
    def __init__(self, gesetz, grund):
        self.gesetz = gesetz
        self.grund = grund
        super().__init__(f"{gesetz}: {grund}")


def lade_gesetze(pfad=None):
    with (Path(pfad) if pfad else CONFIG / "gesetze.yaml").open(encoding="utf-8") as f:
        return yaml.safe_load(f)["gesetze"]


class Manager:
    """Ein Akteur mit Rechten. Der Manager hat die Rechte, die ihm der Captain gibt; Untergebene erben höchstens diese."""

    def __init__(self, name, rechte, tiefe=0, gesetze=None, journal=None, werkzeuge=None):
        self.name = name
        self.rechte = set(rechte)
        self.tiefe = tiefe
        self.g = gesetze or lade_gesetze()
        self.journal = Path(journal) if journal else None
        self.werkzeuge = set(werkzeuge) if werkzeuge is not None else set(self.g["werkzeuge"]["erlaubt"])

    def nutze_werkzeug(self, name):
        """Prüft, ob dieser Akteur das Werkzeug benutzen darf. Wirft VerfassungsVerstoss, sonst None."""
        if name not in self.g["werkzeuge"]["erlaubt"] or name not in self.werkzeuge:
            self._notiere(f"werkzeug:{name}", False, "nicht erlaubt")
            raise VerfassungsVerstoss("werkzeuge", f"Das Werkzeug '{name}' ist für {self.name} nicht erlaubt.")
        self._notiere(f"werkzeug:{name}", True, "erlaubt")

    def _notiere(self, entscheidung, ok, grund, cloud=False):
        if not self.journal:
            return
        self.journal.parent.mkdir(parents=True, exist_ok=True)
        zeile = {"zeit": datetime.now(timezone.utc).isoformat(), "akteur": self.name, "tiefe": self.tiefe,
                 "entscheidung": entscheidung, "ok": ok, "grund": grund, "cloud": cloud}
        with self.journal.open("a", encoding="utf-8") as f:
            f.write(json.dumps(zeile, ensure_ascii=False) + "\n")

    def _cloud_heute(self):
        """Wie viele Cloud-Aufträge heute schon ok waren (aus dem Journal)."""
        if not self.journal or not self.journal.exists():
            return 0
        heute = datetime.now(timezone.utc).date().isoformat()
        n = 0
        for zeile in self.journal.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(zeile)
            except ValueError:
                continue
            if e.get("cloud") and e.get("ok") and str(e.get("zeit", "")).startswith(heute):
                n += 1
        return n

    def pruefe_auftrag(self, aufgabe_typ, recht=None, cloud=False):
        """Prüft einen Auftrag gegen die Gesetze. Wirft VerfassungsVerstoss, sonst None."""
        try:
            if recht and recht in self.g["nur_captain"]:
                raise VerfassungsVerstoss("nur_captain", f"Das Recht '{recht}' vergibt nur der Captain.")
            if recht and recht not in self.rechte:
                raise VerfassungsVerstoss("rechte", f"Der Akteur {self.name} hat das Recht '{recht}' nicht.")
            if cloud and aufgabe_typ not in self.g["cloud_aufgaben"]:
                raise VerfassungsVerstoss("cloud_aufgaben", f"Aufgabentyp '{aufgabe_typ}' ist nicht für die Cloud freigegeben.")
            if cloud:
                grenze = self.g["budget"]["cloud_anfragen_pro_tag"]
                if self._cloud_heute() >= grenze:
                    raise VerfassungsVerstoss("budget", f"Tagesbudget für Cloud-Anfragen ({grenze}) ist aufgebraucht.")
        except VerfassungsVerstoss as exc:
            self._notiere(f"auftrag:{aufgabe_typ}", False, str(exc), cloud=cloud)
            raise
        self._notiere(f"auftrag:{aufgabe_typ}", True, "im Rahmen der Gesetze", cloud=cloud)

    def delegiere(self, name, rechte, werkzeuge=None):
        """Einen Untergebenen einsetzen. Er bekommt höchstens die Rechte und Werkzeuge dieses Akteurs und darf nicht zu tief verschachtelt werden."""
        tiefe = self.tiefe + 1
        wz = set(werkzeuge) if werkzeuge is not None else set(self.werkzeuge)
        if wz - self.werkzeuge:
            self._notiere(f"delegation:{name}", False, f"mehr Werkzeuge als der Manager: {sorted(wz - self.werkzeuge)}")
            raise VerfassungsVerstoss("werkzeuge", f"{name} soll Werkzeuge bekommen, die der Manager nicht hat: {sorted(wz - self.werkzeuge)}.")
        if tiefe > self.g["untergebene"]["hoechste_tiefe"]:
            self._notiere(f"delegation:{name}", False, "zu tief")
            raise VerfassungsVerstoss("untergebene", f"Delegation an {name} wäre Tiefe {tiefe}; erlaubt sind höchstens {self.g['untergebene']['hoechste_tiefe']}.")
        mehr = set(rechte) - self.rechte
        if mehr:
            self._notiere(f"delegation:{name}", False, f"mehr Rechte als der Manager: {sorted(mehr)}")
            raise VerfassungsVerstoss("untergebene", f"{name} soll Rechte bekommen, die der Manager nicht hat: {sorted(mehr)}.")
        self._notiere(f"delegation:{name}", True, "Rechte ⊆ Manager")
        return Manager(name, set(rechte), tiefe=tiefe, gesetze=self.g, journal=self.journal, werkzeuge=wz)
