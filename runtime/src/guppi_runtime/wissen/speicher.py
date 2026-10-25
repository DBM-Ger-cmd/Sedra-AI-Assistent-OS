"""Die Fassade des Wissensspeichers (Spec 7, D7.3 bis D7.8, D7.10): eine SQLite-Datei `local_config/wissen/wissen.sqlite`,
Quellen freigeben und abgleichen, Vektoren über den CPU-Dienst (`embed.py`), die hybride Suche mit Rechtefilter vor dem Ranking,
der Volltext-Rückfall, Vorschläge der Agenten und die Nachmessung (D7.11). Nur hier und in den Teilen der Klasse (`einbetten`, `suche`,
`vorschlaege`, `nachmessung`) entstehen Audit-Ereignisse (`component='wissen'`, nie Text aus Quellen oder Fragen); die reinen Module
(`schema`, `zerlegen`, `fusion`, `vektor`, `ausgabe`) kennen weder Audit noch Desk. Fehler sind `ValueError('<code>')`; `SAETZE`
übersetzt sie für Desk und Werkzeug.

Takt und Desk teilen die Verbindung: jeder Zugriff auf `self.db` läuft unter `self.lock`. Die Sperre wird nie über einen Aufruf
des Embedding-Servers gehalten (Start bis 90 s, Stapel, Anfrage-Vektor): sonst warteten Suchen auf den Einbett-Schritt (Auflage 4, Prüfung F3)."""
from __future__ import annotations

import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from . import adapter as adapter_mod
from . import embed, fusion, schema, zerlegen
from .einbetten import EinbettTeil
from .hilfen import HART, _sha, befunde_von  # noqa: F401  (HART: bisheriger Ort)
from .nachmessung import NACHMESSUNG, URTEILE, NachmessungTeil  # noqa: F401
from .suche import MAX_FRAGE, SucheTeil  # noqa: F401
from .vorschlaege import VorschlagTeil

TIME = "%Y-%m-%dT%H:%M:%SZ"

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
    "wis_antrag_unbekannt": "Zu dieser Freigabe gibt es keinen offenen Antrag mit Gate; angelegt wurde nichts.",
    "wis_testlab_nicht_lesbar": "Das Testlabor ist nicht lesbar; der Wissensspeicher bleibt aus.",
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


class WissenSpeicher(EinbettTeil, SucheTeil, VorschlagTeil, NachmessungTeil):
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
        meta = schema.lies_meta(self.db)
        if meta.get("zerleger_version") not in (None, zerlegen.ZERLEGER_VERSION):      # neue Zerleger-Version: alles neu zerlegen (D7.3)
            with schema._immediate(self.db):
                self.db.execute("UPDATE quellen SET quell_hash = NULL")
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
        self._einbett_lock = threading.Lock()                         # ein Einbett-Schritt zur Zeit (Takt und Verb)
        self._vektor_fehler = set()                                   # (nr, hash), die der Server allein ablehnt (Prüfung F2)
        self._start_thread = None

    @classmethod
    def oeffnen(cls, konfig, **kw):
        try:
            return cls(konfig, **kw)
        except (sqlite3.Error, OSError) as exc:                      # auch Ordner nicht anlegbar, Rechte, Laufwerk weg (G4-Auflage 3)
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
        with self.lock:
            return self._quelle(quelle_id)

    def _quelle(self, quelle_id):
        row = self.db.execute("SELECT q.*, (SELECT count(*) FROM abschnitte a WHERE a.quelle = q.id) AS abschnitte FROM quellen q WHERE q.id = ?", (quelle_id,)).fetchone()
        return dict(row) if row else None

    def quellen(self):
        with self.lock:
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
            alle_aktiv = [q for q in self.quellen() if q["aktiv"]]
            for q in quellen:
                summe["quellen"] += 1
                ausschluss = self._ausschluss(q, alle_aktiv)
                try:
                    ad = self._adapter(q["adapter"])
                    qh = ad.quell_hash(q)
                except ValueError as exc:
                    self._ueberspringe(q, str(exc), summe)
                    continue
                if ausschluss:                                    # ändert sich der Ausschluss, wird neu zerlegt
                    qh += ":aus:" + _sha("|".join(sorted(ausschluss)))[:12]
                if q["stand"] and qh == q["quell_hash"]:
                    summe["uebersprungen"] += 1
                    continue
                neue, gesperrt, gesehen, uebersprungen = [], 0, {}, set()

                def melde(datei, grund):                                  # eine unlesbare Datei behält ihre alten Abschnitte
                    uebersprungen.add(datei)
                    self.audit("WIS_DATEI_UEBERSPRUNGEN", {"quelle": q["id"], "datei": datei, "grund": grund})
                try:
                    for datei, datum, s in ad.stuecke(q, melde):
                        if datei in ausschluss:
                            continue
                        hart, weich = befunde_von(s["text"])
                        if hart:
                            gesperrt += 1
                            self.audit("WIS_ABSCHNITT_GESPERRT", {"quelle": q["id"], "datei": datei, "stelle_sha256": _sha(s["stelle"]), "regeln": hart})
                            continue
                        teil = s["teil"]
                        while (datei, s["stelle"], teil) in gesehen:
                            teil += 1
                        gesehen[(datei, s["stelle"], teil)] = True
                        neue.append({"datei": datei, "stelle": s["stelle"], "teil": teil, "text": s["text"], "hash": zerlegen.abschnitt_hash(s["stelle"], s["text"], zerlegen.ZERLEGER_VERSION),
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

    @staticmethod
    def _ausschluss(q, alle_aktiv):
        """Dateien, die eine andere aktive Datei-Quelle derselben Wurzel schon abdeckt (z. B. das Logbuch im Ordner `docs`):
        eine Ordner-Quelle nimmt sie nicht noch einmal auf, sonst stünde derselbe Text zweimal im Index (Prüfung F4)."""
        if q["art"] != "ordner" or q["adapter"] not in ("markdown", "text"):
            return set()
        return {a["pfad"] for a in alle_aktiv if a["id"] != q["id"] and a["art"] == "datei" and a["wurzel"] == q["wurzel"]
                and a["adapter"] in ("markdown", "text", "logbuch")}

    def _ueberspringe(self, q, grund, summe):
        summe["uebersprungen"] += 1
        self.audit("WIS_DATEI_UEBERSPRUNGEN", {"quelle": q["id"], "datei": q["pfad"], "grund": grund})

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
