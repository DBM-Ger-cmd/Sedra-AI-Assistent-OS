"""Die Routen des Fisches am Hub (uix_server.py: `hub.fisch`). Der Modellaufruf geht wie jeder andere durch den Control Master
(Machbarkeit, Audit, Nutzung, Inhaltsschutz von Build 16) und ist an eine Mission gebunden. Kein Netz, keine Datei außerhalb des Projekts.
Nichts hier erfindet etwas: ohne Modell kommt `no_model`, ohne STT-Provider kommt der benannte Platzhalter."""
from __future__ import annotations

from pathlib import Path

from ..core.util import utcnow
from . import erkenntnisse as ek
from . import nachrichten as nw
from . import transkripte as tk
from . import uebersetzer as ue

PROFIL_DATEI = 'fisch.profil.json'


class FischHub:
    def __init__(self, hub):
        self.hub = hub
        self.store = tk.Store(hub.project_root)

    # ---------------------------------------------------------------- Modell
    def _modell(self, system, user, label, max_tokens=900, temperature=0.3):
        """Ein Modellaufruf ohne Werkzeuge, wie model_test: eine Mission je Aufruf, Antwort als Text."""
        rt = self.hub.runtime
        server = getattr(rt, 'llama_server', None)
        loaded = server.loaded_models() if server is not None else []
        if not loaded:
            grund = getattr(rt, 'llama_server_error', None)
            return {'status': 'no_model', 'message': 'Kein Modell geladen.' + (' Grund: ' + str(grund) if grund else '')}
        model = loaded[0].get('identifier') or loaded[0].get('modelKey')
        with self.hub.lock:
            mission = rt.brain.create_mission(label, None, 'S1')
            out = rt.control.execute(mission, {'action': 'model_inference', 'provider': 'llama-cpp-server', 'model': model,
                                               'temperature': temperature, 'max_tokens': max_tokens,
                                               'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]})
        if out.get('status') != 'completed':
            return {'status': 'failed', 'message': str(out.get('reason_code') or out.get('error') or out.get('status'))[:300]}
        r = out['model_result']
        content = r.get('content') or (r.get('message') or {}).get('content') or ''
        if not str(content).strip():
            return {'status': 'failed', 'message': 'model_answer_empty'}
        return {'status': 'completed', 'model': model, 'content': str(content), 'mission_id': mission['identity']['mission_id'],
                'truncated': r.get('finish_reason') == 'length'}

    # ---------------------------------------------------------------- Übersetzer
    def uebersetzen(self, payload):
        """POST /api/fisch/uebersetzen {text, von, nach, ton, tiefe} – die Nachricht für die Zielrolle; Audit ohne Text."""
        e = ue.pruefen(payload)
        out = self._modell(ue.SYSTEM, ue.nachricht(e), f"Fisch: Übersetzung {e['von']} → {e['nach']}")
        self.hub.runtime.audit.append('FISCH_UEBERSETZT', component='fisch', payload={'von': e['von'], 'nach': e['nach'], 'status': out['status'],
                                                                                      'zeichen': len(e['text'])})
        if out['status'] != 'completed':
            return out
        return dict(out, **ue.lesen(out['content']), von=e['von'], nach=e['nach'], rollen=ue.ROLLEN)

    def rollen(self, payload=None):
        """GET /api/fisch/rollen – die Rollen, Töne und Tiefen (nur lesen)."""
        return {'rollen': [{'id': k, 'name': v[0], 'hinweis': v[1]} for k, v in ue.ROLLEN.items()], 'toene': list(ue.TOENE), 'tiefen': list(ue.TIEFEN)}

    # ---------------------------------------------------------------- Nachrichten
    def _profil_pfad(self):
        return Path(self.hub.project_root) / 'local_config' / PROFIL_DATEI

    def profil(self, payload=None):
        """GET /api/fisch/profil – das News-Profil des Projekts (lokal, keine Cloud)."""
        import json
        p = self._profil_pfad()
        if not p.is_file():
            return {'profil': dict(nw.PROFIL_LEER), 'gespeichert': False}
        try:
            return {'profil': nw.profil_pruefen(json.loads(p.read_text(encoding='utf-8'))), 'gespeichert': True}
        except (ValueError, OSError):
            return {'profil': dict(nw.PROFIL_LEER), 'gespeichert': False}

    def profil_speichern(self, payload):
        """POST /api/fisch/profil – das Profil speichern; Audit ohne Inhalt."""
        import json
        profil = nw.profil_pruefen((payload or {}).get('profil') or payload)
        p = self._profil_pfad(); p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(profil, ensure_ascii=False, indent=1), encoding='utf-8')
        self.hub.runtime.audit.append('FISCH_PROFIL_GESPEICHERT', component='fisch', payload={'interessen': len(profil['interessen']), 'tiefe': profil['tiefe']})
        return {'profil': profil, 'gespeichert': True}

    def brief(self, payload):
        """POST /api/fisch/brief {quellen:[{name, text, datum}], profil?} – der Brief aus gegebenen Quellen. Nie aus dem Netz, nie erfunden."""
        p = payload or {}
        profil = nw.profil_pruefen(p.get('profil') or self.profil()['profil'])
        quellen = nw.quellen_pruefen(p.get('quellen'))
        out = self._modell(nw.SYSTEM, nw.nachricht(profil, quellen, utcnow()[:10]), 'Fisch: Brief aus ' + str(len(quellen)) + ' Quellen', max_tokens=1600)
        self.hub.runtime.audit.append('FISCH_BRIEF', component='fisch', payload={'quellen': len(quellen), 'status': out['status']})
        if out['status'] != 'completed':
            return out
        items = nw.lesen(out['content'], quellen)
        return dict(out, meldungen=items, profil=profil, quellen=[q['name'] for q in quellen],
                    hinweis='' if items else 'Das Modell hat aus diesen Quellen keine Meldung gebildet – das ist in Ordnung, es gibt keine Mindestmenge.')

    # ---------------------------------------------------------------- Transkripte
    def transkripte(self, payload=None):
        """GET /api/fisch/transkripte – die Liste (ohne Text) und die ehrliche Auskunft zum STT-Provider (Kern: hub.sprache)."""
        sprache = getattr(self.hub, 'sprache', None)
        return {'transkripte': self.store.liste(), 'stt': sprache.provider() if sprache is not None else tk.transkribieren()}

    def transkript(self, payload):
        """POST /api/fisch/transkript {id, version?} – ein Transkript mit der gewählten Fassung (Standard: die aktuelle; freigegeben: die eingefrorene)."""
        t = self.store.get((payload or {}).get('id'))
        v = (payload or {}).get('version')
        f = tk.fassung(t, int(v) if v is not None else (t['freigegeben_version'] if t['status'] == 'freigegeben' else None))
        return {'id': t['id'], 'titel': t['titel'], 'sprache': t['sprache'], 'quelle': t['quelle'], 'status': t['status'], 'geschaetzt': t.get('geschaetzt', False),
                'aktuell': t['aktuell'], 'freigegeben_version': t['freigegeben_version'], 'fassung': {k: f[k] for k in ('version', 'herkunft', 'at', 'hash', 'mapping')},
                'versionen': [{k: x[k] for k in ('version', 'herkunft', 'at', 'hash', 'mapping')} for x in t['versionen']], 'cues': f['cues'],
                'erkenntnisse': t.get('erkenntnisse')}

    def transkript_erkenntnisse(self, payload):
        """POST /api/fisch/transkript/erkenntnisse {id} – SEDRA liest die aktuelle Fassung: Zusammenfassung, Entscheidungen, offene Fragen,
        Aufgaben. Gebunden an die Fassung (VoiceBrief); gespeichert am Record, bis eine neue Erkenntnis sie ersetzt. Audit ohne Text."""
        t = self.store.get((payload or {}).get('id'))
        f = tk.fassung(t, t['freigegeben_version'] if t['status'] == 'freigegeben' else None)
        out = self._modell(ek.SYSTEM, ek.nachricht(t, f['cues']), 'Fisch: Erkenntnisse aus ' + t['id'], max_tokens=1200, temperature=0.2)
        self.hub.runtime.audit.append('FISCH_ERKENNTNISSE', component='fisch', payload={'id': t['id'], 'version': f['version'], 'status': out['status']})
        if out['status'] != 'completed':
            return out
        e = dict(ek.lesen(out['content']), version=f['version'], at=utcnow(), model=out['model'], mission_id=out['mission_id'], truncated=out['truncated'])
        t['erkenntnisse'] = e
        self.store.schreiben(t)
        return dict(status='completed', id=t['id'], erkenntnisse=e)

    def transkript_import(self, payload):
        """POST /api/fisch/transkript/import {text, titel, sprache, quelle} – TXT, SRT oder VTT wird ein Record (Version 1, Entwurf)."""
        p = payload or {}
        imp = tk.importieren(p.get('text'), p.get('titel'), str(p.get('sprache') or 'de'), p.get('quelle'))
        t = self.store.schreiben(tk.neu(imp, utcnow()))
        self.hub.runtime.audit.append('FISCH_TRANSKRIPT_IMPORT', component='fisch', payload={'id': t['id'], 'format': imp['format'], 'cues': len(imp['cues']), 'sprache': imp['sprache']})
        return {'id': t['id'], 'titel': t['titel'], 'format': imp['format'], 'cues': len(imp['cues']), 'geschaetzt': imp['geschaetzt']}

    def transkript_suche(self, payload):
        """POST /api/fisch/transkript/suche {id, frage} – ganze Wörter, in Reihenfolge, Groß/Klein egal (LocalScribe)."""
        t = self.store.get((payload or {}).get('id'))
        return {'id': t['id'], 'treffer': tk.suchen(tk.fassung(t)['cues'], (payload or {}).get('frage'))[:200]}

    def transkript_pseudonymisieren(self, payload):
        """POST /api/fisch/transkript/pseudonymisieren {id} – eine neue Fassung mit Platzhaltern (b6core, wie im GateWay);
        das Mapping liegt getrennt (ADR-011). Kein Modell."""
        from ..core.b6core import pseudo as b6pseudo
        from ..core.b6core.normalize import normalize
        from ..core.b6core.privacy import scan_text
        t = self.store.get((payload or {}).get('id'))
        f = tk.fassung(t)
        cues, mapping, funde = [], {}, 0
        for c in f['cues']:
            clean = normalize(c['text']).clean
            scan = scan_text(t['id'], clean)
            res = b6pseudo.pseudonymize(clean, scan)
            funde += len(res.mapping or {})
            mapping.update(res.mapping or {})
            cues.append({'start': c['start'], 'end': c['end'], 'text': res.text})
        t = self.store.neue_fassung(t, cues, 'pseudonymisiert', utcnow(), mapping=mapping)
        self.hub.runtime.audit.append('FISCH_TRANSKRIPT_PSEUDONYMISIERT', component='fisch', payload={'id': t['id'], 'version': t['aktuell'], 'funde': funde})
        return {'id': t['id'], 'version': t['aktuell'], 'funde': funde}

    def transkript_status(self, payload):
        """POST /api/fisch/transkript/status {id, status} – entwurf → geprüft → freigegeben (Golden Record friert die Fassung ein)."""
        p = payload or {}
        t = self.store.get(p.get('id'))
        t = self.store.status_setzen(t, str(p.get('status') or ''), utcnow())
        self.hub.runtime.audit.append('FISCH_TRANSKRIPT_STATUS', component='fisch', payload={'id': t['id'], 'status': t['status'], 'version': t['aktuell']})
        return {'id': t['id'], 'status': t['status'], 'freigegeben_version': t['freigegeben_version']}

    def transkript_export(self, payload):
        """POST /api/fisch/transkript/export {id, format} – TXT/SRT/VTT/JSON in `<Projekt>/fisch/export/`; der Record bleibt unverändert."""
        p = payload or {}
        t = self.store.get(p.get('id'))
        fmt = str(p.get('format') or 'txt')
        inhalt = tk.exportieren(t, fmt)
        ordner = Path(self.hub.project_root) / 'fisch' / 'export'; ordner.mkdir(parents=True, exist_ok=True)
        v = t['freigegeben_version'] if t['status'] == 'freigegeben' else t['aktuell']
        name = f"{t['id']}_v{v}.{fmt}"
        (ordner / name).write_text(inhalt, encoding='utf-8')
        self.hub.runtime.audit.append('FISCH_TRANSKRIPT_EXPORT', component='fisch', payload={'id': t['id'], 'format': fmt, 'version': v, 'vorlaeufig': t['status'] != 'freigegeben'})
        return {'id': t['id'], 'format': fmt, 'version': v, 'datei': str(Path('fisch') / 'export' / name), 'inhalt': inhalt,
                'vorlaeufig': t['status'] != 'freigegeben'}
