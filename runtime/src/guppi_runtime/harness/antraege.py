"""Anträge der Einstellungen mit Gate (SPEC_HARNESS_SHELL_v1 Stufe 5, G2 §4/§5, D-U2/D-U4, G3 N1/N2).

Der Editor schreibt nie direkt: `katalog_antrag`/`katalog_entfernen_antrag`/`grenzen_antrag` legen über `desk/gated.request` einen
Antrag an, der im Posteingang des Captains steht. Erst „Freigeben und anwenden“ (`gated.decide`) ruft den Applier dieser Art, und der
prüft vor dem Schreiben, ob der Stand noch derselbe ist wie beim Antrag (`binding_stale`, G2 §4.4). Die Applier sind Modulfunktionen,
damit `register_applier` sie bei einem zweiten Hub im selben Prozess wiedererkennt; registriert werden sie in `uix_server` vor
`kinds.freeze()` (wie `desk_wissen`)."""
from __future__ import annotations

from ..desk import gated
from . import katalog as harness_katalog
from . import vorlagen as harness_vorlagen

KIND_KATALOG = 'harness_katalog'
KIND_VORLAGE = 'harness_vorlage'
ZIEL_KATALOG = 'local_config/' + harness_katalog.DATEI


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


def _grenzen_anwenden(hub, binding):
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


def registrieren(registry):
    """Vor `kinds.freeze()` in uix_server: die Applier beider Arten."""
    gated.register_applier(KIND_KATALOG, _katalog_anwenden, registry=registry)
    gated.register_applier(KIND_VORLAGE, _grenzen_anwenden, registry=registry)
