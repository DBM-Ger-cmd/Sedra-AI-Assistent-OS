"""Die Routen der Sprache am Hub (`hub.sprache`, uix_server.py): Aufnehmen in Stücken, Abspielen, Löschen, Sprache → Text.
Für jede Shell – das Werkzeug „Rekorder“ zeichnet den Typ `aufnahme`, und jede Shell kann ihn öffnen. Die Transkription läuft im
Hintergrund (Thread, Unterprozess des Providers); das Werkzeug fragt den Stand ab. Ohne Provider: Abschrift von Hand (`text`)
wird ein Transkript mit Herkunft `manuell` – benannt, nicht erfunden. Audit ohne Inhalt."""
from __future__ import annotations

import shutil
from pathlib import Path

from ..util import utcnow
from . import aufnahmen as au
from . import stt


class SpracheHub:
    def __init__(self, hub):
        self.hub = hub
        self.store = au.Store(hub.project_root)
        self.which = shutil.which          # Tests setzen eine Attrappe
        self.run = None                    # Tests setzen eine Attrappe für subprocess.run
        self.laeufe = {}

    # ---------------------------------------------------------------- Auskunft
    def provider(self):
        return stt.provider_finden(self.which, stt.einstellung(self.hub.project_root))

    def status(self, payload=None):
        """GET /api/sprache/status – welcher Provider da ist (oder warum keiner), und was läuft."""
        p = self.provider()
        return {'stt': p, 'laeuft': sorted(self.laeufe), 'sprachen': list(stt.SPRACHEN)}

    def aufnahmen(self, payload=None):
        """GET /api/sprache/aufnahmen – die Liste (ohne Daten) und die Auskunft zum Provider."""
        return {'aufnahmen': self.store.liste(), 'stt': self.provider()}

    # ---------------------------------------------------------------- Aufnehmen
    def beginnen(self, payload):
        """POST /api/sprache/aufnahme/beginnen {titel, mime, sprache} – ein neuer Record, die Datei leer."""
        p = payload or {}
        a = self.store.beginnen(p.get('titel'), p.get('mime'), str(p.get('sprache') or 'de'), utcnow())
        self.hub.runtime.audit.append('SPRACHE_AUFNAHME_BEGONNEN', component='sprache', payload={'id': a['id'], 'mime': a['mime'], 'sprache': a['sprache']})
        return au.kurz(a)

    def stueck(self, payload):
        """POST /api/sprache/aufnahme/stueck {id, data} – ein Stück base64 anhängen; Antwort: Größe und Zahl der Stücke."""
        p = payload or {}
        a = self.store.anhaengen(p.get('id'), p.get('data'))
        return {'id': a['id'], 'groesse': a['groesse'], 'stuecke': a['stuecke']}

    def beenden(self, payload):
        """POST /api/sprache/aufnahme/beenden {id, dauer} – der Record wird fertig; leer bleibt er nicht (aufnahme_leer)."""
        p = payload or {}
        try:
            a = self.store.beenden(p.get('id'), p.get('dauer'), utcnow())
        except ValueError as exc:
            if str(exc) == 'aufnahme_leer': self.store.loeschen(p.get('id'))
            raise
        self.hub.runtime.audit.append('SPRACHE_AUFNAHME_FERTIG', component='sprache', payload={'id': a['id'], 'dauer': a['dauer'], 'groesse': a['groesse']})
        return au.kurz(a)

    def abspielen(self, payload):
        """POST /api/sprache/aufnahme {id} – der Record mit den Daten (base64) für das <audio>-Element."""
        return self.store.abspielen((payload or {}).get('id'))

    def loeschen(self, payload):
        """POST /api/sprache/aufnahme/loeschen {id} – Datei und Record weg; ein Transkript daraus bleibt (eigener Record)."""
        out = self.store.loeschen((payload or {}).get('id'))
        self.hub.runtime.audit.append('SPRACHE_AUFNAHME_GELOESCHT', component='sprache', payload={'id': out['id']})
        return out

    # ---------------------------------------------------------------- Sprache → Text
    def _transkript_anlegen(self, a, text, herkunft):
        """Das Ergebnis wird ein Transkript-Record (fisch/transkripte.py) – mit der Herkunft im Namen der ersten Fassung."""
        from ..fisch import transkripte as tk
        imp = tk.importieren(text, a['titel'], a['sprache'], self.store.pfad_im_projekt(a))
        return self.hub.fisch.store.schreiben(tk.neu(imp, utcnow(), herkunft=herkunft))

    def transkribieren(self, payload):
        """POST /api/sprache/aufnahme/transkribieren {id, text?} – mit Provider: Lauf im Hintergrund (Antwort sofort, Stand im Record);
        mit `text`: die Abschrift von Hand wird das Transkript (Herkunft manuell). Ohne beides und ohne Provider: kein_provider."""
        p = payload or {}
        a = self.store.get(p.get('id'))
        if a['status'] != 'fertig': raise ValueError('aufnahme_laeuft_noch')
        if a['stt']['status'] == 'laeuft': raise ValueError('transkription_laeuft')
        text = str(p.get('text') or '')
        if text.strip():
            t = self._transkript_anlegen(a, text, 'manuell')
            self.store.stt_setzen(a['id'], 'fertig', utcnow(), provider='manuell', transkript_id=t['id'])
            self.hub.runtime.audit.append('SPRACHE_TRANSKRIBIERT', component='sprache', payload={'id': a['id'], 'provider': 'manuell', 'transkript': t['id']})
            return {'id': a['id'], 'status': 'fertig', 'provider': 'manuell', 'transkript_id': t['id']}
        prov = self.provider()
        if prov['status'] != 'bereit':
            raise ValueError('kein_provider')
        self.store.stt_setzen(a['id'], 'laeuft', utcnow(), provider=prov['provider'])
        datei, ziel = self.store.datei(a), Path(self.hub.project_root) / 'sprache' / 'stt' / a['id']

        def lauf():
            try:
                srt = stt.transkribieren(prov, datei, a['sprache'], ziel, **({'run': self.run} if self.run else {}))
                t = self._transkript_anlegen(a, srt, 'stt:' + prov['provider'])
                self.store.stt_setzen(a['id'], 'fertig', utcnow(), transkript_id=t['id'])
                self.hub.runtime.audit.append('SPRACHE_TRANSKRIBIERT', component='sprache', payload={'id': a['id'], 'provider': prov['provider'], 'transkript': t['id']})
            except Exception as exc:        # der Fehler steht im Record, der Thread stirbt leise
                self.store.stt_setzen(a['id'], 'fehler', utcnow(), fehler=str(exc))
                self.hub.runtime.audit.append('SPRACHE_TRANSKRIPTION_FEHLER', component='sprache', payload={'id': a['id'], 'provider': prov['provider'], 'fehler': str(exc)[:200]})
            finally:
                self.laeufe.pop(a['id'], None)

        import threading
        th = threading.Thread(target=lauf, name='sedra-stt-' + a['id'], daemon=True)
        self.laeufe[a['id']] = th
        th.start()
        return {'id': a['id'], 'status': 'laeuft', 'provider': prov['provider'], 'transkript_id': None}
