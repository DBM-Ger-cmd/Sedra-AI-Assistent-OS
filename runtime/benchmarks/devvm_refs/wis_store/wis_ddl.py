"""Saat für wis_store (Spec 7, D7.2): die Tabellen des Wissensspeichers als versionierte Migrationen und das Öffnen der Datei.
Nur Standardbibliothek. Wird vom Bau als Arbeitsstand geladen (PIPE-10, Feld SEED in benchmarks/devvm_specs/wis_store.py) und nicht geändert."""
import sqlite3

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


def open_db(path):
    """Verbindung mit den Einstellungen des Speichers: Zeilen als sqlite3.Row, keine stille Transaktion, Fremdschlüssel an."""
    db = sqlite3.connect(str(path), isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA busy_timeout = 30000")
    return db
