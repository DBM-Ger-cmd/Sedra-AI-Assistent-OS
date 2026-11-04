"""Anträge der Einstellungen mit Gate (SPEC_HARNESS_SHELL_v1 Stufe 5, G2 §4/§5, D-U2/D-U4, G3 N1/N2).

Der Editor schreibt nie direkt: `katalog_antrag`/`katalog_entfernen_antrag`/`grenzen_antrag` legen über `desk/gated.request` einen
Antrag an, der im Posteingang des Captains steht. Erst „Freigeben und anwenden“ (`gated.decide`) ruft den Applier dieser Art, und der
prüft vor dem Schreiben, ob der Stand noch derselbe ist wie beim Antrag (`binding_stale`, G2 §4.4). Die Applier sind Modulfunktionen,
damit `register_applier` sie bei einem zweiten Hub im selben Prozess wiedererkennt; registriert werden sie in `uix_server` vor
`kinds.freeze()` (wie `desk_wissen`)."""
from __future__ import annotations

import subprocess
from pathlib import Path

from ..desk import gated
from . import code_stand as harness_code_stand
from . import katalog as harness_katalog
from . import projekte as harness_projekte
from . import vorlagen as harness_vorlagen
from . import vorlagen_neu as harness_vorlagen_neu

KIND_KATALOG = 'harness_katalog'
KIND_VORLAGE = 'harness_vorlage'
PROJEKT_ANTRAEGE_MAX = 5                 # offene „Ordner öffnen“-Anträge zugleich
KIND_PROJEKT = 'harness_projekt'            # P0 M3 (1.11.): „Ordner öffnen“ → Laufzeitdatei, nie local_config
KIND_CODE_STAND = 'harness_code_stand'      # 04.11.: „Code-Stand übernehmen“ → gesehener Stand unter runtime_data/harness/code_stand
ZIEL_CODE_STAND = 'runtime_data/harness/code_stand'
ZIEL_KATALOG = 'local_config/' + harness_katalog.DATEI
ZIEL_PROJEKTE = harness_projekte.LAUFZEIT.as_posix()


def _vorlage_regeln():
    return harness_katalog.pruefen(__import__('yaml').safe_load(harness_katalog.VORLAGE.read_text(encoding='utf-8')))


def _stand(projekt_root):
    """Die Regeln, die gerade gelten (Datei des Captains oder Vorlage), ihr Hash und die Quelle; eine ungültige Datei zählt als leer."""
    try:
        geladen = harness_katalog.laden(projekt_root)
        return geladen['regeln'], harness_katalog.hash_von(geladen['regeln']), geladen['quelle']
    except harness_katalog.KatalogFehler:
        return [], harness_katalog.hash_von([]), None


def katalog_antrag(hub, regeln):
    """POST katalog/antrag {regeln}: prüfen (400 mit Satz bei Fehler), Befunde als Risiken, dann ein Antrag mit genauer Bindung."""
    try:
        regeln = harness_katalog.pruefe_entwurf(regeln)
    except harness_katalog.KatalogFehler as exc:
        raise ValueError('entwurf_ungueltig: ' + str(exc)) from exc
    stand, stand_hash, _ = _stand(hub.project_root)
    befunde, zahlen = harness_katalog.befunde(regeln, stand, _vorlage_regeln())
    entwurf_hash = harness_katalog.hash_von(regeln)
    if entwurf_hash == stand_hash:
        raise ValueError('entwurf_unveraendert')
    diff = f"{len(zahlen['neu'])} neu, {len(zahlen['geaendert'])} geändert, {len(zahlen['entfernt'])} entfernt"
    binding = {'entwurf_hash': entwurf_hash, 'stand_hash': stand_hash, 'regeln': regeln}
    req = gated.request(hub, KIND_KATALOG, 'HARNESS_KATALOG_WRITE', ZIEL_KATALOG, binding, risks=[diff] + befunde, exact=True,
                        describe=f'Freigabe-Katalog schreiben ({diff})')
    return {'mission_id': req['mission_id'], 'befunde': befunde, 'zahlen': zahlen, 'entwurf_hash': entwurf_hash, 'stand_hash': stand_hash}


def katalog_entfernen_antrag(hub):
    """POST katalog/entfernen: die Datei des Captains mit Sicherung entfernen – danach gilt die Vorlage."""
    stand, stand_hash, quelle = _stand(hub.project_root)
    if quelle != 'local_config' and not (hub.project_root / ZIEL_KATALOG).is_file():
        raise ValueError('keine_datei_des_captains')
    binding = {'stand_hash': stand_hash}
    req = gated.request(hub, KIND_KATALOG, 'HARNESS_KATALOG_REMOVE', ZIEL_KATALOG, binding, exact=True,
                        risks=[f'{len(stand)} Regeln der Datei des Captains werden durch die Vorlage ersetzt (Sicherung bleibt)'],
                        describe='Freigabe-Katalog: zurück zur Vorlage')
    return {'mission_id': req['mission_id'], 'stand_hash': stand_hash}


def _katalog_anwenden(hub, binding):
    _, stand_hash, _ = _stand(hub.project_root)
    if stand_hash != binding.get('stand_hash'):
        raise ValueError(gated.STALE)
    try:
        if 'regeln' in binding:
            out = harness_katalog.schreiben(hub.project_root, binding['regeln'])
            ereignis = 'HARNESS_KATALOG_WRITTEN'
        else:
            out = harness_katalog.entfernen(hub.project_root)
            ereignis = 'HARNESS_KATALOG_REMOVED'
    except (OSError, harness_katalog.KatalogFehler) as exc:
        raise ValueError(gated.REFUSED + 'katalog_nicht_schreibbar: ' + str(exc)) from None
    hub.runtime.audit.append(ereignis, component='harness', payload=dict(out, ziel=ZIEL_KATALOG))
    hub.events.publish('harness.katalog', {'ereignis': ereignis, 'datei': out.get('datei'), 'sicherung': out.get('sicherung')})
    return out


def grenzen_antrag(hub, vorlage_id, max_zuege):
    """POST vorlagen/grenzen {vorlage, max_zuege}: Antrag auf eine Kopie der Vorlage in local_config mit anderer Grenze (D-U4)."""
    if not isinstance(max_zuege, int) or isinstance(max_zuege, bool) or not 4 <= max_zuege <= 40:
        raise ValueError('max_zuege_ungueltig: 4 bis 40')
    try:
        v = harness_vorlagen.laden(hub.project_root, vorlage_id)
    except harness_vorlagen.VorlageFehler as exc:
        raise ValueError(str(exc)) from exc
    if v['max_zuege'] == max_zuege:
        raise ValueError('grenze_unveraendert')
    binding = {'vorlage': v['id'], 'max_zuege': max_zuege, 'stand_hash': v['hash'], 'vorher': v['max_zuege']}
    ziel = f'local_config/harness_vorlagen/{v["id"]}.yaml'
    risiko = (f'Vorlage „{v["name"]}“: max_zuege {v["max_zuege"]} → {max_zuege}' + (' (mehr Züge je Antwort)' if max_zuege > v['max_zuege'] else ''))
    req = gated.request(hub, KIND_VORLAGE, 'HARNESS_VORLAGE_WRITE', ziel, binding, risks=[risiko], exact=True,
                        describe=f'Grenze der Vorlage {v["id"]}: max_zuege {max_zuege}')
    return {'mission_id': req['mission_id'], 'vorlage': v['id'], 'max_zuege': max_zuege, 'vorher': v['max_zuege']}


def vorlage_neu_antrag(hub, payload):
    """POST vorlagen/neu {name, beschreibung?, basis?, werkzeuge?, system?, modell?}: prüfen (400 mit Satz), dann ein Antrag; die Dateien entstehen erst nach der Freigabe."""
    try:
        e = harness_vorlagen_neu.entwurf(hub.project_root, payload)
    except harness_vorlagen.VorlageFehler as exc:
        raise ValueError(str(exc)) from exc
    v = e['vorlage']
    offen = getattr(hub, '_open_requests', None)
    offene = [r for r in (offen() if callable(offen) else []) if r.get('kind') == KIND_VORLAGE and (r.get('binding') or {}).get('neu')]
    if len(offene) >= harness_vorlagen_neu.OFFEN_MAX:
        raise ValueError(f'zu_viele_offene_antraege: {len(offene)} Vorlagen-Anträge warten schon im Posteingang – erst die entscheiden')
    if any((r.get('binding') or {}).get('vorlage') == v['id'] for r in offene):
        raise ValueError('antrag_liegt_schon_im_posteingang: Vorlage ' + v['id'])
    binding = {'neu': True, 'vorlage': v['id'], 'yaml': e['yaml'], 'md': e['md']}
    ziel = f'local_config/harness_vorlagen/{v["id"]}.yaml'
    risks = [f'Neue Vorlage „{v["name"]}“ ({v["id"]}) mit {len(v["werkzeuge"])} Werkzeugen: ' + ', '.join(v['werkzeuge']),
             'Keine Rechte und keine Sitzungs-Erlaubnisse; Modell der Vorlage: ' + (v['modell'] or 'das der Sitzung')]
    req = gated.request(hub, KIND_VORLAGE, 'HARNESS_VORLAGE_WRITE', ziel, binding, risks=risks, exact=True, describe=f'Neue Vorlage anlegen: {v["name"]}')
    return {'mission_id': req['mission_id'], 'vorlage': v['id'], 'name': v['name'], 'werkzeuge': v['werkzeuge'], 'basis': e['basis']}


def _vorlage_neu_anwenden(hub, binding):
    try:
        out = harness_vorlagen_neu.schreiben(hub.project_root, binding.get('yaml') or '', binding.get('md') or '', binding.get('vorlage'))
    except (OSError, harness_vorlagen.VorlageFehler) as exc:
        raise ValueError(gated.REFUSED + 'vorlage_nicht_angelegt: ' + str(exc)) from None
    hub.runtime.audit.append('HARNESS_VORLAGE_ANGELEGT', component='harness', payload=dict(out, vorlage=binding.get('vorlage')))
    hub.events.publish('harness.vorlage', {'ereignis': 'HARNESS_VORLAGE_ANGELEGT', 'vorlage': binding.get('vorlage')})
    return out


def _grenzen_anwenden(hub, binding):
    if binding.get('neu') is True:
        return _vorlage_neu_anwenden(hub, binding)
    try:
        v = harness_vorlagen.laden(hub.project_root, binding.get('vorlage'))
    except harness_vorlagen.VorlageFehler as exc:
        raise ValueError(gated.REFUSED + str(exc)) from None
    if v['hash'] != binding.get('stand_hash'):
        raise ValueError(gated.STALE)
    try:
        out = harness_vorlagen.grenzen_schreiben(hub.project_root, v['id'], int(binding['max_zuege']))
    except (OSError, harness_vorlagen.VorlageFehler) as exc:
        raise ValueError(gated.REFUSED + 'vorlage_nicht_schreibbar: ' + str(exc)) from None
    hub.runtime.audit.append('HARNESS_VORLAGE_WRITTEN', component='harness', payload=dict(out, vorlage=v['id']))
    hub.events.publish('harness.vorlage', {'ereignis': 'HARNESS_VORLAGE_WRITTEN', 'vorlage': v['id'], 'max_zuege': out['max_zuege']})
    return out


# ---- P0 M3: Ordner öffnen
def _laufzeit_hash(daten):
    return harness_katalog.hash_von([daten['projekte'], daten['vorgaben']])


def projekt_antrag(hub, payload):
    """POST projekte {wurzel, name?, schreibbereich?}: prüfen (400 mit Satz), dann ein Antrag mit genauer Bindung. Geschrieben wird erst nach
    Freigabe – in die Laufzeitdatei (E-A8), nie in local_config/."""
    payload = payload or {}
    alle = harness_projekte.laden(hub.project_root)
    anlegen = payload.get('anlegen') is True                 # „Neues Projekt“: `eltern` + `name` → der Ordner wird nach der Freigabe angelegt
    try:
        wurzel = payload.get('wurzel')
        if anlegen:
            if not isinstance(payload.get('eltern'), str) or not payload['eltern'].strip():
                raise harness_projekte.ProjektFehler('eltern_fehlt: der Ordner, in dem das neue Projekt angelegt wird (vollständiger Pfad)')
            wurzel = str(Path(payload['eltern'].strip()) / harness_projekte.ordnername(payload.get('name')))
        neu = harness_projekte.neues_projekt(wurzel, payload.get('name'), payload.get('schreibbereich'), vergeben=[p['id'] for p in alle],
                                            sperrzonen=[hub.project_root / 'local_config', hub.project_root / 'runtime_data'], anlegen=anlegen)
    except harness_projekte.ProjektFehler as exc:
        raise ValueError(str(exc)) from exc
    if any(p['wurzel'] == neu['wurzel'] for p in alle):
        pid = next(p['id'] for p in alle if p['wurzel'] == neu['wurzel'])
        raise ValueError(f'ordner_schon_projekt: {pid} – dieser Ordner ist schon ein Projekt. Es braucht keinen Antrag: ist die Sitzung in diesem Projekt (list_projects markiert es mit diese_sitzung), arbeite direkt darin; sonst bitte den Captain, dort eine neue Sitzung zu beginnen.')
    offen = getattr(hub, '_open_requests', None)
    offene = [r for r in (offen() if callable(offen) else []) if r.get('kind') == KIND_PROJEKT]
    if len(offene) >= PROJEKT_ANTRAEGE_MAX:                  # Härtung: ein Modell flutet den Posteingang nicht mit Ordner-Anträgen
        raise ValueError(f'zu_viele_offene_antraege: {len(offene)} Ordner-Anträge warten schon im Posteingang – erst die entscheiden')
    for r in offene:          # 02.11.2026: drei Anträge für denselben Ordner endeten nach der ersten Freigabe in `binding_stale`
        if r.get('kind') == KIND_PROJEKT and ((r.get('binding') or {}).get('projekt') or {}).get('wurzel') == neu['wurzel']:
            raise ValueError('antrag_liegt_schon_im_posteingang: ' + neu['wurzel'] + ' – bitte dort freigeben oder ablehnen (' + str(r.get('mission_id')) + ')')
    stand = harness_projekte.laufzeit_laden(hub.project_root)
    binding = dict({'projekt': neu, 'stand_hash': _laufzeit_hash(stand)}, **({'anlegen': True} if anlegen else {}))
    weit = any(m.strip() in ('**', '*') for m in neu['schreibbereich'])
    risks = [(f"Der Ordner {neu['wurzel']} wird neu angelegt und" if anlegen else f"Ordner {neu['wurzel']}") + f" wird Projekt „{neu['name']}“ ({neu['id']})",
             'Schreibbereich: ' + ', '.join(neu['schreibbereich']) + (' – das Modell darf nach Katalog überall darin schreiben' if weit else '')]
    req = gated.request(hub, KIND_PROJEKT, 'HARNESS_PROJEKT_ADD', ZIEL_PROJEKTE, binding, risks=risks, exact=True,
                        describe=(f"Neues Projekt anlegen: {neu['name']}" if anlegen else f"Ordner öffnen: {neu['name']}"))
    return {'mission_id': req['mission_id'], 'projekt': neu, 'stand_hash': binding['stand_hash']}


def _projekt_anwenden(hub, binding):
    stand = harness_projekte.laufzeit_laden(hub.project_root)
    if _laufzeit_hash(stand) != binding.get('stand_hash'):
        raise ValueError(gated.STALE)
    neu = dict(binding.get('projekt') or {})
    if binding.get('anlegen') is True:       # der Ordner entsteht erst jetzt, nach der Freigabe; er darf dann noch nicht da sein
        try:
            Path(neu['wurzel']).mkdir(parents=False, exist_ok=False)
        except OSError as exc:
            raise ValueError(gated.REFUSED + 'ordner_nicht_angelegt: ' + str(exc)) from None
    try:
        harness_projekte.pruefen({'projekte': [neu]})
        if any(p['id'] == neu['id'] for p in harness_projekte.laden(hub.project_root)):
            raise harness_projekte.ProjektFehler('projekt_id_inzwischen_vergeben')
        out = harness_projekte.laufzeit_schreiben(hub.project_root, {'projekte': stand['projekte'] + [neu], 'vorgaben': stand['vorgaben']})
    except (OSError, harness_projekte.ProjektFehler) as exc:
        raise ValueError(gated.REFUSED + 'projekt_nicht_schreibbar: ' + str(exc)) from None
    hub.runtime.audit.append('HARNESS_PROJEKT_ADDED', component='harness', payload=dict(out, projekt=neu['id'], wurzel=neu['wurzel'], schreibbereich=neu['schreibbereich'], angelegt=binding.get('anlegen') is True))
    hub.events.publish('harness.projekt', {'ereignis': 'HARNESS_PROJEKT_ADDED', 'projekt': neu['id'], 'name': neu['name']})
    return dict(out, projekt=neu)


# ---- Code-Stand übernehmen (Captain 04.11.2026): ein Antrag im Posteingang statt einer Notiz in jeder neuen Sitzung
def _offene_code_stand(hub, projekt_id):
    offen = getattr(hub, '_open_requests', None)
    return [r for r in (offen() if callable(offen) else []) if r.get('kind') == KIND_CODE_STAND and (r.get('binding') or {}).get('projekt') == projekt_id]


def _git(wurzel, *args):
    """Eine lesende git-Abfrage im Projekt; ohne git, ohne Repo oder bei Fehler ''. Nur Anzeige, nie Grundlage einer Entscheidung."""
    try:
        r = subprocess.run(['git', '-C', str(wurzel), *args], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=15)
        return r.stdout.strip() if r.returncode == 0 else ''
    except (OSError, subprocess.SubprocessError):
        return ''


def code_herkunft(wurzel, liste):
    """Wo der Code herkommt, als Zeilen für den Antrag: von der Harness selbst geschrieben (Spur), Commits laut git (die letzten) und was noch nicht committet ist.
    Der Code liegt im Projekt; die Quelle ist dort nachzulesen (`git log`, `git diff`)."""
    pfade = [e['pfad'] for e in liste]
    zeilen = []
    selbst = [e for e in liste if e.get('herkunft')]
    zeilen.append(f'Herkunft: {len(selbst)} von {len(liste)} Dateien hat die Harness selbst geschrieben (Sitzung und Weg stehen in der Spur)' if selbst
                  else 'Herkunft: keine der Dateien hat die Harness selbst geschrieben – der Code kam von außen (andere Arbeit im Projekt, git pull, Programme)')
    if (_git(wurzel, 'rev-parse', '--is-inside-work-tree') == 'true'):
        offen = {z[3:].strip().strip('"').replace('\\', '/') for z in _git(wurzel, 'status', '--porcelain', '--', *pfade).splitlines()}
        log = _git(wurzel, 'log', '-n', '6', '--format=%h %s', '--', *pfade)
        if log:
            zeilen.append('Letzte Commits an diesen Dateien (git log): ' + ' · '.join(z[:90] for z in log.splitlines()))
        zeilen.append(f'{len(offen)} der Dateien sind noch nicht committet (git status)' if offen else 'Alle Dateien sind committet; Änderungen: git log und git diff im Projekt')
    return zeilen


def code_stand_antrag(hub, projekt, cs):
    """POST code_stand/antrag {projekt}: legt für genau die jetzt ungesehenen Dateien in genau ihrer Fassung einen Antrag in den Posteingang. Der Captain bestätigt einmal
    (Klasse H, Freigabe-Tür), ohne den Code zu lesen; ändert sich danach eine Datei, ist die Bindung veraltet (`binding_stale`). Derselbe Stand ist schon beantragt: kein zweiter Antrag."""
    liste = cs.ungesehen()
    if not liste:
        raise ValueError('nichts_ungesehen: im Projekt ' + projekt['id'] + ' gibt es keinen Code, den der Captain nicht gesehen hat')
    dateien = harness_code_stand.bindung(liste)
    for r in _offene_code_stand(hub, projekt['id']):
        if (r.get('binding') or {}).get('dateien') == dateien:
            return {'mission_id': r.get('mission_id'), 'anzahl': len(liste), 'schon_offen': True}
    neu = sum(1 for e in liste if e['alt'] is None)
    weg = sum(1 for e in liste if e['neu'] is None)
    binding = {'projekt': projekt['id'], 'wurzel': str(projekt['wurzel']), 'dateien': dateien}
    risks = [f'{len(liste)} Code-Dateien in Projekt „{projekt["name"]}“ ({neu} neu, {weg} gelöscht, {len(liste) - neu - weg} geändert) gelten danach als gesehen',
             'Danach laufen Läufe und Befehle ohne Code-Karte; nur diese Fassung ist gedeckt, jede spätere Änderung braucht wieder eine Bestätigung',
             'Zum Beispiel: ' + ', '.join(e['pfad'] for e in liste[:5]) + (' …' if len(liste) > 5 else '')] + code_herkunft(projekt['wurzel'], liste)
    req = gated.request(hub, KIND_CODE_STAND, 'HARNESS_CODE_STAND_UEBERNEHMEN', ZIEL_CODE_STAND + '/' + projekt['id'], binding, risks=risks, exact=True,
                        describe=f'Code-Stand übernehmen: {len(liste)} Dateien in {projekt["name"]}')
    return {'mission_id': req['mission_id'], 'anzahl': len(liste), 'schon_offen': False}


def _code_stand_anwenden(hub, binding):
    pid = binding.get('projekt')
    projekt = next((p for p in harness_projekte.laden(hub.project_root) if p['id'] == pid), None)
    if projekt is None or str(projekt['wurzel']) != binding.get('wurzel'):
        raise ValueError(gated.REFUSED + 'projekt_unbekannt')
    cs = harness_code_stand.CodeStand(hub.project_root / 'runtime_data' / 'harness' / 'code_stand', projekt['wurzel'], pid,
                                      audit=lambda e, p: hub.runtime.audit.append(e, component='harness', payload=p))
    if harness_code_stand.bindung(cs.ungesehen()) != binding.get('dateien'):
        raise ValueError(gated.STALE)                  # seit dem Antrag hat sich Code geändert: nichts wird übernommen
    n = cs.gesehen_setzen(binding['dateien'])
    hub.runtime.audit.append('HARNESS_CODE_STAND_UEBERNOMMEN', component='harness', payload={'projekt': pid, 'anzahl': n, 'kanal': 'posteingang'})
    hub.events.publish('harness.code_stand', {'ereignis': 'HARNESS_CODE_STAND_UEBERNOMMEN', 'projekt': pid, 'anzahl': n})
    return {'projekt': pid, 'anzahl': n}


def registrieren(registry):
    """Vor `kinds.freeze()` in uix_server: die Applier aller Arten."""
    gated.register_applier(KIND_CODE_STAND, _code_stand_anwenden, registry=registry)
    gated.register_applier(KIND_KATALOG, _katalog_anwenden, registry=registry)
    gated.register_applier(KIND_VORLAGE, _grenzen_anwenden, registry=registry)
    gated.register_applier(KIND_PROJEKT, _projekt_anwenden, registry=registry)
