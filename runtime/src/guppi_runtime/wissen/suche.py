"""Suche (Spec 7, D7.5, D7.7; WIS-05, -06, -09, -11): Rechtefilter vor dem Ranking, Wort- und Vektorliste, Güte, Fusion, Volltext-Rückfall.
Ein Teil von `WissenSpeicher` (Mischklasse). Die Suche startet nie einen Server und wartet nie auf einen Start: läuft keiner, fällt sie
sofort auf Volltext zurück und stößt den Start im Hintergrund an (Auflage 4, Prüfung F3)."""
from __future__ import annotations

import json
import time

from . import ausgabe, fusion, glossar, schema, vektor
from .hilfen import _sha

MAX_FRAGE = 500


def filter_sql(f):
    """(Text, Parameter) für den WHERE-Teil auf `a` und `q`; leer ohne Filter (geprüft von `desk_basis.filter_pruefen`).
    Projekt: die Quellen dieses Projekts und die für alle; `bis` schließt den ganzen Tag ein."""
    if not f:
        return "", ()
    teile, params = [], []
    if f.get("quellen"):
        teile.append("q.id IN (" + ",".join("?" * len(f["quellen"])) + ")")
        params += list(f["quellen"])
    if f.get("arten"):
        teile.append("q.adapter IN (" + ",".join("?" * len(f["arten"])) + ")")
        params += list(f["arten"])
    if f.get("projekt"):
        teile.append("(q.projekt IS NULL OR q.projekt = ?)")
        params.append(f["projekt"])
    if f.get("seit"):
        teile.append("a.datum >= ?")
        params.append(f["seit"])
    if f.get("bis"):
        teile.append("a.datum < ?")
        params.append(f["bis"] + "T99")
    return " AND " + " AND ".join(teile), tuple(params)


class SucheTeil:
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

    def suche(self, frage, *, leser, k=5, route="local", mission_id=None, protokoll=True, filter=None):
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
        extra, extra_params = filter_sql(filter)                        # SPEC_SHELL_WISSEN_v1 §4.5: vor dem Ranking, wie der Rechtefilter
        where, params = where + extra, tuple(params) + tuple(extra_params)
        woerter = fusion.woerter(frage)
        if not woerter:
            raise ValueError("wis_anfrage_leer")
        alt = self.alternativen(woerter)
        agent = leser["art"] == "agent"
        befund_sql = " AND a.befunde = '[]'" if agent else ""
        with self.lock:
            tiefe = self.konfig.tiefe
            wort = [r[0] for r in self.db.execute(
                "SELECT a.nr FROM abschnitte_fts f JOIN abschnitte a ON a.nr = f.rowid JOIN quellen q ON q.id = a.quelle WHERE abschnitte_fts MATCH ? AND " + where + befund_sql
                + " ORDER BY bm25(abschnitte_fts, 2.0, 1.0), a.nr LIMIT ?", (fusion.fts_anfrage(glossar.anfrage_woerter(woerter, alt)), *params, tiefe))]
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
        elif self._start_thread is not None and self._start_thread.is_alive():
            grund = "server_startet"
        else:                                                      # ohne Sperre und ohne Start: höchstens `anfrage_timeout_s` (F3)
            anfrage = self.dienst.anfrage_vektor(frage, starten=False)
            if anfrage is None:
                grund = "anfrage_vektor"
                if not self.dienst.antwortet():
                    grund = "server_startet"
                    self._start_anstossen()
        with self.lock:
            self._rueckfall_melden(grund)
            if grund is None:
                erlaubt = {r[0] for r in self.db.execute("SELECT a.nr FROM abschnitte a JOIN quellen q ON q.id = a.quelle WHERE " + where + befund_sql, params)}
                vek = [nr for nr, _ in vektor.top_k(anfrage, self._vektoren_laden(mid), tiefe, erlaubt=lambda nr: nr in erlaubt)]
                g = self._guete(woerter, wort, n_alle, alt)
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
        return {"modus": modus, "hinweis": hinweis, "treffer": out, "modell_id": mid if modus == "hybrid" else None, "abdeckung": round(abdeckung, 4), "ms": ms, "woerter": woerter,
                "glossar": alt}

    def alternativen(self, woerter, an=None):
        """Die Glossar-Alternativen je Fragewort (S7.6 A2); leer, solange `suche.glossar` aus ist."""
        an = self.konfig.glossar_an if an is None else an
        return glossar.alternativen(woerter, self.konfig.glossar) if an and self.konfig.glossar else {}

    def _guete(self, woerter, wort, n_alle, alt=None):
        """g(d) je Abschnitt der Wortliste: welche Wörter ein Abschnitt enthält, entscheidet FTS5 selbst (D7.5). Mit Glossar gilt ein
        Fragewort als enthalten, wenn das Wort oder eine seiner Alternativen im Abschnitt steht (S7.6 A2)."""
        if not wort:
            return {}
        alt = alt or {}
        idf_je_wort, drin = {}, {nr: set() for nr in wort}
        marks = ",".join("?" * len(wort))
        for w in woerter:
            q = fusion.fts_anfrage([w] + list(alt.get(w, [])))
            n_w = self.db.execute("SELECT count(*) FROM abschnitte_fts WHERE abschnitte_fts MATCH ?", (q,)).fetchone()[0]
            idf_je_wort[w] = fusion.idf(n_alle, min(n_w, n_alle))
            for (nr,) in self.db.execute("SELECT rowid FROM abschnitte_fts WHERE abschnitte_fts MATCH ? AND rowid IN (" + marks + ")", (q, *wort)):
                drin[nr].add(w)
        return {nr: fusion.guete(idf_je_wort, enthalten) for nr, enthalten in drin.items()}
