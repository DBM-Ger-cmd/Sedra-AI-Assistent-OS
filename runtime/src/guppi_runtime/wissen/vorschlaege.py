"""Vorschläge der Agenten (Spec 7, D7.8, WIS-10): vorschlagen, aufnehmen (nach Freigabe), ablehnen, zurücknehmen. Ein Teil von
`WissenSpeicher` (Mischklasse), damit `speicher.py` handlich bleibt; `vorschlaege.jsonl` wird immer atomar geschrieben."""
from __future__ import annotations

import json
from pathlib import Path

from . import adapter as adapter_mod
from . import schema
from .hilfen import _sha, befunde_von, lies_jsonl, schreibe_atomar


class VorschlagTeil:
    def vorschlagen(self, *, titel, text, belege, agent_id, lauf_id, aufgabe_id, block_ids, leser):
        """Ein Vorschlag eines Agenten: Form, harter Fund, Belege nur aus dem Block, höchstens 20 offene je Agent; Personenbezug erbt
        er von allen Treffern seines Blocks, nicht nur von den genannten Belegen – sonst trüge ein Vorschlag ohne Belege Text aus
        einer Quelle mit Personenbezug ungekennzeichnet weiter (WIS-11, Prüfung F5). Mit `beantrage` (Desk) entsteht sofort der Antrag."""
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
            herkunft = sorted(set(belege) | {str(b) for b in (block_ids or ())})
            if herkunft:
                marks = ",".join("?" * len(herkunft))
                personenbezug = int(bool(self.db.execute("SELECT 1 FROM abschnitte a JOIN quellen q ON q.id = a.quelle WHERE a.id IN (" + marks + ") AND q.personenbezug = 1", herkunft).fetchone()))
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
        with self.lock:
            row = self.db.execute("SELECT * FROM vorschlaege WHERE id = ?", (vid,)).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["belege"] = json.loads(d.get("belege") or "[]")
        return d

    def vorschlaege(self, status="offen"):
        sql = "SELECT * FROM vorschlaege" + (" WHERE status = ?" if status else "") + " ORDER BY erstellt DESC, id"
        out = []
        with self.lock:
            rows = self.db.execute(sql, (status,) if status else ()).fetchall()
        for r in rows:
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

    def _vorschlaege_datei(self):
        return self.projekt_root / Path(*adapter_mod.VORSCHLAEGE.split("/"))

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
            datei = self._vorschlaege_datei()
            zeile = {"id": v["id"], "titel": v["titel"], "text": v["text"], "hash": v["hash"], "stufe": stufe, "projekt": projekt, "personenbezug": p,
                     "agent_id": v["agent_id"], "lauf_id": v["lauf_id"], "aufgabe_id": v["aufgabe_id"], "belege": v["belege"], "freigegeben": jetzt, "gate": str(gate_id)}
            qid = self._vorschlag_quelle(stufe, projekt, p, gate_id, mission_id)
            alt = [z for z in lies_jsonl(datei) if z.get("id") != v["id"]]
            with schema._immediate(self.db):                          # Status und Datei zusammen: scheitert die Datei, rollt der Status zurück (F6)
                self.db.execute("UPDATE vorschlaege SET status = 'freigegeben', entschieden = ?, vorschlag_stufe = ?, vorschlag_projekt = ?, personenbezug = ? WHERE id = ?",
                                (jetzt, stufe, projekt, p, v["id"]))
                schreibe_atomar(datei, "".join(json.dumps(z, ensure_ascii=False) + "\n" for z in alt + [zeile]))
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
        """Rücknahme eines aufgenommenen Vorschlags (enger, ohne Gate): Zeile aus `vorschlaege.jsonl` (erst die Datei: scheitert sie,
        bleibt der Status), Abschnitte weg, Status `veraltet`."""
        with self.lock:
            v = self.vorschlag(vid)
            if v is None:
                raise ValueError("wis_vorschlag_unbekannt")
            datei = self._vorschlaege_datei()
            if datei.is_file():
                schreibe_atomar(datei, "".join(json.dumps(z, ensure_ascii=False) + "\n" for z in lies_jsonl(datei) if z.get("id") != vid))
            with schema._immediate(self.db):
                self.db.execute("DELETE FROM abschnitte WHERE datei = ?", ("vorschlag:" + vid,))
                self.db.execute("UPDATE vorschlaege SET status = 'veraltet', entschieden = ? WHERE id = ?", (self.uhr(), vid))
            self._vektoren_stempel = None
            self.audit("WIS_VORSCHLAG_ZURUECKGENOMMEN", {"id": vid})
            return {"id": vid, "status": "veraltet"}
