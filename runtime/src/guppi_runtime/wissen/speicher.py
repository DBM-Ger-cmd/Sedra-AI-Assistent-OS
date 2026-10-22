"""Die Fassade des Wissensspeichers (Spec 7, D7.3 bis D7.8, D7.10): eine SQLite-Datei `local_config/wissen/wissen.sqlite`,
Quellen freigeben und abgleichen, Vektoren über den CPU-Dienst (`embed.py`), die hybride Suche mit Rechtefilter vor dem Ranking,
der Volltext-Rückfall, Vorschläge der Agenten und die Nachmessung (D7.11). Nur hier entstehen Audit-Ereignisse (`component='wissen'`,
nie Text aus Quellen oder Fragen); die reinen Module (`schema`, `zerlegen`, `fusion`, `vektor`, `ausgabe`) kennen weder Audit
noch Desk. Fehler sind `ValueError('<code>')`; `SAETZE` übersetzt sie für Desk und Werkzeug.

Takt und Desk teilen die Verbindung: jede öffentliche Methode nimmt `self.lock`."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from ..core.content_policy import KEY_FORMATS, ScanFailure, scan_content
from . import adapter as adapter_mod
from . import ausgabe, embed, fusion, schema, vektor, zerlegen

TIME = "%Y-%m-%dT%H:%M:%SZ"
HART = ("PAN_CVV_V1",)                                                    # A-1: dieselben Klassen wie ContentGuard._finish
MAX_FRAGE = 500
NACHMESSUNG = "nachmessung.jsonl"
URTEILE = ("getroffen", "nicht_getroffen", "ohne_antwort")

SAETZE = {
    "wis_schema_neuer": "Die Wissensdatei ist neuer als dieser Code; sie wird nicht angefasst.",
    "wis_schema_kaputt": "Die Wissensdatei ist beschädigt (Integritätsprüfung); Ausweg ist ein Neuaufbau aus den Quellen.",
    "wis_vektor_dim": "Ein Vektor hat die falsche Länge.",
    "wis_vektor_leer": "Ein Vektor ist leer (Norm 0).",
    "wis_quelle_unbekannt": "Diese Quelle gibt es nicht.",
    "wis_quelle_nicht_freigegeben": "Diese Quelle ist nicht freigegeben.",
    "wis_quelle_neuer_antrag": "Das macht den Speicher weiter; dafür braucht es einen neuen Antrag.",
    "wis_pfad_absolut": "Der Pfad muss relativ zur Wurzel sein (kein Laufwerk, kein führender Schrägstrich).",
    "wis_pfad_ausserhalb": "Der Pfad führt aus der Wurzel hinaus.",
    "wis_dateiart_nicht_erlaubt": "Nur Markdown und Text (*.md, *.txt) sind erlaubt.",
    "wis_adapter_unbekannt": "Diesen Adapter kennt der Speicher nicht.",
    "wis_speicher_nicht_lesbar": "Die Quelle ist nicht lesbar (fehlt oder gesperrt); sie wurde übersprungen.",
    "wis_datei_zu_gross": "Die Datei ist größer als erlaubt; sie wurde übersprungen.",
    "wis_text_kein_utf8": "Die Datei ist kein UTF-8; sie wurde übersprungen.",
    "wis_zerlegen_grenzen": "Die Grenzen des Zerlegers sind ungültig.",
    "wis_engine_fehlt": "Die Engine für das Einbetten fehlt (local_config/wissen.yaml).",
    "wis_modell_fehlt": "Das Embedding-Modell fehlt (local_config/wissen.yaml).",
    "wis_modell_pruefsumme": "Die Prüfsumme des Embedding-Modells stimmt nicht.",
    "wis_server_start": "Der Embedding-Server startet nicht.",
    "wis_server_zeit": "Der Embedding-Server antwortet nicht rechtzeitig.",
    "wis_server_antwort": "Der Embedding-Server antwortet in falscher Form.",
    "wis_port_belegt": "Auf dem Port des Embedding-Servers antwortet ein fremder Prozess; nichts wird angefasst.",
    "wis_anfrage_leer": "Die Frage enthält kein Suchwort.",
    "wis_anfrage_zu_lang": "Die Frage ist länger als 500 Zeichen.",
    "wis_k_ungueltig": "Die Zahl der Treffer muss zwischen 1 und 20 liegen.",
    "wis_fusion_gewichte": "Die Fusionsgewichte sind ungültig.",
    "wis_leser_vom_server": "Wer liest, bestimmt der Server, nicht der Aufruf.",
    "wis_leser_ungueltig": "Der Leser ist ungültig.",
    "wis_stufe_ungueltig": "Die Stufe muss zwischen 0 und 6 liegen.",
    "wis_route_ungueltig": "Die Route ist weder local noch cloud.",
    "wis_liste_ungueltig": "Eine Trefferliste ist ungültig.",
    "wis_idf_ungueltig": "Eine Dokumentzahl ist ungültig.",
    "wis_route_cloud_personenbezug": "Ein Treffer mit Personenbezug darf nicht in die Cloud; er wurde verworfen.",
    "wis_takt_busy": "Ein anderer Prozess taktet den Wissensspeicher schon.",
    "wis_vorschlag_leer": "Titel oder Text des Vorschlags fehlt.",
    "wis_vorschlag_zu_lang": "Der Vorschlag ist zu lang (Titel 160, Text 4000 Zeichen).",
    "wis_vorschlag_gesperrt": "Der Vorschlag enthält einen harten Fund des Inhaltsschutzes.",
    "wis_beleg_fremd": "Ein Beleg stammt nicht aus dem Datenblock dieses Laufs.",
    "wis_vorschlaege_zu_viele": "Dieser Agent hat schon 20 offene Vorschläge.",
    "wis_vorschlag_unbekannt": "Diesen Vorschlag gibt es nicht.",
    "wis_nachmessung_urteil": "Das Urteil muss getroffen, nicht_getroffen oder ohne_antwort sein.",
    "binding_stale": "Seit dem Antrag hat sich etwas geändert; die Freigabe galt für den alten Stand, ausgeführt wurde nichts.",
    "wissen_aus": "Der Wissensspeicher ist ausgeschaltet (Schalter „wissen“).",
}


def satz(code):
    """Der deutsche Satz zu einem Fehlercode; unbekannte Codes bleiben, wie sie sind."""
    return SAETZE.get(str(code), str(code))


def leser(art, stufe, projekt, agent_id=None):
    """Ein Leser als dict (D7.7); gesetzt vom Server, nie aus Argumenten."""
    return {"art": art, "stufe": int(stufe), "projekt": projekt, "agent_id": agent_id}


CAPTAIN = leser("captain", 6, None)


def utc_now():
    return datetime.now(timezone.utc).strftime(TIME)


def _sha(text):
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def befunde_von(text):
    """(hart, weich): Regel-IDs des Inhaltsschutzes je Abschnitt; harte Funde sperren die Aufnahme (D7.3), ein Scannerfehler auch."""
    try:
        hits = scan_content(text)
    except ScanFailure as exc:
        return [str(exc)], []
    hart, weich = [], []
    for h in hits:
        r = h.rule_id.split(":", 1)[0]
        ziel = hart if (r in HART or r in KEY_FORMATS or r.startswith("INVISIBLE_BLOCK")) else weich
        if r not in ziel:
            ziel.append(r)
    return hart, weich


class WissenSpeicher:
    """Die eine Instanz je Runtime; `oeffnen` baut sie aus der Konfiguration und fängt Datenbankfehler als `ValueError`."""

    def __init__(self, konfig, *, projekt_root, repo_root, audit, uhr=None, gpu=None, starter=None, dienst=None):
        self.konfig = konfig
        self.projekt_root = Path(projekt_root).resolve()
        self.repo_root = Path(repo_root).resolve()
        self._audit = audit
        self.uhr = uhr or utc_now
        self.lock = threading.RLock()
        self.pfad = self.projekt_root / "local_config" / Path(*konfig.speicher.split("/"))
        self.pfad.parent.mkdir(parents=True, exist_ok=True)
        self.db = schema.oeffne_db(self.pfad, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode = WAL")
        vorher = schema.lies_meta(self.db).get("schema_version") if self._tabelle("meta") else None
        angewendet = schema.migriere(self.db, jetzt=self.uhr())
        if angewendet:
            self.audit("WIS_SCHEMA_MIGRIERT", {"von": int(vorher or 0), "nach": angewendet[-1]})
        schema.setze_meta(self.db, {"zerleger_version": zerlegen.ZERLEGER_VERSION, "fusion_version": fusion.FUSION_VERSION})
        self.dienst = dienst or embed.EmbeddingDienst(embed.einstellung_aus(konfig), gpu=gpu or embed.OhneGpuZugang(), audit=self.audit,
                                                      pid_datei=self.pfad.parent / "embed.pid", starter=starter,
                                                      merke_lesen=lambda: schema.lies_meta(self.db).get("gguf_pruefung"),
                                                      merke_schreiben=lambda w: schema.setze_meta(self.db, {"gguf_pruefung": w}))
        self.beantrage = None                                             # setzt desk_wissen: Vorschlag → Antrag (D7.8)
        self._vektoren = None
        self._vektoren_stempel = None
        self._rueckfall = None
        self._letzter_schritt = None

    @classmethod
    def oeffnen(cls, konfig, **kw):
        try:
            return cls(konfig, **kw)
        except sqlite3.Error as exc:
            raise ValueError("wis_speicher_nicht_lesbar:" + (str(exc) or type(exc).__name__)[:80]) from None

    def schliessen(self):
        with self.lock:
            try:
                self.dienst.stoppe()
            except Exception:
                pass
            self.db.close()

    def audit(self, event, payload):
        if self._audit is not None:
            self._audit(event, payload)

    def _tabelle(self, name):
        return self.db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone() is not None

    # ---- Quellen (D7.3, WIS-02)
    @staticmethod
    def quelle_id(wurzel, pfad, adapter):
        return "Q-" + _sha(f"{wurzel}|{pfad}|{adapter}")[:8]

    def _adapter(self, name):
        return adapter_mod.adapter_fuer(name, repo_root=self.repo_root, projekt_root=self.projekt_root, datei_max_bytes=self.konfig.datei_max_bytes,
                                        ziel=self.konfig.ziel, grenze=self.konfig.grenze)

    def pruefe_quelle(self, bindung):
        """Die Bindung eines Antrags prüfen und normieren: {wurzel, pfad, adapter, muster, stufe, projekt, personenbezug, art}."""
        b = dict(bindung or {})
        name = str(b.get("adapter") or "")
        ad = self._adapter(name)
        wurzel = str(b.get("wurzel") or "")
        if wurzel not in ("repo", "projekt"):
            raise ValueError("wis_pfad_ausserhalb")
        root = self.repo_root if wurzel == "repo" else self.projekt_root
        roh = str(b.get("pfad") or "")
        kern, _, teil = roh.partition("#")
        pfad = ad.pruefe_pfad(root, kern, b.get("muster") or "*.md") + ("#" + teil if teil else "")
        stufe = b.get("stufe")
        if type(stufe) is not int or not 0 <= stufe <= 6:
            raise ValueError("wis_stufe_ungueltig")
        art = str(b.get("art") or ("speicher" if name in ("knowledge", "arbeitsumfeld", "gateway") else "vorschlaege" if name == "vorschlag"
                                   else "ordner" if (root / Path(*kern.split("/"))).is_dir() else "datei"))
        projekt = b.get("projekt")
        return {"wurzel": wurzel, "pfad": pfad, "adapter": name, "muster": str(b.get("muster") or ("*.md" if name in ("markdown", "logbuch") else "*.txt" if name == "text" else "")),
                "stufe": stufe, "projekt": str(projekt) if projekt not in (None, "") else None, "personenbezug": 1 if b.get("personenbezug") else 0, "art": art}

    def quelle_freigeben(self, bindung, *, gate_id, mission_id):
        """Der Applier des Antrags `wissen_quelle_freigeben`: erst hier entsteht die Zeile in `quellen` (ohne Freigabe bleibt der
        Speicher für diesen Pfad leer); eine vorhandene Quelle übernimmt Stufe, Projekt und Kennzeichen des neuen Antrags."""
        q = self.pruefe_quelle(bindung)
        qid = self.quelle_id(q["wurzel"], q["pfad"], q["adapter"])
        with self.lock:
            jetzt = self.uhr()
            with schema._immediate(self.db):
                if self.db.execute("SELECT 1 FROM quellen WHERE id = ?", (qid,)).fetchone():
                    self.db.execute("UPDATE quellen SET stufe = ?, projekt = ?, personenbezug = ?, aktiv = 1, muster = ?, freigabe_gate = ?, freigabe_mission = ? WHERE id = ?",
                                    (q["stufe"], q["projekt"], q["personenbezug"], q["muster"], str(gate_id), str(mission_id), qid))
                else:
                    self.db.execute("INSERT INTO quellen (id, art, adapter, wurzel, pfad, muster, freigabe_gate, freigabe_mission, stufe, projekt, personenbezug, aktiv, erstellt) "
                                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,1,?)", (qid, q["art"], q["adapter"], q["wurzel"], q["pfad"], q["muster"], str(gate_id), str(mission_id),
                                                                        q["stufe"], q["projekt"], q["personenbezug"], jetzt))
            self.audit("WIS_QUELLE_AUFGENOMMEN", {"quelle": qid, "adapter": q["adapter"], "wurzel": q["wurzel"], "stufe": q["stufe"], "projekt": q["projekt"],
                                                 "personenbezug": q["personenbezug"], "gate": str(gate_id)})
        return dict(q, id=qid)

    def quelle_aendern(self, quelle_id, *, aktiv=None, stufe=None):
        """Ohne Gate nur enger: abschalten oder die Stufe heraufsetzen (D7.3); alles andere ist ein neuer Antrag."""
        with self.lock:
            q = self.quelle(quelle_id)
            if q is None:
                raise ValueError("wis_quelle_unbekannt")
            felder = {}
            if aktiv is not None:
                if aktiv and not q["aktiv"]:
                    raise ValueError("wis_quelle_neuer_antrag")
                felder["aktiv"] = 0 if not aktiv else 1
            if stufe is not None:
                if type(stufe) is not int or not 0 <= stufe <= 6:
                    raise ValueError("wis_stufe_ungueltig")
                if stufe < q["stufe"]:
                    raise ValueError("wis_quelle_neuer_antrag")
                felder["stufe"] = stufe
            if felder:
                with schema._immediate(self.db):
                    self.db.execute("UPDATE quellen SET " + ", ".join(f"{k} = ?" for k in felder) + " WHERE id = ?", (*felder.values(), quelle_id))
                self.audit("WIS_QUELLE_GEAENDERT", {"quelle": quelle_id, **felder})
            return self.quelle(quelle_id)

    def quelle(self, quelle_id):
        row = self.db.execute("SELECT q.*, (SELECT count(*) FROM abschnitte a WHERE a.quelle = q.id) AS abschnitte FROM quellen q WHERE q.id = ?", (quelle_id,)).fetchone()
        return dict(row) if row else None

    def quellen(self):
        return [dict(r) for r in self.db.execute("SELECT q.*, (SELECT count(*) FROM abschnitte a WHERE a.quelle = q.id) AS abschnitte FROM quellen q ORDER BY q.erstellt, q.id")]

    # ---- Aufnahme (D7.3, WIS-03)
    def abgleich(self, quelle_id=None):
        """Je aktive Quelle: Quell-Hash gleich → fertig; sonst Stücke → Abschnitte mit Hash und Befund, `vergleiche` → `wende_an`.
        Eine unlesbare Quelle wird übersprungen, nicht geleert."""
        t0 = time.monotonic()
        summe = {"quellen": 0, "neu": 0, "geaendert": 0, "entfernt": 0, "gesperrt": 0, "uebersprungen": 0, "dateien_uebersprungen": 0, "dauer_s": 0.0}
        with self.lock:
            quellen = [q for q in self.quellen() if q["aktiv"] and (quelle_id is None or q["id"] == quelle_id)]
            if quelle_id is not None and not quellen:
                raise ValueError("wis_quelle_unbekannt")
            for q in quellen:
                summe["quellen"] += 1
                try:
                    ad = self._adapter(q["adapter"])
                    qh = ad.quell_hash(q)
                except ValueError as exc:
                    self._ueberspringe(q, str(exc), summe)
                    continue
                if q["stand"] and qh == q["quell_hash"]:
                    summe["uebersprungen"] += 1
                    continue
                neue, gesperrt, gesehen, uebersprungen = [], 0, {}, set()

                def melde(datei, grund):                                  # eine unlesbare Datei behält ihre alten Abschnitte
                    uebersprungen.add(datei)
                    self.audit("WIS_DATEI_UEBERSPRUNGEN", {"quelle": q["id"], "datei": datei, "grund": grund})
                try:
                    for datei, datum, s in ad.stuecke(q, melde):
                        hart, weich = befunde_von(s["text"])
                        if hart:
                            gesperrt += 1
                            self.audit("WIS_ABSCHNITT_GESPERRT", {"quelle": q["id"], "datei": datei, "stelle_sha256": _sha(s["stelle"]), "regeln": hart})
                            continue
                        teil = s["teil"]
                        while (datei, s["stelle"], teil) in gesehen:
                            teil += 1
                        gesehen[(datei, s["stelle"], teil)] = True
                        neue.append({"datei": datei, "stelle": s["stelle"], "teil": teil, "text": s["text"], "hash": zerlegen.abschnitt_hash(s["stelle"], s["text"]),
                                     "datum": datum or "1970-01-01T00:00:00Z", "befunde": weich})
                except ValueError as exc:
                    self._ueberspringe(q, str(exc), summe)
                    continue
                jetzt = self.uhr()
                abgleich = schema.vergleiche(self.db, q["id"], neue)
                if uebersprungen:
                    bleibt = {r[0] for r in self.db.execute("SELECT nr FROM abschnitte WHERE quelle = ? AND datei IN (" + ",".join("?" * len(uebersprungen)) + ")", (q["id"], *uebersprungen))}
                    abgleich["entfernt"] = [nr for nr in abgleich["entfernt"] if nr not in bleibt]
                    summe["dateien_uebersprungen"] += len(uebersprungen)
                zahl = schema.wende_an(self.db, q["id"], abgleich, jetzt=jetzt)
                with schema._immediate(self.db):
                    self.db.execute("UPDATE quellen SET quell_hash = ? WHERE id = ?", (qh, q["id"]))
                    self.db.execute("INSERT INTO laeufe (art, start, ende, geraet, neu, geaendert, entfernt, status) VALUES ('abgleich', ?, ?, NULL, ?, ?, ?, 'fertig')",
                                    (jetzt, self.uhr(), zahl["neu"], zahl["geaendert"], zahl["entfernt"]))
                for k in ("neu", "geaendert", "entfernt"):
                    summe[k] += zahl[k]
                summe["gesperrt"] += gesperrt
                self.audit("WIS_ABGLEICH", {"quelle": q["id"], **zahl, "gesperrt": gesperrt, "dauer_s": round(time.monotonic() - t0, 3)})
            self._vektoren_stempel = None
        summe["dauer_s"] = round(time.monotonic() - t0, 3)
        return summe

    def _ueberspringe(self, q, grund, summe):
        summe["uebersprungen"] += 1
        self.audit("WIS_DATEI_UEBERSPRUNGEN", {"quelle": q["id"], "datei": q["pfad"], "grund": grund})

    # ---- Einbetten (D7.4, WIS-04, WIS-12)
    def _modell_pruefen(self):
        """Weicht die Modell-ID der Einstellung von `meta` ab: Vektoren des alten Modells weg, Lauf `neuaufbau` (WIS-04)."""
        mid, meta = self.dienst.modell_id(), schema.lies_meta(self.db)
        if meta.get("modell_id") == mid and meta.get("modell_dim") == str(self.konfig.dim):
            return 0
        alt = meta.get("modell_id")
        geloescht = schema.modellwechsel(self.db, mid, self.konfig.dim)
        with schema._immediate(self.db):
            self.db.execute("INSERT INTO laeufe (art, start, geraet, status) VALUES ('neuaufbau', ?, 'cpu', 'laeuft')", (self.uhr(),))
        if alt is not None:
            self.audit("WIS_MODELL_WECHSEL", {"alt": alt, "neu": mid, "geloescht": geloescht})
        self._vektoren_stempel = None
        return geloescht

    def einbetten_schritt(self):
        """Ein Schritt des Dienstes (`EmbeddingDienst.lauf`) über die offenen Vektoren; Pause und Ende stehen in `laeufe`."""
        with self.lock:
            ok, grund = self.dienst.bereit()
            if not ok:
                self._letzter_schritt = {"geraet": "cpu", "eingebettet": 0, "dauer_s": 0.0, "ende": "fehler", "grund": grund}
                return self._letzter_schritt
            self._modell_pruefen()
            mid = self.dienst.modell_id()
            start = self.uhr()
            out = self.dienst.lauf(lambda n: schema.offene_vektoren(self.db, mid, n), lambda zeilen: schema.schreibe_vektoren(self.db, mid, self.konfig.dim, zeilen))
            with schema._immediate(self.db):
                status = "pausiert" if out["ende"] == "pause" else "abgebrochen" if out["ende"] == "fehler" else "fertig"
                self.db.execute("INSERT INTO laeufe (art, start, ende, geraet, lease, eingebettet, pause_grund, status) VALUES ('einbetten', ?, ?, 'cpu', 0, ?, ?, ?)",
                                (start, self.uhr(), out["eingebettet"], out.get("grund") or None, status))
                if out["ende"] == "fertig" and not schema.offene_vektoren(self.db, mid, 1):
                    self.db.execute("UPDATE laeufe SET status = 'fertig', ende = ? WHERE art = 'neuaufbau' AND status = 'laeuft'", (self.uhr(),))
            self._vektoren_stempel = None
            self._letzter_schritt = out
            return out

    def nachfuehren(self):
        """Abgleich und ein Einbett-Schritt (Typ-Verb `wissen.nachfuehren` und Takt, G2-S7-j)."""
        with self.lock:
            a = self.abgleich()
            e = self.einbetten_schritt()
            self.dienst.leerlauf_pruefen()
            return {"abgleich": a, "einbetten": e}

    # ---- Suche (D7.5, D7.7; WIS-05, -06, -09, -11)
    def _abdeckung(self, mid):
        n = self.db.execute("SELECT count(*) FROM abschnitte").fetchone()[0]
        if not n:
            return 1.0, 0, 0
        v = self.db.execute("SELECT count(*) FROM vektoren v JOIN abschnitte a ON a.nr = v.abschnitt WHERE v.modell_id = ? AND v.hash = a.hash", (mid,)).fetchone()[0]
        return v / n, n, v

    def _vektoren_laden(self, mid):
        stempel = self.db.execute("SELECT count(*), max(abschnitt) FROM vektoren WHERE modell_id = ?", (mid,)).fetchone()
        key = (mid, tuple(stempel))
        if self._vektoren_stempel != key:
            dim = self.konfig.dim
            self._vektoren = [(r["abschnitt"], vektor.lese(r["blob"], dim)) for r in
                              self.db.execute("SELECT v.abschnitt, v.blob FROM vektoren v JOIN abschnitte a ON a.nr = v.abschnitt WHERE v.modell_id = ? AND v.dim = ? AND v.hash = a.hash", (mid, dim))]
            self._vektoren_stempel = key
        return self._vektoren

    def _rueckfall_melden(self, grund):
        if grund != self._rueckfall:
            self._rueckfall = grund
            if grund is not None:
                self.audit("WIS_RUECKFALL_VOLLTEXT", {"grund": grund})

    def suche(self, frage, *, leser, k=5, route="local", mission_id=None, protokoll=True):
        """Rechtefilter → Wortliste (FTS5, BM25) und Vektorliste (Skalarprodukt im Arbeitsspeicher) → Güte → gewichtete Fusion.
        Ohne bereiten Dienst, Anfrage-Vektor oder genug Abdeckung: Modus `volltext` mit Hinweis (WIS-06)."""
        t0 = time.monotonic()
        if not isinstance(frage, str):
            raise ValueError("wis_anfrage_leer")
        frage = frage.strip()
        if len(frage) > MAX_FRAGE:
            raise ValueError("wis_anfrage_zu_lang")
        if type(k) is not int or not 1 <= k <= 20:
            raise ValueError("wis_k_ungueltig")
        where, params = fusion.sql_filter(leser, route)
        woerter = fusion.woerter(frage)
        if not woerter:
            raise ValueError("wis_anfrage_leer")
        agent = leser["art"] == "agent"
        befund_sql = " AND a.befunde = '[]'" if agent else ""
        with self.lock:
            tiefe = self.konfig.tiefe
            wort = [r[0] for r in self.db.execute(
                "SELECT a.nr FROM abschnitte_fts f JOIN abschnitte a ON a.nr = f.rowid JOIN quellen q ON q.id = a.quelle WHERE abschnitte_fts MATCH ? AND " + where + befund_sql
                + " ORDER BY bm25(abschnitte_fts, 2.0, 1.0), a.nr LIMIT ?", (fusion.fts_anfrage(woerter), *params, tiefe))]
            mid, grund, anfrage = self.dienst.modell_id(), None, None
            meta = schema.lies_meta(self.db)
            bereit, bereit_grund = self.dienst.bereit()
            abdeckung, n_alle, _ = self._abdeckung(mid)
            if not bereit:
                grund = bereit_grund
            elif meta.get("modell_id") != mid:
                grund = "modell_wechsel"
            elif abdeckung < self.konfig.abdeckung_min:
                grund = "abdeckung"
            else:
                anfrage = self.dienst.anfrage_vektor(frage)
                if anfrage is None:
                    grund = "anfrage_vektor"
            self._rueckfall_melden(grund)
            if grund is None:
                erlaubt = {r[0] for r in self.db.execute("SELECT a.nr FROM abschnitte a JOIN quellen q ON q.id = a.quelle WHERE " + where + befund_sql, params)}
                vek = [nr for nr, _ in vektor.top_k(anfrage, self._vektoren_laden(mid), tiefe, erlaubt=lambda nr: nr in erlaubt)]
                g = self._guete(woerter, wort, n_alle)
                treffer = fusion.fusioniere(wort, vek, g, self.konfig.gewichte, k_aus=k)
                modus = "hybrid"
            else:
                treffer = fusion.nur_volltext(wort, k_aus=k)
                modus = "volltext"
            rows = {r["nr"]: dict(r) for r in self.db.execute(
                "SELECT a.*, q.personenbezug AS q_personenbezug FROM abschnitte a JOIN quellen q ON q.id = a.quelle WHERE a.nr IN (" + ",".join("?" * len(treffer)) + ")",
                [t["nr"] for t in treffer])} if treffer else {}
        out = []
        for t in treffer:
            r = rows.get(t["nr"])
            if r is None:
                continue
            out.append({"id": r["id"], "quelle": r["quelle"], "datei": r["datei"], "stelle": r["stelle"], "datum": r["datum"], "text": r["text"], "hash": r["hash"],
                        "punkte": t["punkte"], "rang_wort": t["rang_wort"], "rang_vektor": t["rang_vektor"], "guete": t["guete"],
                        "personenbezug": bool(r["q_personenbezug"]), "befunde": tuple(json.loads(r["befunde"] or "[]"))})
        hinweis = ausgabe.HINWEIS_VOLLTEXT.format(grund=grund) if modus == "volltext" else (
            ausgabe.HINWEIS_ABDECKUNG.format(n=n_alle - round(abdeckung * n_alle)) if abdeckung < 1.0 else None)
        ms = int((time.monotonic() - t0) * 1000)
        ids = [o["id"] for o in out]
        self.audit("WIS_SUCHE", {"leser_art": leser["art"], "agent_id": leser.get("agent_id"), "stufe": leser["stufe"], "projekt": leser.get("projekt"), "route": route,
                                 "modus": modus, "k": k, "ids": ids, "frage_sha256": _sha(frage), "ms": ms, "mission_id": mission_id})
        if protokoll and leser["art"] == "captain":
            self._protokolliere(frage, ids, modus)
        return {"modus": modus, "hinweis": hinweis, "treffer": out, "modell_id": mid if modus == "hybrid" else None, "abdeckung": round(abdeckung, 4), "ms": ms, "woerter": woerter}

    def _guete(self, woerter, wort, n_alle):
        """g(d) je Abschnitt der Wortliste: welche Wörter ein Abschnitt enthält, entscheidet FTS5 selbst (D7.5)."""
        if not wort:
            return {}
        idf_je_wort, drin = {}, {nr: set() for nr in wort}
        marks = ",".join("?" * len(wort))
        for w in woerter:
            q = fusion.fts_anfrage([w])
            n_w = self.db.execute("SELECT count(*) FROM abschnitte_fts WHERE abschnitte_fts MATCH ?", (q,)).fetchone()[0]
            idf_je_wort[w] = fusion.idf(n_alle, min(n_w, n_alle))
            for (nr,) in self.db.execute("SELECT rowid FROM abschnitte_fts WHERE abschnitte_fts MATCH ? AND rowid IN (" + marks + ")", (q, *wort)):
                drin[nr].add(w)
        return {nr: fusion.guete(idf_je_wort, enthalten) for nr, enthalten in drin.items()}

    # ---- Stand (Werkzeug, Ereignisstrom)
    def stand(self):
        with self.lock:
            mid = self.dienst.modell_id()
            meta = schema.lies_meta(self.db)
            bereit, grund = self.dienst.bereit()
            abdeckung, n, v = self._abdeckung(mid)
            lauf = self.db.execute("SELECT * FROM laeufe WHERE art IN ('einbetten', 'neuaufbau') ORDER BY id DESC LIMIT 1").fetchone()
            neuaufbau = self.db.execute("SELECT 1 FROM laeufe WHERE art = 'neuaufbau' AND status = 'laeuft'").fetchone() is not None
            offen = self.db.execute("SELECT count(*) FROM vorschlaege WHERE status = 'offen'").fetchone()[0]
            modus = "hybrid" if bereit and meta.get("modell_id") == mid and abdeckung >= self.konfig.abdeckung_min else "volltext"
            return {"modell_id": mid, "modell_in_datei": meta.get("modell_id"), "bereit": bereit, "grund": grund or None, "abschnitte": n, "vektoren": v,
                    "abdeckung": round(abdeckung, 4), "modus": modus, "neuaufbau": neuaufbau or meta.get("modell_id") != mid, "server_laeuft": self.dienst.laeuft(),
                    "letzter_lauf": dict(lauf) if lauf else None, "pause_grund": (dict(lauf).get("pause_grund") if lauf and lauf["status"] == "pausiert" else None),
                    "quellen": len(self.quellen()), "vorschlaege_offen": offen, "zerleger": meta.get("zerleger_version"), "fusion": meta.get("fusion_version"),
                    "geraet": "cpu", "lage": self.dienst.gpu.lage().zustand}

    # ---- Vorschläge (D7.8, WIS-10)
    def vorschlagen(self, *, titel, text, belege, agent_id, lauf_id, aufgabe_id, block_ids, leser):
        """Ein Vorschlag eines Agenten: Form, harter Fund, Belege nur aus dem Block, höchstens 20 offene je Agent; Personenbezug erbt
        er von seinen Belegen. Mit `beantrage` (Desk) entsteht sofort der Antrag."""
        titel, text = str(titel or "").strip(), str(text or "").strip()
        if not titel or not text:
            raise ValueError("wis_vorschlag_leer")
        if len(titel) > self.konfig.titel_max or len(text) > self.konfig.text_max:
            raise ValueError("wis_vorschlag_zu_lang")
        hart, _ = befunde_von(titel + "\n" + text)
        if hart:
            raise ValueError("wis_vorschlag_gesperrt")
        belege = [str(b) for b in (belege or [])]
        if any(b not in block_ids for b in belege):
            raise ValueError("wis_beleg_fremd")
        with self.lock:
            offen = self.db.execute("SELECT count(*) FROM vorschlaege WHERE agent_id = ? AND status = 'offen'", (agent_id,)).fetchone()[0]
            if offen >= self.konfig.offene_je_agent:
                raise ValueError("wis_vorschlaege_zu_viele")
            personenbezug = 0
            if belege:
                marks = ",".join("?" * len(belege))
                personenbezug = int(bool(self.db.execute("SELECT 1 FROM abschnitte a JOIN quellen q ON q.id = a.quelle WHERE a.id IN (" + marks + ") AND q.personenbezug = 1", belege).fetchone()))
            jetzt = self.uhr()
            h = _sha(titel + "\n" + text)
            vid = "WV-" + _sha(f"{agent_id}|{lauf_id}|{h}|{jetzt}|{offen}")[:8]
            with schema._immediate(self.db):
                self.db.execute("INSERT INTO vorschlaege (id, titel, text, hash, agent_id, lauf_id, aufgabe_id, belege, vorschlag_stufe, vorschlag_projekt, personenbezug, status, erstellt) "
                                "VALUES (?,?,?,?,?,?,?,?,?,?,?,'offen',?)", (vid, titel, text, h, agent_id, lauf_id, aufgabe_id, json.dumps(belege), leser["stufe"], leser.get("projekt"), personenbezug, jetzt))
            self.audit("WIS_VORSCHLAG_NEU", {"id": vid, "agent_id": agent_id, "lauf_id": lauf_id, "belege": belege, "personenbezug": personenbezug})
            out = {"id": vid, "hash": h, "stufe": leser["stufe"], "projekt": leser.get("projekt"), "personenbezug": personenbezug, "titel": titel, "mission_id": None}
            if self.beantrage is not None:
                try:
                    out["mission_id"] = self.beantrage(out)
                    with schema._immediate(self.db):
                        self.db.execute("UPDATE vorschlaege SET mission_id = ? WHERE id = ?", (out["mission_id"], vid))
                except Exception as exc:
                    self.audit("WIS_VORSCHLAG_VERWORFEN", {"id": vid, "grund": "antrag:" + (str(exc) or type(exc).__name__)[:80]})
            return out

    def vorschlag(self, vid):
        row = self.db.execute("SELECT * FROM vorschlaege WHERE id = ?", (vid,)).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["belege"] = json.loads(d.get("belege") or "[]")
        return d

    def vorschlaege(self, status="offen"):
        sql = "SELECT * FROM vorschlaege" + (" WHERE status = ?" if status else "") + " ORDER BY erstellt DESC, id"
        out = []
        for r in self.db.execute(sql, (status,) if status else ()):
            d = dict(r)
            d["belege"] = json.loads(d.get("belege") or "[]")
            out.append(d)
        return out

    def _vorschlag_quelle(self, stufe, projekt, personenbezug, gate_id, mission_id):
        """Die Quelle `Q-VS-<stufe>-<projekt>-<p>` (Art `vorschlaege`, Adapter `vorschlag`), beim ersten Mal angelegt."""
        qid = f"Q-VS-{stufe}-{projekt or 'alle'}-{personenbezug}"
        if not self.db.execute("SELECT 1 FROM quellen WHERE id = ?", (qid,)).fetchone():
            with schema._immediate(self.db):
                self.db.execute("INSERT INTO quellen (id, art, adapter, wurzel, pfad, muster, freigabe_gate, freigabe_mission, stufe, projekt, personenbezug, aktiv, erstellt) "
                                "VALUES (?, 'vorschlaege', 'vorschlag', 'projekt', ?, '', ?, ?, ?, ?, ?, 1, ?)",
                                (qid, adapter_mod.VORSCHLAEGE + "#" + qid, str(gate_id), str(mission_id), stufe, projekt, personenbezug, self.uhr()))
        return qid

    def vorschlag_aufnehmen(self, bindung, *, gate_id, mission_id):
        """Der Applier des Antrags `wissen_vorschlag_aufnehmen`: noch offen und Hash gleich (sonst `binding_stale`), Zeile an
        `vorschlaege.jsonl`, Quelle der Partition, Abgleich; Status `freigegeben` (WIS-10)."""
        with self.lock:
            v = self.vorschlag(str(bindung.get("vorschlag_id") or ""))
            if v is None:
                raise ValueError("wis_vorschlag_unbekannt")
            if v["status"] != "offen" or v["hash"] != bindung.get("hash"):
                raise ValueError("binding_stale")
            stufe, projekt, p = int(bindung.get("stufe", v["vorschlag_stufe"])), bindung.get("projekt", v["vorschlag_projekt"]), int(bool(bindung.get("personenbezug", v["personenbezug"])))
            jetzt = self.uhr()
            datei = self.projekt_root / Path(*adapter_mod.VORSCHLAEGE.split("/"))
            datei.parent.mkdir(parents=True, exist_ok=True)
            zeile = {"id": v["id"], "titel": v["titel"], "text": v["text"], "hash": v["hash"], "stufe": stufe, "projekt": projekt, "personenbezug": p,
                     "agent_id": v["agent_id"], "lauf_id": v["lauf_id"], "aufgabe_id": v["aufgabe_id"], "belege": v["belege"], "freigegeben": jetzt, "gate": str(gate_id)}
            with datei.open("a", encoding="utf-8") as f:
                f.write(json.dumps(zeile, ensure_ascii=False) + "\n")
            qid = self._vorschlag_quelle(stufe, projekt, p, gate_id, mission_id)
            with schema._immediate(self.db):
                self.db.execute("UPDATE vorschlaege SET status = 'freigegeben', entschieden = ?, vorschlag_stufe = ?, vorschlag_projekt = ?, personenbezug = ? WHERE id = ?",
                                (jetzt, stufe, projekt, p, v["id"]))
            self.abgleich(qid)
            self.audit("WIS_VORSCHLAG_AUFGENOMMEN", {"id": v["id"], "quelle": qid, "stufe": stufe, "projekt": projekt, "personenbezug": p})
            return {"id": v["id"], "quelle": qid}

    def vorschlag_ablehnen(self, vid):
        with self.lock:
            v = self.vorschlag(vid)
            if v is None:
                raise ValueError("wis_vorschlag_unbekannt")
            if v["status"] == "offen":
                with schema._immediate(self.db):
                    self.db.execute("UPDATE vorschlaege SET status = 'abgelehnt', entschieden = ? WHERE id = ?", (self.uhr(), vid))
                self.audit("WIS_VORSCHLAG_ABGELEHNT", {"id": vid})
            return {"id": vid, "status": "abgelehnt" if v["status"] in ("offen", "abgelehnt") else v["status"]}

    def vorschlag_zuruecknehmen(self, vid):
        """Rücknahme eines aufgenommenen Vorschlags (enger, ohne Gate): Abschnitte weg, Zeile aus `vorschlaege.jsonl`, Status `veraltet`."""
        with self.lock:
            v = self.vorschlag(vid)
            if v is None:
                raise ValueError("wis_vorschlag_unbekannt")
            datei = self.projekt_root / Path(*adapter_mod.VORSCHLAEGE.split("/"))
            if datei.is_file():
                zeilen = [z for z in datei.read_text(encoding="utf-8").splitlines() if z.strip() and json.loads(z).get("id") != vid]
                datei.write_text("".join(z + "\n" for z in zeilen), encoding="utf-8")
            with schema._immediate(self.db):
                self.db.execute("DELETE FROM abschnitte WHERE datei = ?", ("vorschlag:" + vid,))
                self.db.execute("UPDATE vorschlaege SET status = 'veraltet', entschieden = ? WHERE id = ?", (self.uhr(), vid))
            self._vektoren_stempel = None
            self.audit("WIS_VORSCHLAG_ZURUECKGENOMMEN", {"id": vid})
            return {"id": vid, "status": "veraltet"}

    # ---- Nachmessung (D7.11): je Suche des Captains ein Protokollsatz ohne Fragetext
    def _nachmessung_datei(self):
        return self.pfad.parent / NACHMESSUNG

    def _protokolliere(self, frage, ids, modus):
        try:
            with self._nachmessung_datei().open("a", encoding="utf-8") as f:
                f.write(json.dumps({"zeit": self.uhr(), "frage_sha256": _sha(frage), "ids": ids, "modus": modus}) + "\n")
        except OSError:
            pass

    def nachmessung(self):
        p = self._nachmessung_datei()
        if not p.is_file():
            return []
        out = []
        for z in p.read_text(encoding="utf-8").splitlines():
            if z.strip():
                try:
                    out.append(json.loads(z))
                except ValueError:
                    continue
        return out

    def nachmessung_bewerten(self, frage_sha256, urteil):
        if urteil not in URTEILE:
            raise ValueError("wis_nachmessung_urteil")
        saetze = self.nachmessung()
        for s in saetze:
            if s.get("frage_sha256") == frage_sha256:
                s["urteil"] = urteil
        self._nachmessung_datei().write_text("".join(json.dumps(s) + "\n" for s in saetze), encoding="utf-8")
        return {"frage_sha256": frage_sha256, "urteil": urteil}

    def nachmessung_abschliessen(self):
        """Die bewerteten Fragen zählen, Ergebnis als Datei neben dem Speicher, Audit `WIS_NACHMESSUNG`; das Protokoll beginnt neu."""
        saetze = self.nachmessung()
        bewertet = [s for s in saetze if s.get("urteil") in URTEILE]
        getroffen = sum(1 for s in bewertet if s["urteil"] == "getroffen")
        beantwortbar = [s for s in bewertet if s["urteil"] != "ohne_antwort"]
        anteil = round(getroffen / len(beantwortbar), 4) if beantwortbar else None
        zeiten = [s.get("zeit") for s in saetze if s.get("zeit")]
        ergebnis = {"fragen": len(bewertet), "getroffen": getroffen, "anteil": anteil, "zeitraum": [min(zeiten), max(zeiten)] if zeiten else None, "saetze": bewertet}
        datum = self.uhr()[:10]
        ziel = self.pfad.parent / f"nachmessung_{datum}.json"
        ziel.write_text(json.dumps(ergebnis, ensure_ascii=False, indent=1), encoding="utf-8")
        p = self._nachmessung_datei()
        if p.is_file():
            p.unlink()
        self.audit("WIS_NACHMESSUNG", {"fragen": len(bewertet), "getroffen": getroffen, "anteil": anteil, "zeitraum": ergebnis["zeitraum"]})
        return dict(ergebnis, datei=ziel.name)
