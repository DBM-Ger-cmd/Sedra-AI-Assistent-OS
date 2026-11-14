"""W3-Werkzeuge `desktop_aendern` und `profil_wechseln` (Spec W3, 14.11.2026).

Eigene Datei, unter 400 Zeilen. `werkzeuge.py` ruft nur die beiden Zweige
(`vorbereiten` / `ausfuehren`) und fügt Schemas, NAMEN und WIRKUNGSKLASSE hinzu.
Die Werkzeuge schreiben nie direkt: `vorbereiten` baut einen Diff
(`difflib.unified_diff` über JSON) und eine Karte mit `gate.aktion = 'update_desktop'`;
`ausfuehren` delegiert an `harness/desktop.py` (speichern / profil_anwenden /
vorlage_uebernehmen) und publiziert das Event `harness.desktop`.
"""
from __future__ import annotations

import difflib
import json
from pathlib import Path

from . import desktop as dt
from .werkzeuge import WerkzeugFehler

TEILE = dt.TEILE  # ('start', 'zellen', 'marke', 'startseite', 'layout')


def _dump(wahl):
    return json.dumps(wahl, ensure_ascii=False, sort_keys=True, indent=1)


def _diff(alt, neu, rel):
    zeilen = list(difflib.unified_diff(
        _dump(alt).splitlines(), _dump(neu).splitlines(),
        'a/' + rel, 'b/' + rel, lineterm=''))
    return '\n'.join(zeilen)


class WerkzeugDesktop:
    def __init__(self, werkzeuge):
        self.w = werkzeuge  # Werkzeuge-Instanz (wurzel, melden, ...)

    # ---- Vorbereiten: Ziel, Vorschau (Diff), Gate – ohne Wirkung

    def vorbereiten(self, name, args):
        if name == 'desktop_aendern':
            return self._vorbereiten_desktop_aendern(args)
        if name == 'profil_wechseln':
            return self._vorbereiten_profil_wechseln(args)
        raise WerkzeugFehler(f'werkzeug_unbekannt: {name}')

    def _vorbereiten_desktop_aendern(self, args):
        args = args if isinstance(args, dict) else {}
        if not args:
            raise WerkzeugFehler(
                'argument_fehlt: desktop_aendern braucht mindestens einen Teil '
                '(start, zellen, marke, startseite, layout)')
        ungültig = [k for k in args if k not in TEILE]
        if ungültig:
            raise WerkzeugFehler(
                'argument_fehlt: unbekannter Teil ' + ', '.join(ungültig)
                + ' (erlaubt: ' + ', '.join(TEILE) + ')')
        try:
            neu_wahl = dt.pruefen(args)
        except ValueError as exc:
            raise WerkzeugFehler('argument_fehlt: ' + str(exc)) from exc
        jetzt = dt.laden(str(self.w.wurzel))
        teile = sorted(args)
        ziel = 'desktop/' + ','.join(teile)
        alt = {t: jetzt[t] for t in teile}
        diff_text = _diff(alt, {t: neu_wahl[t] for t in teile}, ziel)
        return {
            'ziel': ziel,
            'vorhanden': True,
            'vorschau': diff_text,
            'kurz': ziel,
            'diff': diff_text,
            'neu_wahl': neu_wahl,
            'teile': teile,
            'gate': {
                'aktion': 'update_desktop',
                'ziel': ziel,
                'bindung': {'werkzeug': 'desktop_aendern', 'args': args, 'diff': diff_text},
            },
        }

    def _vorbereiten_profil_wechseln(self, args):
        args = args if isinstance(args, dict) else {}
        profil = args.get('profil')
        vorlage = args.get('vorlage')
        if profil is None and vorlage is None:
            raise WerkzeugFehler(
                'argument_fehlt: profil_wechseln braucht genau eines von profil/vorlage')
        if profil is not None and vorlage is not None:
            raise WerkzeugFehler(
                'argument_fehlt: profil_wechseln braucht genau eines von profil/vorlage (nicht beides)')
        if profil is not None:
            quelle = 'profil'
            profil_id = str(profil)
            try:
                p = dt.profil_lesen(str(self.w.wurzel), profil_id)
            except ValueError as exc:
                raise WerkzeugFehler('argument_fehlt: ' + str(exc)) from exc
            neu_wahl = {t: p[t] for t in TEILE}
        else:
            quelle = 'vorlage'
            profil_id = str(vorlage)
            try:
                v = dt.vorlage_lesen(profil_id)
            except ValueError as exc:
                raise WerkzeugFehler('argument_fehlt: ' + str(exc)) from exc
            profil_id = v['id']
            neu_wahl = {t: v[t] for t in TEILE}
        jetzt = dt.laden(str(self.w.wurzel))
        ziel = quelle + '/' + profil_id
        diff_text = _diff({t: jetzt[t] for t in TEILE}, neu_wahl, ziel)
        return {
            'ziel': ziel,
            'vorhanden': True,
            'vorschau': diff_text,
            'kurz': ziel,
            'diff': diff_text,
            'quelle': quelle,
            'profil_id': profil_id,
            'neu_wahl': neu_wahl,
            'gate': {
                'aktion': 'update_desktop',
                'ziel': ziel,
                'bindung': {'werkzeug': 'profil_wechseln', 'args': args, 'diff': diff_text,
                            'quelle': quelle},
            },
        }

    # ---- Ausführen (Token ist schon geprüft; Delegation an desktop.py)

    def ausfuehren(self, name, args, *, token=None, plan=None):
        plan = plan or self.vorbereiten(name, args)
        wurzel = str(self.w.wurzel)
        if name == 'desktop_aendern':
            teile = plan['teile']
            neu = {t: plan['neu_wahl'][t] for t in teile}
            dt.speichern(wurzel, neu)
            daten = dt.laden(wurzel)  # neue Wahl komplett, für das Event
            ergebnis = 'Desktop aktualisiert (' + ', '.join(teile) + ')'
        else:
            quelle = plan['quelle']
            pid = plan['profil_id']
            if quelle == 'profil':
                dt.profil_anwenden(wurzel, pid)
            else:
                dt.vorlage_uebernehmen(wurzel, pid)
            daten = {'werkzeug': 'profil_wechseln', 'quelle': quelle, 'id': pid}
            ergebnis = 'Profil ' + pid + ' angewendet'
        melde = getattr(self.w, 'melden', None)
        if callable(melde):
            try:
                melde('harness.desktop', daten)
            except Exception:
                pass
        return {'status': 'ok', 'ergebnis': ergebnis, 'wirkung': True}
