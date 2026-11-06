"""Abgleich und Stand je Datei (SPEC_WISSEN_KERN_v1 WK-22, WK-23; G2 K5 §2.4, §2.5): ein Teil von `WissenSpeicher` (Mischklasse).

Bisher las der Abgleich bei jeder Änderung die ganze Quelle neu (B1). Jetzt merkt sich die Tabelle `dateien` je Datei den Hash
(„Größe:mtime_ns“), den Zustand und die Zahl der Abschnitte. Gelesen und zerlegt werden nur neue und geänderte Dateien, höchstens
`konfig.dateien_je_schritt` je Durchgang; was fehlt, verliert seine Abschnitte. Eine unlesbare Datei behält ihre alten Abschnitte und steht als
`uebersprungen` mit Grund da (Hash leer: beim nächsten Abgleich wird sie wieder versucht). Der Quell-Hash wird erst gesetzt, wenn keine Datei
mehr offen ist – sonst macht der nächste Durchgang weiter. Audit ohne Text: Zahlen, je Durchgang höchstens AUDIT_DATEIEN Einzelmeldungen."""
from __future__ import annotations

from . import schema, zerlegen
from .hilfen import _sha, befunde_von

AUDIT_DATEIEN = 20
STAND_MAX = 500


class DateienTeil:
    def _abgleich_je_datei(self, q, ad, qh, ausschluss, summe):
        """Für Datei-Adapter (markdown, text, logbuch, dokumente): den Abgleich dieser Quelle je Datei. Rückgabe die Zählung (neu, geaendert, entfernt, gesperrt)."""
        liste = [(rel, p, h) for rel, p, h in ad.datei_liste(q) if rel not in ausschluss]
        if q.get("quell_hash") is None:                            # das vereinbarte Zeichen „alles neu zerlegen“ (neue Zerleger-Version, Ausschluss geändert)
            with schema._immediate(self.db):                       # je Datei vergessen und das Zeichen verbrauchen – sonst begänne jeder Schritt wieder vorn
                self.db.execute("UPDATE dateien SET hash = '' WHERE quelle = ?", (q["id"],))
                self.db.execute("UPDATE quellen SET quell_hash = '' WHERE id = ?", (q["id"],))
        alt ={r["datei"]: r["hash"] for r in self.db.execute("SELECT datei, hash FROM dateien WHERE quelle = ?", (q["id"],))}
        mit_abschnitten = {r[0] for r in self.db.execute("SELECT DISTINCT datei FROM abschnitte WHERE quelle = ?", (q["id"],))}
        da = {rel for rel, _, _ in liste}
        offen = [(rel, p, h) for rel, p, h in liste if alt.get(rel) != h]
        weg = sorted((set(alt) | mit_abschnitten) - da)
        schritt = offen[:max(1, int(getattr(self.konfig, "dateien_je_schritt", 200)))]
        neue, zeilen, gemeldet, gesperrt = [], {}, 0, 0
        for rel, p, h in schritt:
            try:
                stuecke = ad.stuecke_datei(q, p)
            except ValueError as exc:
                zeilen[rel] = {"hash": "", "zustand": "uebersprungen", "grund": str(exc)[:200], "abschnitte": 0, "gesperrt": 0}
                if gemeldet < AUDIT_DATEIEN:
                    self.audit("WIS_DATEI_UEBERSPRUNGEN", {"quelle": q["id"], "datei": rel, "grund": str(exc)[:120]})
                gemeldet += 1
                continue
            n, g, gesehen = 0, 0, set()
            for datei, datum, s in stuecke:
                hart, weich = befunde_von(s["text"])
                if hart:
                    g += 1
                    self.audit("WIS_ABSCHNITT_GESPERRT", {"quelle": q["id"], "datei": datei, "stelle_sha256": _sha(s["stelle"]), "regeln": hart})
                    continue
                teil = s["teil"]
                while (s["stelle"], teil) in gesehen:
                    teil += 1
                gesehen.add((s["stelle"], teil))
                neue.append({"datei": datei, "stelle": s["stelle"], "teil": teil, "text": s["text"], "hash": zerlegen.abschnitt_hash(s["stelle"], s["text"], zerlegen.ZERLEGER_VERSION),
                             "datum": datum or "1970-01-01T00:00:00Z", "befunde": weich})
                n += 1
            gesperrt += g
            zeilen[rel] = {"hash": h, "zustand": "aufgenommen", "grund": None, "abschnitte": n, "gesperrt": g}
        betroffen = {rel for rel, z in zeilen.items() if z["zustand"] == "aufgenommen"} | set(weg)
        abgleich = schema.vergleiche_dateien(self.db, q["id"], neue, betroffen)
        jetzt = self.uhr()
        zahl = schema.wende_an(self.db, q["id"], abgleich, jetzt=jetzt)
        groessen = {rel: _groesse(p) for rel, p, _ in schritt}
        rest = len(offen) - len(schritt)
        with schema._immediate(self.db):
            for rel, z in zeilen.items():
                self.db.execute("INSERT OR REPLACE INTO dateien (quelle, datei, hash, art, zustand, grund, abschnitte, gesperrt, groesse, geprueft) VALUES (?,?,?,?,?,?,?,?,?,?)",
                                (q["id"], rel, z["hash"], _art(rel), z["zustand"], z["grund"], z["abschnitte"], z["gesperrt"], groessen.get(rel, 0), jetzt))
            for i in range(0, len(weg), 500):
                teil = weg[i:i + 500]
                self.db.execute("DELETE FROM dateien WHERE quelle = ? AND datei IN (" + ",".join("?" * len(teil)) + ")", (q["id"], *teil))
            if rest == 0:
                self.db.execute("UPDATE quellen SET quell_hash = ? WHERE id = ?", (qh, q["id"]))
            self.db.execute("INSERT INTO laeufe (art, start, ende, geraet, neu, geaendert, entfernt, status) VALUES ('abgleich', ?, ?, NULL, ?, ?, ?, 'fertig')",
                            (jetzt, self.uhr(), zahl["neu"], zahl["geaendert"], zahl["entfernt"]))
        uebersprungen = sum(1 for z in zeilen.values() if z["zustand"] == "uebersprungen")
        summe["dateien_uebersprungen"] += uebersprungen
        summe["dateien_offen"] = summe.get("dateien_offen", 0) + rest
        self.audit("WIS_ABGLEICH", {"quelle": q["id"], **zahl, "gesperrt": gesperrt, "dateien": len(schritt), "dateien_offen": rest,
                                    "dateien_uebersprungen": uebersprungen, "dateien_weg": len(weg)})
        return dict(zahl, gesperrt=gesperrt)

    def dateien_stand(self, quelle_id, *, zustand=None, limit=100):
        """WK-22: {summen: {aufgenommen, uebersprungen, offen, gesperrt, abschnitte}, dateien: [...]} einer Quelle. `offen` sind Dateien, die
        der Adapter sieht, die aber noch nicht (oder in einer anderen Fassung) aufgenommen sind; `restzeit_s` bleibt leer, solange nichts gemessen ist."""
        if zustand not in (None, "aufgenommen", "uebersprungen"):
            raise ValueError("wis_zustand_ungueltig")
        limit = max(1, min(int(limit), STAND_MAX))
        with self.lock:
            q = self._quelle(quelle_id)
            if q is None:
                raise ValueError("wis_quelle_unbekannt")
            rows = [dict(r) for r in self.db.execute("SELECT datei, art, zustand, grund, abschnitte, gesperrt, groesse, geprueft, hash FROM dateien WHERE quelle = ? ORDER BY datei", (quelle_id,))]
            offen = None
            if q["adapter"] in ("markdown", "text", "logbuch", "dokumente") and q["aktiv"]:
                try:
                    ad = self._adapter(q["adapter"])
                    bekannt = {r["datei"]: r["hash"] for r in rows if r["zustand"] == "aufgenommen"}
                    offen = sum(1 for rel, _, h in ad.datei_liste(q) if bekannt.get(rel) != h)
                except ValueError:
                    offen = None
        summen = {"aufgenommen": sum(1 for r in rows if r["zustand"] == "aufgenommen"), "uebersprungen": sum(1 for r in rows if r["zustand"] == "uebersprungen"),
                  "offen": offen, "gesperrt": sum(r["gesperrt"] for r in rows), "abschnitte": sum(r["abschnitte"] for r in rows)}
        liste = [{k: v for k, v in r.items() if k != "hash"} for r in rows if zustand is None or r["zustand"] == zustand][:limit]
        return {"quelle": quelle_id, "summen": summen, "dateien": liste, "restzeit_s": None}


def _art(rel):
    punkt = rel.rfind(".")
    return rel[punkt + 1:].lower()[:10] if punkt > rel.rfind("/") else ""


def _groesse(p):
    try:
        return p.stat().st_size
    except OSError:
        return 0
