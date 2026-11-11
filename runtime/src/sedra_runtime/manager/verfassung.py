"""Verfassung des Managers: die Gesetze als harte, nachprüfbare Grenzen. Der Rahmen (verfassung.md) bleibt Text,
die Gesetze (gesetze.yaml) werden hier vor jeder Entscheidung und jeder Delegation geprüft.

Der Manager darf frei entscheiden, aber jede Entscheidung läuft durch `pruefe_auftrag` und `delegiere`. Verstöße werfen
VerfassungsVerstoss; der Grund steht im Journal (runtime_data/manager/journal.jsonl).
"""
import json
import re
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


TYP = re.compile(r"[a-z0-9_]{1,60}")          # nur ASCII: str.isalnum ließe auch "²" oder Umlaute durch
KOPF_ERLAUBT = {"typ", "werkzeuge", "cloud", "sprache", "quelle_sha256", "text_sha256", "freigegeben", "quelle", "uebersetzt_von"}
MAX_DATEI = 20000                              # Bytes; eine Anweisung ist kurz, ein langer Text würde den Kontext der Modelle fressen
MAX_TEXT = 8000                                # Zeichen im Text


def lade_arbeitsanweisung(typ, gesetze=None, pfad=None, pflicht=True):
    """Lädt die Arbeitsanweisung eines Aufgabentyps (dritte Ebene) und prüft, dass sie nur einschränkt.

    Rückgabe: {"typ", "werkzeuge" (Menge oder None), "cloud" (bool), "text"}.
    Fehlt die Datei und ist `pflicht` falsch, kommt None zurück. Wirft VerfassungsVerstoss, wenn sie Werkzeuge außerhalb der Gesetze nennt,
    die Cloud für einen nicht freigegebenen Typ öffnet, Rechte vergeben will, unbekannte Kopf-Felder oder falsche Typen hat oder zu groß ist.
    """
    g = gesetze or lade_gesetze()
    if not isinstance(typ, str) or not TYP.fullmatch(typ):
        raise VerfassungsVerstoss("arbeitsanweisungen", f"Ungültiger Aufgabentyp '{typ}'.")
    datei = Path(pfad) if pfad else CONFIG / g["arbeitsanweisungen"]["ordner"] / f"{typ}.md"
    if not datei.is_file():
        if not pflicht:
            return None
        raise VerfassungsVerstoss("arbeitsanweisungen", f"Keine Arbeitsanweisung für '{typ}'.")
    if datei.stat().st_size > MAX_DATEI:
        raise VerfassungsVerstoss("arbeitsanweisungen", f"Arbeitsanweisung '{typ}' ist größer als {MAX_DATEI} Bytes.")
    try:
        roh = datei.read_text(encoding="utf-8").replace("\r\n", "\n")
        kopf, text = {}, roh
        if roh.startswith("---\n"):
            ende = roh.find("\n---\n", 4)
            if ende != -1:
                kopf = yaml.safe_load(roh[4:ende]) or {}
                text = roh[ende + 5:]
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise VerfassungsVerstoss("arbeitsanweisungen", f"Arbeitsanweisung '{typ}' ist nicht lesbar: {type(exc).__name__}.") from exc
    if not isinstance(kopf, dict):
        raise VerfassungsVerstoss("arbeitsanweisungen", f"Der Kopf von '{typ}' muss eine Zuordnung sein.")
    if any(k in kopf for k in ("rechte", "nur_captain")):
        raise VerfassungsVerstoss("arbeitsanweisungen", "Eine Arbeitsanweisung kann keine Rechte vergeben.")
    unbekannt = set(kopf) - KOPF_ERLAUBT
    if unbekannt:
        raise VerfassungsVerstoss("arbeitsanweisungen", f"Arbeitsanweisung '{typ}' hat unbekannte Kopf-Felder: {sorted(map(str, unbekannt))}.")
    if "typ" in kopf and kopf["typ"] != typ:
        raise VerfassungsVerstoss("arbeitsanweisungen", f"Der Kopf nennt den Typ '{kopf['typ']}', die Datei heißt '{typ}'.")
    wz = kopf.get("werkzeuge")
    if wz is not None:
        if not isinstance(wz, list) or not all(isinstance(w, str) for w in wz):
            raise VerfassungsVerstoss("arbeitsanweisungen", f"'werkzeuge' in '{typ}' muss eine Liste von Namen sein.")
        mehr = set(wz) - set(g["werkzeuge"]["erlaubt"])
        if mehr:
            raise VerfassungsVerstoss("arbeitsanweisungen", f"Arbeitsanweisung '{typ}' nennt Werkzeuge außerhalb der Gesetze: {sorted(mehr)}.")
        wz = set(wz)
    cloud = kopf.get("cloud", False)
    if not isinstance(cloud, bool):
        raise VerfassungsVerstoss("arbeitsanweisungen", f"'cloud' in '{typ}' muss wahr oder falsch sein (kein Text).")
    if cloud and typ not in g["cloud_aufgaben"]:
        raise VerfassungsVerstoss("arbeitsanweisungen", f"Arbeitsanweisung '{typ}' öffnet die Cloud für einen nicht freigegebenen Typ.")
    text = text.strip()
    if not text:
        raise VerfassungsVerstoss("arbeitsanweisungen", f"Arbeitsanweisung '{typ}' hat keinen Text.")
    if len(text) > MAX_TEXT:
        raise VerfassungsVerstoss("arbeitsanweisungen", f"Der Text von '{typ}' ist länger als {MAX_TEXT} Zeichen.")
    return {"typ": typ, "werkzeuge": wz, "cloud": cloud, "text": text}


def lade_arbeitsanweisung_fuer_modell(typ, gesetze=None):
    """Die Arbeitsanweisung in der Sprache für Modelle: die freigegebene englische Fassung, wenn sie gültig ist (Hash der deutschen Quelle,
    Freigabe, Struktur, gleicher Kopf), sonst die deutsche. Rückgabe: (Anweisung, "en" oder "de", Gründe gegen die englische Fassung)."""
    from . import uebersetzung
    g = gesetze or lade_gesetze()
    a = lade_arbeitsanweisung(typ, gesetze=g)                       # die deutsche Fassung muss immer gültig sein (Gesetze)
    ordner = CONFIG / g["arbeitsanweisungen"]["ordner"]
    gruende = uebersetzung.pruefe_fassung(typ, ordner)
    if gruende:
        return a, "de", gruende
    _, text_en = uebersetzung.teile((ordner / f"{typ}.en.md").read_text(encoding="utf-8"))
    return {**a, "text": text_en.strip()}, "en", []


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

    def arbeitsanweisung(self, typ, pflicht=True):
        """Arbeitsanweisung für den Aufgabentyp laden; sie darf die Werkzeuge dieses Akteurs nur verkleinern.
        Rückgabe: (Anweisung, Werkzeugmenge für diesen Auftrag); ohne Datei und ohne `pflicht` (None, alle Werkzeuge).
        Verstöße kommen ins Journal."""
        try:
            a = lade_arbeitsanweisung(typ, gesetze=self.g, pflicht=pflicht)
        except VerfassungsVerstoss as exc:
            self._notiere(f"arbeitsanweisung:{typ}", False, str(exc))
            raise
        if a is None:
            return None, set(self.werkzeuge)
        wz = self.werkzeuge if a["werkzeuge"] is None else self.werkzeuge & a["werkzeuge"]
        self._notiere(f"arbeitsanweisung:{typ}", True, "nur eingeschränkt, im Rahmen der Gesetze")
        return a, wz

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
