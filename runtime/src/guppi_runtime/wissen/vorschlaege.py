"""Vorschläge der Agenten (Spec 7, D7.8, WIS-10): vorschlagen, aufnehmen (nach Freigabe), ablehnen, zurücknehmen. Ein Teil von
`WissenSpeicher` (Mischklasse), damit `speicher.py` handlich bleibt; `vorschlaege.jsonl` wird immer atomar geschrieben."""
from __future__ import annotations

import json
from pathlib import Path

from . import adapter as adapter_mod
from . import schema
from .hilfen import _sha, befunde_von, schreibe_atomar


class VorschlagTeil:
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
            bisher = datei.read_text(encoding="utf-8") if datei.is_file() else ""
            if bisher and not bisher.endswith("\n"):
                bisher += "\n"
            schreibe_atomar(datei, bisher + json.dumps(zeile, ensure_ascii=False) + "\n")
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
                schreibe_atomar(datei, "".join(z + "\n" for z in zeilen))
            with schema._immediate(self.db):
                self.db.execute("DELETE FROM abschnitte WHERE datei = ?", ("vorschlag:" + vid,))
                self.db.execute("UPDATE vorschlaege SET status = 'veraltet', entschieden = ? WHERE id = ?", (self.uhr(), vid))
            self._vektoren_stempel = None
            self.audit("WIS_VORSCHLAG_ZURUECKGENOMMEN", {"id": vid})
            return {"id": vid, "status": "veraltet"}
