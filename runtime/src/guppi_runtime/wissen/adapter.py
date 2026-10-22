"""Adapter der Aufnahme (Spec 7, D7.3): Dateien und Ordner unter `repo` oder `projekt` (Markdown, Text, Logbuch), die drei
bestehenden Speicher (`knowledge` JSON-Zeilen, `arbeitsumfeld` und `gateway` SQLite) und die freigegebenen Vorschläge
(`local_config/wissen/vorschlaege.jsonl`). Alle nur lesend: die SQLite-Dateien werden mit `file:…?mode=ro` geöffnet, nie über
ihre Klassen (deren Konstruktoren bauen neu auf, A-10); die Speicher bleiben unverändert (WIS-01).

Ein Adapter liefert `pruefe_pfad` (normierter relativer Pfad oder `wis_pfad_*`), `quell_hash` (billig: Größe, Änderungszeit,
Zeilenzahl – gleich wie beim letzten Abgleich heißt: nichts zerlegen) und `stuecke(quelle, melde)` → `(datei, datum, stueck)`;
übersprungene Dateien meldet er mit `melde(datei, grund)` statt sie zu leeren."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from . import zerlegen

NAMEN = ("markdown", "text", "logbuch", "knowledge", "arbeitsumfeld", "gateway", "vorschlag")
DATEIARTEN = {"*.md", "*.txt"}                                               # G1-S7-c
AUSGELASSEN = {".git", ".venv", "node_modules", "__pycache__", "runtime_data"}
LOGBUCH = "docs/LOGBUCH_AGENT_MANAGER.md"
KNOWLEDGE = "runtime_data/knowledge/records.jsonl"
ARBEITSUMFELD = "local_config/arbeitsumfeld/wissen.sqlite"
GATEWAY = "local_config/gateway/wissen.sqlite"
VORSCHLAEGE = "local_config/wissen/vorschlaege.jsonl"


def _iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha(teile):
    h = hashlib.sha256()
    for t in teile:
        h.update(str(t).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def _datei_hash(path):
    try:
        st = path.stat()
    except OSError:
        return "fehlt"
    return f"{st.st_size}:{st.st_mtime_ns}"


class _Basis:
    name = ""

    def __init__(self, repo_root, projekt_root, *, datei_max_bytes=2_000_000, ziel=zerlegen.ZIEL_ZEICHEN, grenze=zerlegen.MAX_ZEICHEN):
        self.repo_root = Path(repo_root).resolve()
        self.projekt_root = Path(projekt_root).resolve()
        self.datei_max_bytes = datei_max_bytes
        self.ziel, self.grenze = ziel, grenze

    def wurzel(self, quelle):
        return self.repo_root if quelle.get("wurzel") == "repo" else self.projekt_root

    def pruefe_pfad(self, wurzel, pfad, muster=""):
        """Relativer Pfad mit '/' unter der Wurzel; Laufwerksbuchstabe oder führender Schrägstrich → `wis_pfad_absolut`,
        `..` oder ein Ziel außerhalb → `wis_pfad_ausserhalb`."""
        pfad = str(pfad or "").strip().replace("\\", "/")
        if not pfad or pfad.startswith("/") or (len(pfad) > 1 and pfad[1] == ":"):
            raise ValueError("wis_pfad_absolut")
        rein = PurePosixPath(pfad)
        if ".." in rein.parts:
            raise ValueError("wis_pfad_ausserhalb")
        wurzel = Path(wurzel).resolve()
        ziel = (wurzel / Path(*rein.parts)).resolve()
        if ziel != wurzel and wurzel not in ziel.parents:
            raise ValueError("wis_pfad_ausserhalb")
        return str(PurePosixPath(*rein.parts))

    def _lies_text(self, path):
        """UTF-8 streng, höchstens `datei_max_bytes`; sonst `wis_datei_zu_gross` / `wis_text_kein_utf8` / `wis_speicher_nicht_lesbar`."""
        try:
            if path.stat().st_size > self.datei_max_bytes:
                raise ValueError("wis_datei_zu_gross")
            return path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("wis_text_kein_utf8") from None
        except OSError:
            raise ValueError("wis_speicher_nicht_lesbar") from None


class DateiAdapter(_Basis):
    """`markdown` und `text`: eine Datei oder ein Ordner (nur `*.md`, `*.txt`), Stelle = Überschriftenpfad bzw. Dateiname."""
    name = "markdown"

    def __init__(self, *args, name="markdown", **kw):
        super().__init__(*args, **kw)
        self.name = name

    def pruefe_pfad(self, wurzel, pfad, muster="*.md"):
        rel = super().pruefe_pfad(wurzel, pfad, muster)
        for m in str(muster or "*.md").split(","):
            if m.strip() not in DATEIARTEN:
                raise ValueError("wis_dateiart_nicht_erlaubt")
        return rel

    def _dateien(self, quelle):
        wurzel = self.wurzel(quelle)
        start = wurzel / Path(*PurePosixPath(quelle["pfad"]).parts)
        if start.is_file():
            if "*" + start.suffix.lower() not in DATEIARTEN:
                raise ValueError("wis_dateiart_nicht_erlaubt")
            return [start]
        if not start.is_dir():
            raise ValueError("wis_speicher_nicht_lesbar")
        muster = [m.strip() for m in str(quelle.get("muster") or "*.md").split(",")]
        out = []
        for p in sorted(start.rglob("*")):
            if not p.is_file() or p.is_symlink() or any(part in AUSGELASSEN or part.startswith(".") for part in p.relative_to(start).parts[:-1]):
                continue
            if any(p.match(m) for m in muster):
                out.append(p)
        return out

    def quell_hash(self, quelle):
        try:
            dateien = self._dateien(quelle)
        except ValueError as exc:
            return str(exc)
        wurzel = self.wurzel(quelle)
        return _sha((p.relative_to(wurzel).as_posix(), _datei_hash(p)) for p in dateien)

    def stuecke(self, quelle, melde=None):
        wurzel = self.wurzel(quelle)
        for p in self._dateien(quelle):
            rel = p.relative_to(wurzel).as_posix()
            try:
                text = self._lies_text(p)
            except ValueError as exc:
                if melde:
                    melde(rel, str(exc))
                continue
            datum = _iso(p.stat().st_mtime)
            if self.name == "markdown" and p.suffix.lower() == ".md":
                teile = zerlegen.zerlege_markdown(text, p.name, ziel=self.ziel, grenze=self.grenze)
            else:
                teile = zerlegen.zerlege_text(text, p.name, ziel=self.ziel, grenze=self.grenze)
            for s in teile:
                yield rel, datum, s


class LogbuchAdapter(DateiAdapter):
    """`logbuch`: das Logbuch des Agent Managers, eine Tabellenzeile je Abschnitt, Datum aus der Zeile."""
    name = "logbuch"

    def __init__(self, *args, **kw):
        super().__init__(*args, name="logbuch", **kw)

    def stuecke(self, quelle, melde=None):
        wurzel = self.wurzel(quelle)
        for p in self._dateien(quelle):
            rel = p.relative_to(wurzel).as_posix()
            try:
                text = self._lies_text(p)
            except ValueError as exc:
                if melde:
                    melde(rel, str(exc))
                continue
            datum = _iso(p.stat().st_mtime)
            for s in zerlegen.zerlege_logbuch(text, p.name):
                zeile = s["stelle"].split(" > Zeile ", 1)
                stempel = zeile[1][:16].strip() if len(zeile) == 2 else ""
                yield rel, (stempel.replace(" ", "T") if stempel[:4].isdigit() else datum), s


class KnowledgeAdapter(_Basis):
    """`knowledge`: JSON-Zeilen des `KnowledgeStore` (nur `status == 'active'`): Notiz oder Lektion mit Auslösewörtern."""
    name = "knowledge"

    def _pfad(self, quelle):
        return self.wurzel(quelle) / Path(*PurePosixPath(quelle.get("pfad") or KNOWLEDGE).parts)

    def quell_hash(self, quelle):
        return _datei_hash(self._pfad(quelle))

    def _zeilen(self, quelle):
        p = self._pfad(quelle)
        if not p.is_file():
            return []
        out = []
        for line in self._lies_text(p).splitlines():
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
        return out

    def stuecke(self, quelle, melde=None):
        for r in self._zeilen(quelle):
            if not isinstance(r, dict) or r.get("status") != "active" or not r.get("id"):
                continue
            art = "Lektion" if r.get("type") == "coding_lesson" else "Notiz"
            inhalt = r.get("content") or {}
            text = str(inhalt.get("summary") or "")
            tags = [str(t) for t in (r.get("scope") or {}).get("tags") or []]
            if tags:
                text += "\nAuslöser: " + ", ".join(tags)
            datum = str((r.get("provenance") or {}).get("created_at") or "")[:19] or "1970-01-01T00:00:00Z"
            for s in zerlegen.zerlege_eintrag(f"{art} {r.get('title') or r['id']}", text, ziel=self.ziel, grenze=self.grenze):
                yield f"knowledge:{r['id']}", datum, s


class _SqliteAdapter(_Basis):
    """Gemeinsames Lesen einer fremden SQLite-Datei: nur `mode=ro`, nie über die Klasse des Besitzers."""

    def _datei(self, quelle):
        pfad = str(quelle.get("pfad") or "").split("#", 1)[0]
        return self.wurzel(quelle) / Path(*PurePosixPath(pfad).parts)

    def _lesend(self, path):
        if not path.is_file():
            raise ValueError("wis_speicher_nicht_lesbar")
        try:
            db = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=5)
            db.row_factory = sqlite3.Row
            return db
        except sqlite3.Error:
            raise ValueError("wis_speicher_nicht_lesbar") from None

    def _zeilen(self, quelle, sql):
        db = self._lesend(self._datei(quelle))
        try:
            return [dict(r) for r in db.execute(sql)]
        except sqlite3.Error:
            raise ValueError("wis_speicher_nicht_lesbar") from None
        finally:
            db.close()

    def quell_hash(self, quelle):
        p = self._datei(quelle)
        try:
            n = self._zeilen(quelle, f"SELECT count(*) AS n FROM {self.tabelle(quelle)}")[0]["n"]
        except ValueError as exc:
            return str(exc)
        return f"{_datei_hash(p)}:{n}"


class ArbeitsumfeldAdapter(_SqliteAdapter):
    """`arbeitsumfeld`: Tabelle `wissen(id, art, titel, text, quelle, version)`; Stelle = Titel (trägt die Art), Text + Quelle."""
    name = "arbeitsumfeld"

    def tabelle(self, quelle):
        return "wissen"

    def stuecke(self, quelle, melde=None):
        datum = _iso(self._datei(quelle).stat().st_mtime)
        for r in self._zeilen(quelle, "SELECT id, art, titel, text, quelle FROM wissen ORDER BY id"):
            text = str(r.get("text") or "")
            if r.get("quelle"):
                text += "\nQuelle: " + str(r["quelle"])
            for s in zerlegen.zerlege_eintrag(str(r.get("titel") or r["id"]), text, ziel=self.ziel, grenze=self.grenze):
                yield f"arbeitsumfeld:{r['id']}", datum, s


class GatewayAdapter(_SqliteAdapter):
    """`gateway`: `#wissen` (Regelbuch, Zustände, Fehler, Begriffe: Stelle = Titel, Text + „Was tun“) und `#eigene` (freie
    Einträge des Nutzers, Vorgabe Personenbezug = ja: Stelle „Eigene Frage“, Frage + Antwort)."""
    name = "gateway"

    def _teil(self, quelle):
        return str(quelle.get("pfad") or "").split("#", 1)[1] if "#" in str(quelle.get("pfad") or "") else "wissen"

    def tabelle(self, quelle):
        return "eigene" if self._teil(quelle) == "eigene" else "wissen"

    def stuecke(self, quelle, melde=None):
        datum = _iso(self._datei(quelle).stat().st_mtime)
        if self._teil(quelle) == "eigene":
            for r in self._zeilen(quelle, "SELECT id, frage, antwort, erstellt FROM eigene ORDER BY id"):
                text = "Frage: " + str(r.get("frage") or "") + "\nAntwort: " + str(r.get("antwort") or "")
                for s in zerlegen.zerlege_eintrag("Eigene Frage", text, ziel=self.ziel, grenze=self.grenze):
                    yield f"gateway:eigene:{r['id']}", str(r.get("erstellt") or datum)[:20] or datum, s
            return
        for r in self._zeilen(quelle, "SELECT id, art, titel, text, tun FROM wissen ORDER BY id"):
            text = str(r.get("text") or "")
            if r.get("tun"):
                text += "\nWas tun: " + str(r["tun"])
            for s in zerlegen.zerlege_eintrag(str(r.get("titel") or r["id"]), text, ziel=self.ziel, grenze=self.grenze):
                yield f"gateway:{r['id']}", datum, s


class VorschlagAdapter(_Basis):
    """`vorschlag`: freigegebene Vorschläge aus `vorschlaege.jsonl`, je Quelle die Zeilen mit gleicher Stufe, gleichem Projekt und
    gleichem Personenbezug (Quelle `Q-VS-<stufe>-<projekt>-<p>`, D7.8); ein Neuaufbau liest sie von dort."""
    name = "vorschlag"

    def _pfad(self, quelle):
        return self.projekt_root / Path(*PurePosixPath(VORSCHLAEGE).parts)

    def quell_hash(self, quelle):
        return _datei_hash(self._pfad(quelle))

    def stuecke(self, quelle, melde=None):
        p = self._pfad(quelle)
        if not p.is_file():
            return
        for line in self._lies_text(p).splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if not isinstance(r, dict) or not r.get("id"):
                continue
            if (int(r.get("stufe", -1)), r.get("projekt"), int(bool(r.get("personenbezug")))) != (int(quelle["stufe"]), quelle.get("projekt"), int(quelle["personenbezug"])):
                continue
            for s in zerlegen.zerlege_eintrag("Vorschlag " + str(r.get("titel") or r["id"]), str(r.get("text") or ""), ziel=self.ziel, grenze=self.grenze):
                yield f"vorschlag:{r['id']}", str(r.get("freigegeben") or "")[:20] or "1970-01-01T00:00:00Z", s


def adapter_fuer(name, *, repo_root, projekt_root, **kw):
    """Der Adapter zu seinem Namen; unbekannt → `wis_adapter_unbekannt`."""
    if name == "markdown":
        return DateiAdapter(repo_root, projekt_root, name="markdown", **kw)
    if name == "text":
        return DateiAdapter(repo_root, projekt_root, name="text", **kw)
    if name == "logbuch":
        return LogbuchAdapter(repo_root, projekt_root, **kw)
    if name == "knowledge":
        return KnowledgeAdapter(repo_root, projekt_root, **kw)
    if name == "arbeitsumfeld":
        return ArbeitsumfeldAdapter(repo_root, projekt_root, **kw)
    if name == "gateway":
        return GatewayAdapter(repo_root, projekt_root, **kw)
    if name == "vorschlag":
        return VorschlagAdapter(repo_root, projekt_root, **kw)
    raise ValueError("wis_adapter_unbekannt")


# Vorgaben für die Erstbestückung (G2-S7-l): Pfad je Adapter, Stufe und Personenbezug; der Captain ändert sie im Antrag.
ERSTBESTUECKUNG = (
    {"adapter": "markdown", "wurzel": "repo", "pfad": "docs", "muster": "*.md", "art": "ordner", "stufe": 1, "personenbezug": 0},
    {"adapter": "logbuch", "wurzel": "repo", "pfad": LOGBUCH, "muster": "*.md", "art": "datei", "stufe": 1, "personenbezug": 0},
    {"adapter": "knowledge", "wurzel": "projekt", "pfad": KNOWLEDGE, "muster": "", "art": "speicher", "stufe": 1, "personenbezug": 0},
    {"adapter": "arbeitsumfeld", "wurzel": "projekt", "pfad": ARBEITSUMFELD, "muster": "", "art": "speicher", "stufe": 1, "personenbezug": 0},
    {"adapter": "gateway", "wurzel": "projekt", "pfad": GATEWAY + "#wissen", "muster": "", "art": "speicher", "stufe": 1, "personenbezug": 0},
    {"adapter": "gateway", "wurzel": "projekt", "pfad": GATEWAY + "#eigene", "muster": "", "art": "speicher", "stufe": 3, "personenbezug": 1},
)
