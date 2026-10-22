"""Das Gedächtnis des Wissensspeichers (Spec 7, D7.2, D7.3; Bau-Spec `wis_store`): Tabellen als versionierte Migrationen,
Meta-Werte, der Abgleich alter und neuer Abschnitte einer Quelle, sein Anwenden in einer Transaktion, die stabile Abschnitts-ID,
die offenen Vektoren und der Modellwechsel.

Rein: nur `sqlite3`, `hashlib`, `json`; keine Uhr (jeder Zeitpunkt ist ein Argument), keine Datei außer der übergebenen Verbindung.
Die Verbindung öffnet der Aufrufer mit `oeffne_db` (Zeilen als `sqlite3.Row`, keine stille Transaktion, Fremdschlüssel an).
Jedes Schreiben läuft in `BEGIN IMMEDIATE … COMMIT` (ROLLBACK bei jedem Fehler); eine Ablehnung (`ValueError` mit Code) kommt,
bevor etwas geschrieben ist. Die Migrationen sind die Saat `benchmarks/wis_schema_seed/wis_ddl.py`; nur anhängen, nie ändern."""
import hashlib
import json
import sqlite3
from contextlib import contextmanager

MIGRATIONEN = (
    (1, "Grundschema Spec 7 (quellen, abschnitte, FTS5, vektoren, vorschlaege, laeufe)", """
CREATE TABLE meta (schluessel TEXT PRIMARY KEY, wert TEXT NOT NULL);
CREATE TABLE migrationen (version INTEGER PRIMARY KEY, angewendet TEXT NOT NULL, beschreibung TEXT NOT NULL);
CREATE TABLE quellen (
  id TEXT PRIMARY KEY,
  art TEXT NOT NULL CHECK (art IN ('datei','ordner','speicher','vorschlaege')),
  adapter TEXT NOT NULL CHECK (adapter IN ('markdown','text','logbuch','knowledge','arbeitsumfeld','gateway','vorschlag')),
  wurzel TEXT NOT NULL CHECK (wurzel IN ('repo','projekt')),
  pfad TEXT NOT NULL,
  muster TEXT NOT NULL DEFAULT '*.md',
  freigabe_gate TEXT NOT NULL,
  freigabe_mission TEXT NOT NULL,
  stufe INTEGER NOT NULL CHECK (stufe BETWEEN 0 AND 6),
  projekt TEXT,
  personenbezug INTEGER NOT NULL CHECK (personenbezug IN (0,1)),
  aktiv INTEGER NOT NULL DEFAULT 1,
  stand TEXT,
  quell_hash TEXT,
  erstellt TEXT NOT NULL
);
CREATE TABLE abschnitte (
  nr INTEGER PRIMARY KEY AUTOINCREMENT,
  id TEXT NOT NULL UNIQUE,
  quelle TEXT NOT NULL REFERENCES quellen(id) ON DELETE CASCADE,
  datei TEXT NOT NULL,
  stelle TEXT NOT NULL,
  teil INTEGER NOT NULL DEFAULT 1,
  text TEXT NOT NULL,
  hash TEXT NOT NULL,
  datum TEXT NOT NULL,
  aufgenommen TEXT NOT NULL,
  befunde TEXT NOT NULL DEFAULT '[]',
  zeichen INTEGER NOT NULL,
  UNIQUE (quelle, datei, stelle, teil)
);
CREATE INDEX abschnitte_quelle ON abschnitte(quelle);
CREATE VIRTUAL TABLE abschnitte_fts USING fts5(stelle, text, content='abschnitte', content_rowid='nr', tokenize='unicode61 remove_diacritics 2');
CREATE TRIGGER abschnitte_ai AFTER INSERT ON abschnitte BEGIN
  INSERT INTO abschnitte_fts(rowid, stelle, text) VALUES (new.nr, new.stelle, new.text); END;
CREATE TRIGGER abschnitte_ad AFTER DELETE ON abschnitte BEGIN
  INSERT INTO abschnitte_fts(abschnitte_fts, rowid, stelle, text) VALUES ('delete', old.nr, old.stelle, old.text); END;
CREATE TRIGGER abschnitte_au AFTER UPDATE ON abschnitte BEGIN
  INSERT INTO abschnitte_fts(abschnitte_fts, rowid, stelle, text) VALUES ('delete', old.nr, old.stelle, old.text);
  INSERT INTO abschnitte_fts(rowid, stelle, text) VALUES (new.nr, new.stelle, new.text); END;
CREATE VIRTUAL TABLE abschnitte_vocab USING fts5vocab(abschnitte_fts, 'row');
CREATE TABLE vektoren (
  abschnitt INTEGER PRIMARY KEY REFERENCES abschnitte(nr) ON DELETE CASCADE,
  modell_id TEXT NOT NULL,
  dim INTEGER NOT NULL,
  hash TEXT NOT NULL,
  blob BLOB NOT NULL CHECK (length(blob) = 4 * dim)
);
CREATE INDEX vektoren_modell ON vektoren(modell_id);
CREATE TABLE vorschlaege (
  id TEXT PRIMARY KEY,
  titel TEXT NOT NULL, text TEXT NOT NULL, hash TEXT NOT NULL,
  agent_id TEXT, lauf_id TEXT, aufgabe_id TEXT,
  belege TEXT NOT NULL DEFAULT '[]',
  vorschlag_stufe INTEGER NOT NULL, vorschlag_projekt TEXT, personenbezug INTEGER NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('offen','freigegeben','abgelehnt','veraltet')),
  mission_id TEXT, erstellt TEXT NOT NULL, entschieden TEXT
);
CREATE TABLE laeufe (
  id INTEGER PRIMARY KEY AUTOINCREMENT, art TEXT NOT NULL CHECK (art IN ('abgleich','einbetten','neuaufbau')),
  start TEXT NOT NULL, ende TEXT, geraet TEXT CHECK (geraet IN ('gpu','cpu')), lease INTEGER NOT NULL DEFAULT 0,
  neu INTEGER DEFAULT 0, geaendert INTEGER DEFAULT 0, entfernt INTEGER DEFAULT 0, eingebettet INTEGER DEFAULT 0,
  pause_grund TEXT, status TEXT NOT NULL CHECK (status IN ('laeuft','fertig','pausiert','abgebrochen'))
);
"""),
)
SCHEMA_VERSION = len(MIGRATIONEN)
FELDER = ("datei", "stelle", "teil", "text", "hash", "datum")


def oeffne_db(path, *, check_same_thread=True):
    """Verbindung mit den Einstellungen des Speichers: Zeilen als `sqlite3.Row`, keine stille Transaktion, Fremdschlüssel an,
    30 s Wartezeit bei Sperren. `check_same_thread=False` für die Fassade (Takt und Desk teilen eine Verbindung unter Sperre)."""
    db = sqlite3.connect(str(path), isolation_level=None, check_same_thread=check_same_thread)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA busy_timeout = 30000")
    return db


@contextmanager
def _immediate(db):
    db.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        db.execute("ROLLBACK")
        raise
    db.execute("COMMIT")


def _tabelle_da(db, name):
    return db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone() is not None


def migriere(db, *, jetzt):
    """Fehlende Migrationen anwenden, je eine in eigener Transaktion; Rückgabe die jetzt angewandten Versionen.
    `wis_schema_kaputt` (quick_check), `wis_schema_neuer` (Datei neuer als der Code: nichts wird geschrieben)."""
    if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        raise ValueError("wis_schema_kaputt")
    stand = db.execute("SELECT COALESCE(MAX(version), 0) FROM migrationen").fetchone()[0] if _tabelle_da(db, "migrationen") else 0
    if stand > SCHEMA_VERSION:
        raise ValueError("wis_schema_neuer")
    angewendet = []
    for version, beschreibung, sql in MIGRATIONEN:
        if version <= stand:
            continue
        db.executescript("BEGIN IMMEDIATE;" + sql)
        db.execute("INSERT INTO migrationen (version, angewendet, beschreibung) VALUES (?, ?, ?)", (version, jetzt, beschreibung))
        db.execute("INSERT OR REPLACE INTO meta (schluessel, wert) VALUES ('schema_version', ?)", (str(version),))
        db.execute("COMMIT")
        angewendet.append(version)
    return angewendet


def lies_meta(db):
    """Alle Meta-Werte als dict (Schlüssel → Text)."""
    return {r["schluessel"]: r["wert"] for r in db.execute("SELECT schluessel, wert FROM meta ORDER BY schluessel")}


def setze_meta(db, werte):
    """Jeden Eintrag als Text schreiben (INSERT OR REPLACE), eine Transaktion."""
    with _immediate(db):
        db.executemany("INSERT OR REPLACE INTO meta (schluessel, wert) VALUES (?, ?)", [(str(k), str(v)) for k, v in dict(werte).items()])


def abschnitt_id(quelle_id, datei, stelle, teil, belegt):
    """Stabile ID: 'W' + 10 Hex aus sha256(quelle|datei|stelle|teil); solange `belegt(id)` wahr ist, zwei Zeichen mehr (bis 64)."""
    voll = hashlib.sha256(f"{quelle_id}|{datei}|{stelle}|{teil}".encode("utf-8")).hexdigest()
    for n in range(10, 65, 2):
        kandidat = "W" + voll[:n]
        if not belegt(kandidat):
            return kandidat
    raise ValueError("wis_id_kollision")


def _pruefe(abschnitt):
    """Form eines neuen Abschnitts: dict mit den sechs Feldern, `teil` int >= 1, die übrigen nicht leere Texte."""
    if not isinstance(abschnitt, dict) or any(k not in abschnitt for k in FELDER):
        raise ValueError("wis_abschnitt_ungueltig")
    if type(abschnitt["teil"]) is not int or abschnitt["teil"] < 1 or not all(isinstance(abschnitt[k], str) and abschnitt[k] for k in FELDER if k != "teil"):
        raise ValueError("wis_abschnitt_ungueltig")
    return (abschnitt["datei"], abschnitt["stelle"], abschnitt["teil"])


def vergleiche(db, quelle_id, abschnitte):
    """Nur lesen: {"neu": [dict], "geaendert": [(nr, dict)], "entfernt": [nr], "gleich": n} gegen die Zeilen dieser Quelle.
    Die Eingabe-dicts kommen unverändert als dieselben Objekte zurück."""
    alt = {(r["datei"], r["stelle"], r["teil"]): (r["nr"], r["hash"]) for r in
           db.execute("SELECT nr, datei, stelle, teil, hash FROM abschnitte WHERE quelle = ?", (quelle_id,))}
    neu, geaendert, gesehen, gleich = [], [], set(), 0
    for a in abschnitte:
        key = _pruefe(a)
        if key in gesehen:
            raise ValueError("wis_abschnitt_doppelt")
        gesehen.add(key)
        if key not in alt:
            neu.append(a)
        elif alt[key][1] != a["hash"]:
            geaendert.append((alt[key][0], a))
        else:
            gleich += 1
    entfernt = sorted(nr for key, (nr, _) in alt.items() if key not in gesehen)
    return {"neu": neu, "geaendert": geaendert, "entfernt": entfernt, "gleich": gleich}


def _befunde(abschnitt):
    return json.dumps(list(abschnitt.get("befunde") or []))


def wende_an(db, quelle_id, abgleich, *, jetzt):
    """Ein Ergebnis von `vergleiche` in EINER Transaktion anwenden: entfernen, ändern (ID und nr bleiben), einfügen, `quellen.stand`.
    Rückgabe die Zählung {"neu", "geaendert", "entfernt"}. FTS5 folgt über die Trigger."""
    if db.execute("SELECT 1 FROM quellen WHERE id = ?", (quelle_id,)).fetchone() is None:
        raise ValueError("wis_quelle_unbekannt")
    for a in list(abgleich["neu"]) + [a for _, a in abgleich["geaendert"]]:
        _pruefe(a)
    belegt = lambda i: db.execute("SELECT 1 FROM abschnitte WHERE id = ?", (i,)).fetchone() is not None
    with _immediate(db):
        for nr in abgleich["entfernt"]:
            db.execute("DELETE FROM abschnitte WHERE nr = ? AND quelle = ?", (nr, quelle_id))
        for nr, a in abgleich["geaendert"]:
            db.execute("UPDATE abschnitte SET text = ?, hash = ?, datum = ?, aufgenommen = ?, befunde = ?, zeichen = ? WHERE nr = ? AND quelle = ?",
                       (a["text"], a["hash"], a["datum"], jetzt, _befunde(a), len(a["text"]), nr, quelle_id))
        for a in abgleich["neu"]:
            db.execute("INSERT INTO abschnitte (id, quelle, datei, stelle, teil, text, hash, datum, aufgenommen, befunde, zeichen) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                       (abschnitt_id(quelle_id, a["datei"], a["stelle"], a["teil"], belegt), quelle_id, a["datei"], a["stelle"], a["teil"],
                        a["text"], a["hash"], a["datum"], jetzt, _befunde(a), len(a["text"])))
        db.execute("UPDATE quellen SET stand = ? WHERE id = ?", (jetzt, quelle_id))
    return {"neu": len(abgleich["neu"]), "geaendert": len(abgleich["geaendert"]), "entfernt": len(abgleich["entfernt"])}


def offene_vektoren(db, modell_id, limit):
    """Abschnitte ohne Vektor dieses Modells zum aktuellen Hash, nach nr: [(nr, eingabetext 'stelle\\ntext', hash)], höchstens `limit`."""
    if type(limit) is not int or limit < 1:
        raise ValueError("wis_limit_ungueltig")
    rows = db.execute("SELECT a.nr, a.stelle, a.text, a.hash FROM abschnitte a LEFT JOIN vektoren v ON v.abschnitt = a.nr AND v.modell_id = ? AND v.hash = a.hash "
                      "WHERE v.abschnitt IS NULL ORDER BY a.nr LIMIT ?", (modell_id, limit))
    return [(r["nr"], r["stelle"] + "\n" + r["text"], r["hash"]) for r in rows]


def schreibe_vektoren(db, modell_id, dim, zeilen):
    """Vektoren schreiben (INSERT OR REPLACE), eine Transaktion; `zeilen` = (nr, hash, blob) mit genau 4·dim Bytes je Blob.
    `wis_vektor_dim` vor dem Schreiben, `wis_abschnitt_unbekannt` bei fremder nr (alles zurückgerollt)."""
    if type(dim) is not int or dim < 1:
        raise ValueError("wis_vektor_dim")
    zeilen = list(zeilen)
    for nr, hash_, blob in zeilen:
        if not isinstance(blob, (bytes, bytearray)) or len(blob) != 4 * dim:
            raise ValueError("wis_vektor_dim")
    try:
        with _immediate(db):
            db.executemany("INSERT OR REPLACE INTO vektoren (abschnitt, modell_id, dim, hash, blob) VALUES (?,?,?,?,?)",
                           [(nr, modell_id, dim, hash_, bytes(blob)) for nr, hash_, blob in zeilen])
    except sqlite3.IntegrityError:
        raise ValueError("wis_abschnitt_unbekannt") from None
    return len(zeilen)


def modellwechsel(db, modell_id, dim):
    """Gilt schon dieses Modell mit dieser Dimension: 0. Sonst alle Vektoren anderer Modell-ID oder Dimension löschen, Meta setzen;
    Rückgabe die Zahl der gelöschten Vektoren (WIS-04)."""
    meta = lies_meta(db)
    if meta.get("modell_id") == modell_id and meta.get("modell_dim") == str(dim):
        return 0
    with _immediate(db):
        geloescht = db.execute("DELETE FROM vektoren WHERE modell_id != ? OR dim != ?", (modell_id, dim)).rowcount
        db.executemany("INSERT OR REPLACE INTO meta (schluessel, wert) VALUES (?, ?)", [("modell_id", modell_id), ("modell_dim", str(dim))])
    return geloescht
