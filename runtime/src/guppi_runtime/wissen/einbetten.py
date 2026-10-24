"""Einbetten (Spec 7, D7.4, WIS-04, WIS-12): Modellwechsel, Einbett-Schritt, Nachführen, Hintergrundstart des Embedding-Servers. Ein Teil
von `WissenSpeicher` (Mischklasse). `self.lock` gilt nur für die Datenbank, nie für Start, Stapel oder Anfrage des Servers (Auflage 4,
Prüfung F3); ein Einbett-Schritt zur Zeit (`_einbett_lock`)."""
from __future__ import annotations

import threading

from . import schema, zerlegen


class EinbettTeil:
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

    def _offene(self, mid, n):
        """Offene Vektoren ohne die Abschnitte, die der Server in diesem Prozess schon allein abgelehnt hat (F2)."""
        with self.lock:
            rows = [r for r in schema.offene_vektoren(self.db, mid, n + len(self._vektor_fehler)) if (r[0], r[2]) not in self._vektor_fehler][:n]
            if getattr(self.dienst.e, "eingabeformat", "e1") == "e2" and rows:            # S7.6 A1: Dokument > Stelle, Tabellen als „Spalte: Wert“
                marks = ",".join("?" * len(rows))
                quelle = {r["nr"]: r for r in self.db.execute("SELECT nr, datei, stelle, text FROM abschnitte WHERE nr IN (" + marks + ")", [r[0] for r in rows])}
                rows = [(nr, zerlegen.eingabetext_e2(quelle[nr]["datei"], quelle[nr]["stelle"], quelle[nr]["text"]), h) for nr, _, h in rows]
        return rows

    def _schreibe(self, mid, zeilen):
        with self.lock:
            return schema.schreibe_vektoren(self.db, mid, self.konfig.dim, zeilen)

    def _markiere(self, nr, hash_, grund):
        self._vektor_fehler.add((nr, hash_))
        self.audit("WIS_ABSCHNITT_NICHT_EINBETTBAR", {"abschnitt": nr, "hash": hash_, "grund": str(grund)[:80]})

    def einbetten_schritt(self):
        """Ein Schritt des Dienstes (`EmbeddingDienst.lauf`) über die offenen Vektoren; Pause und Ende stehen in `laeufe`.
        Die Sperre gilt nur für die Datenbank (lesen, schreiben), nicht für Start und Stapel (F3); ein zweiter gleichzeitiger
        Schritt endet sofort mit `beschaeftigt`."""
        if not self._einbett_lock.acquire(blocking=False):
            return {"geraet": "cpu", "eingebettet": 0, "dauer_s": 0.0, "ende": "beschaeftigt", "grund": "anderer_schritt", "uebersprungen": 0}
        try:
            with self.lock:
                ok, grund = self.dienst.bereit()
                if not ok:
                    self._letzter_schritt = {"geraet": "cpu", "eingebettet": 0, "dauer_s": 0.0, "ende": "fehler", "grund": grund, "uebersprungen": 0}
                    return self._letzter_schritt
                self._modell_pruefen()
                mid = self.dienst.modell_id()
                start = self.uhr()
            out = self.dienst.lauf(lambda n: self._offene(mid, n), lambda zeilen: self._schreibe(mid, zeilen), markiere=self._markiere)
            with self.lock:
                with schema._immediate(self.db):
                    status = "pausiert" if out["ende"] == "pause" else "abgebrochen" if out["ende"] == "fehler" else "fertig"
                    self.db.execute("INSERT INTO laeufe (art, start, ende, geraet, lease, eingebettet, pause_grund, status) VALUES ('einbetten', ?, ?, 'cpu', 0, ?, ?, ?)",
                                    (start, self.uhr(), out["eingebettet"], out.get("grund") or None, status))
                if out["ende"] == "fertig" and not self._offene(mid, 1):
                    with schema._immediate(self.db):
                        self.db.execute("UPDATE laeufe SET status = 'fertig', ende = ? WHERE art = 'neuaufbau' AND status = 'laeuft'", (self.uhr(),))
                self._vektoren_stempel = None
                self._letzter_schritt = out
            return out
        finally:
            self._einbett_lock.release()

    def nachfuehren(self):
        """Abgleich und ein Einbett-Schritt (Typ-Verb `wissen.nachfuehren` und Takt, G2-S7-j); keine Sperre über beides (F3)."""
        a = self.abgleich()
        e = self.einbetten_schritt()
        with self.lock:
            self.dienst.leerlauf_pruefen()
        return {"abgleich": a, "einbetten": e}

    def _start_anstossen(self):
        """Den Embedding-Server im Hintergrund starten, damit die nächste Suche hybrid ist; die jetzige wartet nicht (F3)."""
        if self._start_thread is not None and self._start_thread.is_alive():
            return

        def run():
            try:
                self.dienst.starte()
            except Exception:                                      # Fehlstarts zählt der Dienst selbst (`bereit`)
                pass
        self._start_thread = threading.Thread(target=run, name="wissen-embed-start", daemon=True)
        self._start_thread.start()
