import hashlib
import json
import sqlite3
from contextlib import contextmanager

from wis_ddl import MIGRATIONEN

SCHEMA_VERSION = len(MIGRATIONEN)
FELDER = ("datei", "stelle", "teil", "text", "hash", "datum")


@contextmanager
def _immediate(db):
    db.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        db.execute("ROLLBACK")
        raise
    db.execute("COMMIT")


def _has_table(db, name):
    return db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone() is not None


def migriere(db, *, jetzt):
    if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        raise ValueError("wis_schema_kaputt")
    stand = db.execute("SELECT COALESCE(MAX(version), 0) FROM migrationen").fetchone()[0] if _has_table(db, "migrationen") else 0
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
    return {r["schluessel"]: r["wert"] for r in db.execute("SELECT schluessel, wert FROM meta ORDER BY schluessel")}


def setze_meta(db, werte):
    with _immediate(db):
        db.executemany("INSERT OR REPLACE INTO meta (schluessel, wert) VALUES (?, ?)", [(str(k), str(v)) for k, v in dict(werte).items()])


def abschnitt_id(quelle_id, datei, stelle, teil, belegt):
    voll = hashlib.sha256(f"{quelle_id}|{datei}|{stelle}|{teil}".encode("utf-8")).hexdigest()
    for n in range(10, 65, 2):
        kandidat = "W" + voll[:n]
        if not belegt(kandidat):
            return kandidat
    raise ValueError("wis_id_kollision")


def _pruefe(abschnitt):
    if not isinstance(abschnitt, dict) or any(k not in abschnitt for k in FELDER):
        raise ValueError("wis_abschnitt_ungueltig")
    if type(abschnitt["teil"]) is not int or abschnitt["teil"] < 1 or not all(isinstance(abschnitt[k], str) and abschnitt[k] for k in FELDER if k != "teil"):
        raise ValueError("wis_abschnitt_ungueltig")
    return (abschnitt["datei"], abschnitt["stelle"], abschnitt["teil"])


def vergleiche(db, quelle_id, abschnitte):
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
    if db.execute("SELECT 1 FROM quellen WHERE id = ?", (quelle_id,)).fetchone() is None:
        raise ValueError("wis_quelle_unbekannt")
    for a in list(abgleich["neu"]) + [a for _, a in abgleich["geaendert"]]:
        _pruefe(a)
    with _immediate(db):
        for nr in abgleich["entfernt"]:
            db.execute("DELETE FROM abschnitte WHERE nr = ? AND quelle = ?", (nr, quelle_id))
        for nr, a in abgleich["geaendert"]:
            db.execute("UPDATE abschnitte SET text = ?, hash = ?, datum = ?, aufgenommen = ?, befunde = ?, zeichen = ? WHERE nr = ? AND quelle = ?",
                       (a["text"], a["hash"], a["datum"], jetzt, _befunde(a), len(a["text"]), nr, quelle_id))
        for a in abgleich["neu"]:
            belegt = lambda i: db.execute("SELECT 1 FROM abschnitte WHERE id = ?", (i,)).fetchone() is not None
            db.execute("INSERT INTO abschnitte (id, quelle, datei, stelle, teil, text, hash, datum, aufgenommen, befunde, zeichen) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                       (abschnitt_id(quelle_id, a["datei"], a["stelle"], a["teil"], belegt), quelle_id, a["datei"], a["stelle"], a["teil"],
                        a["text"], a["hash"], a["datum"], jetzt, _befunde(a), len(a["text"])))
        db.execute("UPDATE quellen SET stand = ? WHERE id = ?", (jetzt, quelle_id))
    return {"neu": len(abgleich["neu"]), "geaendert": len(abgleich["geaendert"]), "entfernt": len(abgleich["entfernt"])}


def offene_vektoren(db, modell_id, limit):
    if type(limit) is not int or limit < 1:
        raise ValueError("wis_limit_ungueltig")
    rows = db.execute("SELECT a.nr, a.stelle, a.text, a.hash FROM abschnitte a LEFT JOIN vektoren v ON v.abschnitt = a.nr AND v.modell_id = ? AND v.hash = a.hash "
                      "WHERE v.abschnitt IS NULL ORDER BY a.nr LIMIT ?", (modell_id, limit))
    return [(r["nr"], r["stelle"] + "\n" + r["text"], r["hash"]) for r in rows]


def schreibe_vektoren(db, modell_id, dim, zeilen):
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
    meta = lies_meta(db)
    if meta.get("modell_id") == modell_id and meta.get("modell_dim") == str(dim):
        return 0
    with _immediate(db):
        geloescht = db.execute("DELETE FROM vektoren WHERE modell_id != ? OR dim != ?", (modell_id, dim)).rowcount
        db.executemany("INSERT OR REPLACE INTO meta (schluessel, wert) VALUES (?, ?)", [("modell_id", modell_id), ("modell_dim", str(dim))])
    return geloescht
