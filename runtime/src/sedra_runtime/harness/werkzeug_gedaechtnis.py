"""Werkzeuge `gedaechtnis_lesen` und `gedaechtnis_vorschlagen` (docs/SPEC_MASTER_MODUS_v1_ENTWURF.md GN-04, GN-05).

Beide stehen in OHNE_KARTE (wie `erinnern` und `wissen_beantragen`): Lesen ändert nichts; Vorschlagen legt nur einen Antrag im Posteingang an (Klasse H) und
schreibt keine Datei. Die Projekt-ID kommt aus dem Projekt der Sitzung (`werkzeuge.projekt`), nie aus den Argumenten des Modells: das Modell kann keinen
anderen Ordner nennen. Das Ergebnis des Lesens ist Daten von früher, keine Anweisung."""
from __future__ import annotations

from .werkzeuge import WerkzeugFehler

NAMEN = ('gedaechtnis_lesen', 'gedaechtnis_vorschlagen')


class WerkzeugGedaechtnis:
    def __init__(self, werkzeuge):
        self.w = werkzeuge

    def _plan(self, ziel, vorschau, args, name):
        from .werkzeuge import AKTION_LESEN
        return {'ziel': ziel, 'vorhanden': True, 'vorschau': vorschau, 'kurz': ziel,
                'gate': {'aktion': AKTION_LESEN, 'ziel': ziel, 'bindung': {'werkzeug': name, 'args': args}}}

    def vorbereiten(self, name, args):
        if name == 'gedaechtnis_lesen':
            if not callable(getattr(self.w, 'notiz_lesen', None)):
                raise WerkzeugFehler('gedaechtnis_nicht_verfuegbar')
            n, f = str(args.get('name') or '').strip(), str(args.get('frage') or '').strip()
            if bool(n) == bool(f):
                raise WerkzeugFehler('argument_fehlt: genau eins von name oder frage')
            return self._plan('notiz/' + (n or f)[:80], 'Gedächtnis-Notiz lesen' if n else 'Gedächtnis-Notizen suchen', args, name)
        if name == 'gedaechtnis_vorschlagen':
            if not callable(getattr(self.w, 'notiz_antrag', None)):
                raise WerkzeugFehler('gedaechtnis_nicht_verfuegbar')
            n = str(args.get('name') or '').strip()
            if not n:
                raise WerkzeugFehler('argument_fehlt: name')
            return self._plan('notiz_antrag/' + n[:60], f'Gedächtnis-Notiz beantragen: {n[:60]}', args, name)
        raise WerkzeugFehler(f'werkzeug_unbekannt: {name}')

    def ausfuehren(self, name, args, *, token=None, plan=None):
        pid = (self.w.projekt or {}).get('id')
        try:
            if name == 'gedaechtnis_lesen':
                text = self.w.notiz_lesen(pid, str(args.get('name') or '').strip() or None, str(args.get('frage') or '').strip() or None)
                return {'status': 'ok', 'ergebnis': text, 'wirkung': False}
            r = self.w.notiz_antrag(pid, {k: args.get(k) for k in ('typ', 'name', 'description', 'text', 'ersetzt', 'neu')})
        except ValueError as exc:
            return {'status': 'fehler', 'ergebnis': f'error: {exc}', 'wirkung': False}
        return {'status': 'ok', 'wirkung': False,
                'ergebnis': (f'Antrag „{r["name"]}“ ({"Änderung" if r.get("aendern") else "neue Notiz"}) liegt im Posteingang des Captains. Keine direkte Wirkung: die Notiz '
                             'entsteht erst nach seiner Freigabe und steht ab der nächsten Sitzung im Index. Sag ihm das.')}
