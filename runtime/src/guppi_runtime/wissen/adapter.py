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

from . import wurzeln as wurzeln_mod
from . import zerlegen

NAMEN = ("markdown", "text", "logbuch", "knowledge", "arbeitsumfeld", "gateway", "vorschlag", "dokumente")
DATEIARTEN = {"*.md", "*.txt"}                                               # G1-S7-c
DOKUMENTARTEN = {"*.md", "*.txt", "*.docx", "*.csv", "*.pdf", "*.xlsx", "*.pptx"}   # K5-3/K5-4 (WK-20); pdf/xlsx/pptx über die Hilfswerkzeuge
GRENZEN_VORGABE = {"md": 20_000_000, "txt": 20_000_000, "csv": 50_000_000, "docx": 50_000_000}   # K5-5 (D-K5-5), Bytes je Datei
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


def _unter(pfad, wurzel_echt):
    """Liegt die aufgelöste Datei (Verknüpfungen und Junctions aufgelöst) unter der aufgelösten Wurzel? Nicht lesbar zählt als außerhalb."""
    try:
        echt = Path(pfad).resolve()
    except (OSError, RuntimeError):
        return False
    return echt == wurzel_echt or wurzel_echt in echt.parents


class _Basis:
    name = ""

    def __init__(self, repo_root, projekt_root, *, datei_max_bytes=2_000_000, ziel=zerlegen.ZIEL_ZEICHEN, grenze=zerlegen.MAX_ZEICHEN, wurzeln=None, je_art=None):
        self.je_art = dict(je_art or {})                           # K5-5 (WK-25): Grenze je Dateiart; fehlt eine Art, gilt datei_max_bytes
        self.repo_root = Path(repo_root).resolve()
        self.projekt_root = Path(projekt_root).resolve()
        self.datei_max_bytes = datei_max_bytes
        self.ziel, self.grenze = ziel, grenze
        self.wurzeln = dict(wurzeln or {})                         # K5 (WK-21): freigegebene Ordner, Kennung → Pfad (wissen/wurzeln.py)

    def wurzel(self, quelle):
        """`repo`, `projekt` oder ein freigegebener Ordner `w:<id>`; ein unbekannter Ordner ist `wis_wurzel_unbekannt` (die Quelle wird übersprungen, nie geleert)."""
        w = quelle.get("wurzel")
        if w == "repo":
            return self.repo_root
        if w in ("projekt", None, ""):
            return self.projekt_root
        wid = wurzeln_mod.kennung(w)
        if wid and wid in self.wurzeln:
            return Path(self.wurzeln[wid]).resolve()
        raise ValueError("wis_wurzel_unbekannt")

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

    @staticmethod
    def _bleibt_drin(path, wurzel):
        """Liegt `path` nach Auflösen aller Symlinks und Junctions noch unter der Wurzel? Die Freigabe prüft den Pfad nur einmal;
        ein später angelegter Link darf nicht aus der Wurzel hinausführen (G4-Auflage 2, Prüfung F7)."""
        return _unter(path, Path(wurzel).resolve())

    @staticmethod
    def _ist_link(path):
        path = Path(path)
        return path.is_symlink() or bool(getattr(path, "is_junction", lambda: False)())

    def grenze_fuer(self, path):
        """Die Grenze in Bytes für diese Datei: je Art (K5-5), sonst `datei_max_bytes`."""
        return int(self.je_art.get(path.suffix.lower().lstrip("."), self.datei_max_bytes))

    def _pruefe_groesse(self, path):
        try:
            if path.stat().st_size > self.grenze_fuer(path):
                raise ValueError("wis_datei_zu_gross")
        except OSError:
            raise ValueError("wis_speicher_nicht_lesbar") from None

    def _lies_text(self, path):
        """UTF-8 streng, höchstens die Grenze der Art; sonst `wis_datei_zu_gross` / `wis_text_kein_utf8` / `wis_speicher_nicht_lesbar`."""
        try:
            if path.stat().st_size > self.grenze_fuer(path):
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

    arten = DATEIARTEN

    def pruefe_pfad(self, wurzel, pfad, muster="*.md"):
        rel = super().pruefe_pfad(wurzel, pfad, muster)
        for m in str(muster or "*.md").split(","):
            if m.strip() not in self.arten:
                raise ValueError("wis_dateiart_nicht_erlaubt")
        return rel

    def _dateien(self, quelle):
        wurzel = self.wurzel(quelle)
        start = wurzel / Path(*PurePosixPath(quelle["pfad"]).parts)
        if not self._bleibt_drin(start, wurzel):
            raise ValueError("wis_pfad_ausserhalb")
        if start.is_file():
            if "*" + start.suffix.lower() not in self.arten:
                raise ValueError("wis_dateiart_nicht_erlaubt")
            return [start]
        if not start.is_dir():
            raise ValueError("wis_speicher_nicht_lesbar")
        muster = [m.strip() for m in str(quelle.get("muster") or "*.md").split(",")]
        out = []
        wurzel_echt = wurzel.resolve()
        for p in sorted(start.rglob("*")):
            if not p.is_file() or self._ist_link(p) or any(part in AUSGELASSEN or part.startswith(".") for part in p.relative_to(start).parts[:-1]):
                continue
            if not _unter(p, wurzel_echt):                           # Ordner-Junction oder Link auf dem Weg nach draußen (Auflage 2, F7)
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

    def datei_liste(self, quelle):
        """K5 (Abgleich je Datei): [(relativer Pfad, Pfad, Hash „Größe:mtime_ns“)] der Dateien dieser Quelle."""
        wurzel = self.wurzel(quelle)
        return [(p.relative_to(wurzel).as_posix(), p, _datei_hash(p)) for p in self._dateien(quelle)]

    def stuecke_datei(self, quelle, path):
        """Die Abschnitte EINER Datei als [(rel, datum, stück)]; nicht lesbar → ValueError mit Code (der Abgleich vermerkt die Datei als übersprungen)."""
        rel = path.relative_to(self.wurzel(quelle)).as_posix()
        text = self._lies_text(path)
        datum = _iso(path.stat().st_mtime)
        if self.name == "markdown" and path.suffix.lower() == ".md":
            teile = zerlegen.zerlege_markdown(text, path.name, ziel=self.ziel, grenze=self.grenze)
        else:
            teile = zerlegen.zerlege_text(text, path.name, ziel=self.ziel, grenze=self.grenze)
        return [(rel, datum, s) for s in teile]

    def stuecke(self, quelle, melde=None):
        wurzel = self.wurzel(quelle)
        for p in self._dateien(quelle):
            try:
                teile = self.stuecke_datei(quelle, p)
            except ValueError as exc:
                if melde:
                    melde(p.relative_to(wurzel).as_posix(), str(exc))
                continue
            yield from teile


class DokumenteAdapter(DateiAdapter):
    """`dokumente` (K5-3, WK-20): ein Ordner oder eine Datei mit Markdown, Text, Word und CSV. Jede Art wird zu Markdown (wissen/leser),
    dann wie eine Markdown-Datei zerlegt; die Grenze gilt je Art (K5-5)."""
    name = "dokumente"
    arten = DOKUMENTARTEN

    def __init__(self, repo_root, projekt_root, *, umwandeln_s=60.0, **kw):
        super().__init__(repo_root, projekt_root, name="dokumente", **kw)
        self.umwandeln_s = umwandeln_s                             # K5-4 (D-K5-3): Zeitgrenze für das Umwandeln im eigenen Prozess

    def stuecke_datei(self, quelle, path):
        endung = path.suffix.lower()
        if endung in (".md", ".txt"):
            self.name = "markdown"                                 # Markdown zerlegt nach Köpfen, Text nach Absätzen (wie bisher)
            try:
                return super().stuecke_datei(quelle, path)
            finally:
                self.name = "dokumente"
        from .leser import docx as docx_leser, extern, tabelle
        rel = path.relative_to(self.wurzel(quelle)).as_posix()
        self._pruefe_groesse(path)
        if endung in extern.ARTEN:                                 # K5-4: PDF, Excel, PowerPoint – MarkItDown, für PDF sonst pypdf, im eigenen Prozess
            text = extern.markdown(path, zeitgrenze=self.umwandeln_s)
        else:
            text = docx_leser.markdown(path) if endung == ".docx" else tabelle.markdown(path) if endung == ".csv" else None
        if text is None:
            raise ValueError("wis_dateiart_nicht_erlaubt")
        datum = _iso(path.stat().st_mtime)
        return [(rel, datum, s) for s in zerlegen.zerlege_markdown(text, path.name, ziel=self.ziel, grenze=self.grenze)]


class LogbuchAdapter(DateiAdapter):
    """`logbuch`: das Logbuch des Agent Managers, eine Tabellenzeile je Abschnitt, Datum aus der Zeile."""
    name = "logbuch"

    def __init__(self, *args, **kw):
        super().__init__(*args, name="logbuch", **kw)

    def stuecke_datei(self, quelle, path):
        rel = path.relative_to(self.wurzel(quelle)).as_posix()
        text = self._lies_text(path)
        datum = _iso(path.stat().st_mtime)
        out = []
        for s in zerlegen.zerlege_logbuch(text, path.name):
            zeile = s["stelle"].split(" > Zeile ", 1)
            stempel = zeile[1][:16].strip() if len(zeile) == 2 else ""
            out.append((rel, (stempel.replace(" ", "T") if stempel[:4].isdigit() else datum), s))
        return out


class KnowledgeAdapter(_Basis):
    """`knowledge`: JSON-Zeilen des `KnowledgeStore` (nur `status == 'active'`): Notiz oder Lektion mit Auslösewörtern."""
    name = "knowledge"

    def _pfad(self, quelle):
        p = self.wurzel(quelle) / Path(*PurePosixPath(quelle.get("pfad") or KNOWLEDGE).parts)
        if not self._bleibt_drin(p, self.wurzel(quelle)):
            raise ValueError("wis_pfad_ausserhalb")
        return p

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
            datum = str((r.get("provenance") or {}).get("created_at") or "")[:20] or "1970-01-01T00:00:00Z"
            for s in zerlegen.zerlege_eintrag(f"{art} {r.get('title') or r['id']}", text, ziel=self.ziel, grenze=self.grenze):
                yield f"knowledge:{r['id']}", datum, s


class _SqliteAdapter(_Basis):
    """Gemeinsames Lesen einer fremden SQLite-Datei: nur `mode=ro`, nie über die Klasse des Besitzers."""

    def _datei(self, quelle):
        pfad = str(quelle.get("pfad") or "").split("#", 1)[0]
        p = self.wurzel(quelle) / Path(*PurePosixPath(pfad).parts)
        if not self._bleibt_drin(p, self.wurzel(quelle)):
            raise ValueError("wis_pfad_ausserhalb")
        return p

    def _datum(self, quelle):
        try:
            return _iso(self._datei(quelle).stat().st_mtime)
        except OSError:
            raise ValueError("wis_speicher_nicht_lesbar") from None

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
        datum = self._datum(quelle)
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
        datum = self._datum(quelle)
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
    if name == "dokumente":
        return DokumenteAdapter(repo_root, projekt_root, **kw)
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
